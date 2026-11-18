"""Tests of the non-deterministic monitoring flow with scripted (non-LLM) agent nodes.

The real Strands Graph, the deterministic steps and the guardrails run unchanged; only the five LLM
agents are replaced by scripted FunctionNodes that call the same tools the agents get.
"""

from datetime import date

import pytest

from real_basket.core.engine import compute_results
from real_basket.core.settings import get_settings
from real_basket.core.store import DataStore
from real_basket.data.sources import sources_for
from real_basket.flow.graph import FunctionNode, auto_approver, deferred_approver, run_flow
from real_basket.flow.steps import publish_run
from real_basket.flow.tools import FlowTools
from real_basket.schemas.flow import DATASETS, Decision, DatasetStatus, RunPlan, RunStatus, Trigger

END = date(2025, 12, 1)


@pytest.fixture
def settings(monkeypatch):
    def apply(**env):
        for k, v in {"DEMO_FAULT_RATE": "0", "DEMO_FAULT_SEED": "1", "DESTATIS_GENESIS_TOKEN": "", **env}.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()
        return get_settings()
    yield apply
    get_settings.cache_clear()


def scripted(datasets=DATASETS, report_conf=0.9, replan=False, collect=True, validator_accepts=False,
             skip_investigation=False):
    def factory(ctx):
        ft = FlowTools(ctx)

        def planner():
            months = 30 if ctx.replan_request else 24
            return ft.submit_plan(list(datasets), months, "test", 2, "scripted")

        def collector():
            for d in ctx.with_status(DatasetStatus.PENDING):
                if not collect:
                    continue
                tried = ctx.tried_sources.get(d, [])
                options = [s.name for s in sources_for(d) if s.available() and s.name not in tried]
                ft.fetch(d, (options or [tried[-1]])[0])
            return "collected"

        def validator():
            for d in ctx.with_status(DatasetStatus.COLLECTED):
                bad = ctx.reports[d].has_critical
                ft.decide(d, "accept" if validator_accepts or not bad else "retry", "scripted")
            return "validated"

        def analyst():
            if replan and ctx.replans == 0:
                return ft.request_more_data(["food"], "need longer history", months=30)
            if not skip_investigation and ft.results().get("investigation_required"):
                ft.investigate("category")
            ft.submit_analysis("scripted analysis", ["rent"], 0.9)
            return "analysed"

        def reporter():
            return ft.submit_report("# Scripted report", ["chat", "pdf"], report_conf)

        fns = {"planner": planner, "collector": collector, "validator": validator, "analyst": analyst,
               "reporter": reporter}
        return {n: FunctionNode(n, f) for n, f in fns.items()}
    return factory


def run(tmp_path, approver=auto_approver, **kw):
    return run_flow("test goal", Trigger.SCHEDULE, approver=approver, executors=scripted(**kw),
                    store=DataStore(tmp_path), end=END)


def test_happy_path_is_published_and_reproducible(tmp_path, settings):
    settings()
    ctx = run(tmp_path)
    assert ctx.run_status == RunStatus.PUBLISHED
    assert ctx.path[:2] == ["planner", "plan_gate"] and ctx.path[-1] == "publish"
    assert all(s == DatasetStatus.ACCEPTED for s in ctx.status.values())
    # numbers are reproducible from the stored dataset
    rows, weights = ctx.store.load_dataset(ctx.run_id)
    assert compute_results(rows, weights) == ctx.results
    record = ctx.store.load_run(ctx.run_id)
    assert record["status"] == "published" and any(f.endswith("report.pdf") for f in record["published_files"])
    md = ctx.report["final_markdown"]
    assert "does NOT mean" in md and "Demo data" in md and ctx.results["dataset_hash"] in md


def test_faulty_source_triggers_retry_with_alternative_source(tmp_path, settings):
    settings(DEMO_FAULT_RATE=1)
    ctx = run(tmp_path)
    assert ctx.run_status == RunStatus.PUBLISHED
    assert ctx.path.count("collector") == 2                   # validation loop ran twice
    food = ctx.record()["datasets"]["food"]
    assert food["status"] == "accepted" and food["attempts"] == 2
    assert food["sources_tried"] == ["demo-supermarket-api", "demo-price-comparison"]
    assert ctx.memory.reliability("demo-supermarket-api") < ctx.memory.reliability("demo-price-comparison")


def test_critical_data_can_never_be_accepted(tmp_path, settings):
    settings(DEMO_FAULT_RATE=1)
    ctx = run(tmp_path, validator_accepts=True)
    assert ctx.accepted                                     # the alternative sources are clean
    for d, decisions in ctx.decisions.items():
        first = decisions[0]
        assert first["source"] != "demo-supermarket-api" or first["decision"] != "accept"
    assert ctx.status["food"] == DatasetStatus.ACCEPTED
    assert ctx.accepted["food"][0].source == "demo-price-comparison"


