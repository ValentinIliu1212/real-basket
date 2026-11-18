"""Strands Graph of the non-deterministic monitoring flow.

    planner -> plan_gate -> collector -> quality_checks -> validator -> validation_gate
                   |            ^                 |                        |  |  |
                   |            +---- retry ------+------------------------+  |  +-> human_review
                   v                                                          v          |
               calculate <----------------------------------------------------+----------+
                   |  (no results) -> reporter
                   v
                analyst --(request_more_data)--> planner          (re-plan loop)
                   v
                reporter -> release_gate --(confidence >= threshold or human approval)--> publish

LLM agents: planner, collector, validator, analyst, reporter.
Deterministic function nodes: plan_gate, quality_checks, validation_gate, human_review, calculate,
release_gate, publish. Edge conditions are pure reads of the RunContext.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from typing import Any

from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics

from real_basket.agents.prompts import (
    ANALYST_PROMPT,
    FLOW_COLLECTOR_PROMPT,
    PLANNER_PROMPT,
    REPORTER_PROMPT,
    VALIDATOR_PROMPT,
)
from real_basket.core.store import DataStore
from real_basket.flow import steps
from real_basket.flow.context import Approver, RunContext
from real_basket.flow.tools import FlowTools, strands_toolsets
from real_basket.schemas.flow import RunStatus, Trigger

AGENT_NODES = ("planner", "collector", "validator", "analyst", "reporter")
AGENT_PROMPTS = {"planner": PLANNER_PROMPT, "collector": FLOW_COLLECTOR_PROMPT, "validator": VALIDATOR_PROMPT,
                 "analyst": ANALYST_PROMPT, "reporter": REPORTER_PROMPT}


class FunctionNode(MultiAgentBase):
    """Graph node that runs a deterministic Python function instead of an LLM."""

    def __init__(self, name: str, fn: Callable[[], str]):
        super().__init__()
        self.id = name
        self.name = name
        self.fn = fn

    async def invoke_async(self, task: Any, invocation_state: dict | None = None, **kwargs: Any) -> MultiAgentResult:
        start = time.time()
        text = self.fn()
        result = AgentResult(stop_reason="end_turn", message={"role": "assistant", "content": [{"text": text}]},
                             metrics=EventLoopMetrics(), state={})
        ms = round((time.time() - start) * 1000)
        return MultiAgentResult(status=Status.COMPLETED, execution_time=ms, execution_count=1,
                                results={self.name: NodeResult(result=result, execution_time=ms,
                                                               status=Status.COMPLETED, execution_count=1)})


def create_flow_agents(ctx: RunContext) -> dict[str, Agent]:
    from real_basket.agents.orchestrator import create_model

    toolsets = strands_toolsets(FlowTools(ctx))
    prefix = ctx.settings.AGENT_NAME_PREFIX
    return {name: Agent(name=f"{prefix}-{name.upper()}", system_prompt=AGENT_PROMPTS[name],
                        model=create_model(temperature=ctx.settings.FLOW_TEMPERATURE),
                        tools=toolsets[name], callback_handler=None)
            for name in AGENT_NODES}


def _tracked(ctx: RunContext, name: str, fn: Callable[[RunContext], str]) -> Callable[[], str]:
    def run() -> str:
        ctx.path.append(name)
        return fn(ctx)
    return run


Executors = dict[str, Any] | Callable[[RunContext], dict[str, Any]]


def build_graph(ctx: RunContext, executors: Executors | None = None):
    """Build the graph. `executors` (or a factory taking the RunContext) can replace the LLM agents,
    e.g. scripted nodes in tests."""
    if callable(executors):
        executors = executors(ctx)
    executors = executors or create_flow_agents(ctx)
    b = GraphBuilder()
    for name in AGENT_NODES:
        b.add_node(executors[name], name)
    for name, fn in {"plan_gate": steps.plan_gate, "quality_checks": steps.quality_checks,
                     "validation_gate": steps.validation_gate, "human_review": steps.human_review,
                     "calculate": steps.calculate, "release_gate": steps.release_gate,
                     "publish": steps.publish}.items():
        b.add_node(FunctionNode(name, _tracked(ctx, name, fn)), name)

    def route(src: str, dst: str, decide: Callable[[], str]) -> None:
        b.add_edge(src, dst, condition=lambda _state: decide() == dst)

    b.add_edge("planner", "plan_gate")
    route("plan_gate", "collector", ctx.next_after_plan_gate)
    route("plan_gate", "calculate", ctx.next_after_plan_gate)
    b.add_edge("collector", "quality_checks")
    route("quality_checks", "validator", ctx.next_after_quality_checks)
    route("quality_checks", "validation_gate", ctx.next_after_quality_checks)
    b.add_edge("validator", "validation_gate")
    route("validation_gate", "collector", ctx.next_after_validation_gate)       # retry loop
    route("validation_gate", "human_review", ctx.next_after_validation_gate)
    route("validation_gate", "calculate", ctx.next_after_validation_gate)
    b.add_edge("human_review", "calculate")
    route("calculate", "analyst", ctx.next_after_calculate)
    route("calculate", "reporter", ctx.next_after_calculate)
    route("analyst", "planner", ctx.next_after_analyst)                         # re-plan loop
    route("analyst", "reporter", ctx.next_after_analyst)
    b.add_edge("reporter", "release_gate")
    b.add_edge("release_gate", "publish", condition=lambda _state: ctx.approved is True)

    b.set_entry_point("planner")
    b.reset_on_revisit(True)
    b.set_max_node_executions(ctx.settings.MAX_NODE_EXECUTIONS)
    b.set_execution_timeout(ctx.settings.RUN_TIMEOUT_S)
    return b.build()


def run_flow(goal: str, trigger: Trigger = Trigger.QUESTION, approver: Approver | None = None,
             executors: Executors | None = None, weights: dict[str, float] | None = None,
             store: DataStore | None = None, end: date | None = None) -> RunContext:
    """Run one monitoring flow end-to-end and persist run record, audit trail and memory."""
    kwargs: dict[str, Any] = {"trigger": trigger, "goal": goal, "approver": approver or deferred_approver,
                              "end": end}
    if weights:
        kwargs["weights"] = weights
    if store:
        kwargs["store"] = store
    ctx = RunContext(**kwargs)
    graph = build_graph(ctx, executors)
    task = (f"Trigger: {trigger.value}. Goal: {goal}. Run id: {ctx.run_id}. "
            "Use your tools; the run state is shared between all agents.")
    try:
        result = graph(task)
        ctx.path = [n.node_id for n in result.execution_order]
        graph_status = str(getattr(result.status, "value", result.status))
    except Exception as exc:  # noqa: BLE001 - a failed run must still be persisted
        graph_status = f"error: {exc}"
    ctx.log("system", "graph_finished", status=graph_status, path=ctx.path)
    if ctx.run_status == RunStatus.RUNNING:
        ctx.run_status = RunStatus.FAILED
        ctx.log("system", "run_failed", reason=f"graph ended without release ({graph_status})")
    _remember(ctx)
    ctx.save()
    return ctx


def _remember(ctx: RunContext) -> None:
    r = ctx.results or {}
    ctx.memory.add_run({"run_id": ctx.run_id, "trigger": ctx.trigger.value, "status": ctx.run_status.value,
                        "goal": ctx.goal[:120], "period": r.get("period"), "deviation_pp": r.get("deviation_pp"),
                        "excluded": r.get("excluded_categories", []),
                        "retries": {d: a for d, a in ctx.attempts.items() if a > 1}})
    ctx.memory.save()


# --- approvers (human-in-the-loop) -------------------------------------------------------------

def deferred_approver(kind: str, payload: dict) -> Any:
    """Non-interactive: escalated data is excluded, low-confidence reports wait for approval (UI)."""
    return "exclude" if kind == "data" else None


def auto_approver(kind: str, payload: dict) -> Any:
    """Approves everything (demo / tests only)."""
    return "accept" if kind == "data" else True


def cli_approver(kind: str, payload: dict) -> Any:
    if kind == "data":
        print(f"\n[HUMAN REVIEW] Dataset '{payload['dataset']}' needs a decision.")
        print(f"Quality report: {payload['report']}")
        return "accept" if input("Accept anyway? [y/N] ").strip().lower() == "y" else "exclude"
    print(f"\n[APPROVAL] Confidence {payload['confidence']} is below the threshold.\n")
    print(payload["markdown"])
    answer = input("\nPublish? [y]es / [n]o / [l]ater: ").strip().lower()
    return {"y": True, "n": False}.get(answer)