def test_apply_decision_rejects_accept_on_critical(tmp_path, settings):
    settings(DEMO_FAULT_RATE=1)
    from real_basket.flow.context import RunContext

    ctx = RunContext(trigger=Trigger.QUESTION, goal="g", approver=deferred_approver, store=DataStore(tmp_path),
                     end=END)
    ctx.set_plan(RunPlan(datasets=["food"], months=24))
    FlowTools(ctx).fetch("food", "demo-supermarket-api")
    from real_basket.flow.steps import quality_checks

    quality_checks(ctx)
    assert ctx.reports["food"].has_critical
    assert "Rejected by hard rule" in ctx.apply_decision("food", Decision.ACCEPT, "x", "validator")
    assert ctx.status["food"] == DatasetStatus.COLLECTED


def test_low_confidence_waits_for_human_approval(tmp_path, settings):
    settings()
    ctx = run(tmp_path, approver=deferred_approver, report_conf=0.3)
    assert ctx.run_status == RunStatus.PENDING_APPROVAL and ctx.path[-1] == "release_gate"
    assert ctx.store.load_run(ctx.run_id)["status"] == "pending_approval"
    publish_run(ctx.store, ctx.run_id, approved_by="test")
    assert ctx.store.load_run(ctx.run_id)["status"] == "published"
    assert {"actor": "human", "action": "approved"}.items() <= ctx.store.load_audit(ctx.run_id)[-1].items()


def test_human_rejection_is_audited_and_not_published(tmp_path, settings):
    from real_basket.flow.steps import reject_run

    settings()
    ctx = run(tmp_path, approver=deferred_approver, report_conf=0.3)
    reject_run(ctx.store, ctx.run_id, rejected_by="test", reason="numbers look off")
    record = ctx.store.load_run(ctx.run_id)
    assert record["status"] == "rejected" and record["approved"] is False
    assert not record.get("published_files")
    last = ctx.store.load_audit(ctx.run_id)[-1]
    assert last["action"] == "rejected" and last["detail"]["reason"] == "numbers look off"


def test_analyst_can_trigger_replanning(tmp_path, settings):
    settings()
    ctx = run(tmp_path, replan=True)
    assert ctx.path.count("planner") == 2 and ctx.replans == 1
    assert ctx.plan.months == 30
    assert ctx.run_status == RunStatus.PUBLISHED


def test_missing_data_is_escalated_and_excluded(tmp_path, settings):
    settings()
    ctx = run(tmp_path, collect=False)
    assert "human_review" in ctx.path
    assert all(s == DatasetStatus.EXCLUDED for s in ctx.status.values())
    assert ctx.run_status == RunStatus.FAILED and ctx.results is None


def test_investigation_is_enforced_for_large_deviation(tmp_path, settings):
    settings(DEVIATION_THRESHOLD_PP=0)
    ctx = run(tmp_path, skip_investigation=True)
    assert ctx.analysis is None                             # submit_analysis was rejected
    assert ctx.investigations == []
    assert ctx.compute_confidence() <= ctx.report["confidence"]


def test_scoped_plan_is_not_penalised_as_missing_data(tmp_path, settings):
    """A rent-only question: unplanned categories are out of scope, not excluded data."""
    settings()
    ctx = run(tmp_path, datasets=["rent", "cpi"])
    cov = ctx.coverage()
    assert cov == {"excluded": [], "out_of_scope": ["food", "energy", "mobility"]}
    assert ctx.confidence == 0.9 and ctx.run_status == RunStatus.PUBLISHED
    assert "out of scope: food, energy, mobility" in ctx.report["final_markdown"]
    assert FlowTools(ctx).results()["excluded_categories"] == []


def test_planned_but_lost_category_lowers_confidence(tmp_path, settings):
    settings()
    ctx = run(tmp_path)
    before = ctx.compute_confidence()
    ctx.results = {**ctx.results, "excluded_categories": ["food"]}     # food was planned, then lost
    assert ctx.coverage()["excluded"] == ["food"]
    assert ctx.compute_confidence() == round(before - 0.15, 2)


def test_audit_log_survives_parallel_tool_calls(tmp_path):
    """Strands runs parallel tool calls in threads; audit lines must never interleave."""
    from concurrent.futures import ThreadPoolExecutor

    from real_basket.schemas.flow import AuditEvent

    store = DataStore(tmp_path)
    detail = {"reason": "x" * 2000}

    def write(i):
        store.append_audit("r1", AuditEvent(actor="validator", action=f"a{i}", detail=detail))

    with ThreadPoolExecutor(16) as pool:
        list(pool.map(write, range(400)))
    events = store.load_audit("r1")
    assert len(events) == 400
    assert not [e for e in events if e["action"] == "corrupt_audit_line"]
