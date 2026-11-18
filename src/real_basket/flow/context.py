"""Run state shared by all nodes of one monitoring run, incl. hard guardrails and audit logging.

Agents change the state only through tools (see tools.py); every change goes through a method of
this class so that the rules (retry limits, no acceptance of critical data, ...) are enforced in code.
Routing between graph nodes is a pure read of this state (see `next_after_*`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from real_basket.core.engine import DEFAULT_WEIGHTS, carry_forward
from real_basket.core.settings import Settings, get_settings
from real_basket.core.store import DataStore, Memory
from real_basket.core.validation import validate_rows
from real_basket.data.sources import period_range
from real_basket.schemas.flow import (
    DATASETS,
    AuditEvent,
    DatasetStatus,
    Decision,
    Row,
    RunPlan,
    RunStatus,
    Trigger,
    ValidationReport,
)

# approver(kind, payload) -> kind "data": "accept" | "exclude"; kind "publish": True | False | None (later)
Approver = Callable[[str, dict], Any]


@dataclass
class RunContext:
    trigger: Trigger
    goal: str
    approver: Approver
    store: DataStore = field(default_factory=DataStore)
    settings: Settings = field(default_factory=get_settings)
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    end: date | None = None
    run_id: str = field(default_factory=DataStore.new_run_id)

    plan: RunPlan | None = None
    status: dict[str, DatasetStatus] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    tried_sources: dict[str, list[str]] = field(default_factory=dict)
    candidates: dict[str, list[Row]] = field(default_factory=dict)
    reports: dict[str, ValidationReport] = field(default_factory=dict)
    decisions: dict[str, list[dict]] = field(default_factory=dict)
    accepted: dict[str, list[Row]] = field(default_factory=dict)
    reused: dict[str, dict] = field(default_factory=dict)      # dataset -> from_run, reason, carried months
    human_overrides: list[str] = field(default_factory=list)

    results: dict | None = None
    calc_error: str | None = None
    investigation_steps: int = 0
    investigations: list[dict] = field(default_factory=list)
    replans: int = 0
    replan_request: dict | None = None
    analysis: dict | None = None
    report: dict | None = None
    confidence: float | None = None
    approved: bool | None = None
    approval_reason: str | None = None      # why a human must approve (low confidence / fallback data)
    run_status: RunStatus = RunStatus.RUNNING
    published_files: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def __post_init__(self) -> None:
        self.memory = Memory(self.store)
        self.log("system", "run_started", trigger=self.trigger.value, goal=self.goal)

    # --- audit ----------------------------------------------------------------------------------
    def log(self, actor: str, action: str, /, **detail: Any) -> None:
        event = AuditEvent(actor=actor, action=action, detail=detail)
        self.audit.append(event.model_dump())
        self.store.append_audit(self.run_id, event)

    # --- plan -----------------------------------------------------------------------------------
    def expected_periods(self) -> list[str]:
        start, _ = period_range(self.plan.months, self.end)
        idx0 = start.year * 12 + start.month - 1
        return [date((idx0 + i) // 12, (idx0 + i) % 12 + 1, 1).isoformat() for i in range(self.plan.months)]

    def set_plan(self, plan: RunPlan, actor: str = "planner") -> str:
        """Hard rule: the essential index is only defined for the complete basket, so every plan covers
        all DATASETS. The planner decides per dataset whether to fetch fresh data or re-use stored,
        validated data (`plan.reuse`), plus history length, focus and investigation depth."""
        requested = set((self.replan_request or {}).get("datasets", []))
        asked = [d for d in dict.fromkeys(plan.datasets) if d in DATASETS]
        if set(asked) != set(DATASETS):
            self.log("guardrail", "plan_amended", requested=asked, datasets=list(DATASETS),
                     reason="the essential index needs the complete basket (all categories + CPI)")
        plan.datasets = list(DATASETS)
        plan.reuse = [d for d in dict.fromkeys(x.lower() for x in plan.reuse) if d in DATASETS and d not in requested]
        plan.investigation_depth = min(plan.investigation_depth, self.settings.MAX_INVESTIGATION_STEPS)

        months_changed = self.plan is not None and self.plan.months != plan.months
        if self.plan is not None:  # re-plan: previous numbers are outdated
            self.results, self.analysis = None, None
        self.plan = plan
        for d in DATASETS:
            if d not in self.status or months_changed or d in requested:
                self.status[d] = DatasetStatus.PENDING
                self.attempts[d] = 0
                self.reused.pop(d, None)
                self.accepted.pop(d, None)
                self.candidates.pop(d, None)
                self.reports.pop(d, None)
        self.replan_request = None
        self.log(actor, "plan_submitted", **plan.model_dump())
        notes = [f"{d}: {'re-used' if self.reuse_dataset(d, 'planned') else 'no usable stored data, will fetch'}"
                 for d in plan.reuse if self.status[d] == DatasetStatus.PENDING]
        pending = self.with_status(DatasetStatus.PENDING)
        return f"Plan accepted (complete basket). Datasets to collect: {pending}." + (
            f" Re-use: {'; '.join(notes)}." if notes else "")

    def reuse_dataset(self, dataset: str, reason: str) -> bool:
        """Take `dataset` from the last validated run (missing trailing months carried forward).
        reason 'planned' = planner chose it, 'fallback' = fresh data was lost (needs human approval)."""
        found = self.store.latest_validated(dataset, exclude_run=self.run_id)
        if found is None:
            self.log("guardrail", "reuse_unavailable", dataset=dataset, reason=reason, error="no validated data stored")
            return False
        from_run, stored = found
        expected = self.expected_periods()
        try:
            rows, filled = carry_forward(stored, expected, self.settings.MAX_CARRY_FORWARD_MONTHS)
        except ValueError as exc:
            self.log("guardrail", "reuse_unavailable", dataset=dataset, reason=reason, from_run=from_run, error=str(exc))
            return False
        report = validate_rows(dataset, rows, expected)
        if report.has_critical:
            self.log("guardrail", "reuse_unavailable", dataset=dataset, reason=reason, from_run=from_run,
                     error="stored data fails the quality checks")
            return False
        self.status[dataset] = DatasetStatus.ACCEPTED
        self.candidates[dataset] = self.accepted[dataset] = rows
        self.reports[dataset] = report
        self.reused[dataset] = {"from_run": from_run, "reason": reason, "carried_forward_months": filled,
                                "last_observed": max(r.period for r in stored)}
        self.log("guardrail", "dataset_reused", dataset=dataset, **self.reused[dataset])
        return True

    def ensure_plan(self) -> None:
        if self.plan is None:
            self.set_plan(RunPlan(months=24, focus="default", investigation_depth=2,
                                  rationale="fallback: planner submitted no plan"), actor="guardrail")

    # --- datasets -------------------------------------------------------------------------------
    def with_status(self, *statuses: DatasetStatus) -> list[str]:
        return [d for d, s in self.status.items() if s in statuses]

    def apply_decision(self, dataset: str, decision: Decision, reason: str, actor: str) -> str:
        if self.status.get(dataset) != DatasetStatus.COLLECTED:
            return f"Error: '{dataset}' has no collected data waiting for a decision."
        report = self.reports[dataset]
        if decision == Decision.ACCEPT and report.has_critical:
            return ("Rejected by hard rule: data with critical issues cannot be accepted. "
                    "Choose retry (alternative source), exclude or escalate.")
        if decision == Decision.RETRY and self.attempts[dataset] >= self.settings.MAX_SOURCE_ATTEMPTS:
            self.log("guardrail", "retry_converted_to_escalate", dataset=dataset,
                     attempts=self.attempts[dataset])
            decision, reason = Decision.ESCALATE, f"{reason} (retry limit reached)"

        new_status = {Decision.ACCEPT: DatasetStatus.ACCEPTED, Decision.RETRY: DatasetStatus.PENDING,
                      Decision.EXCLUDE: DatasetStatus.EXCLUDED, Decision.ESCALATE: DatasetStatus.ESCALATED}
        self.status[dataset] = new_status[decision]
        if decision == Decision.ACCEPT:
            self.accepted[dataset] = self.candidates[dataset]
        self.memory.record_source(report.source or self.tried_sources[dataset][-1], decision == Decision.ACCEPT)
        entry = {"decision": decision.value, "reason": reason, "actor": actor, "source": report.source,
                 "score": report.score, "attempt": self.attempts[dataset]}
        self.decisions.setdefault(dataset, []).append(entry)
        self.log(actor, "validation_decision", dataset=dataset, **entry)
        return f"Decision for '{dataset}': {decision.value}."

    # --- routing (pure reads, evaluated by graph edge conditions) -------------------------------
    def next_after_plan_gate(self) -> str:
        return "collector" if self.with_status(DatasetStatus.PENDING) else "calculate"

    def next_after_quality_checks(self) -> str:
        return "validator" if self.with_status(DatasetStatus.COLLECTED) else "validation_gate"

    def next_after_validation_gate(self) -> str:
        if self.with_status(DatasetStatus.PENDING):
            return "collector"
        if self.with_status(DatasetStatus.ESCALATED):
            return "human_review"
        return "calculate"

    def next_after_calculate(self) -> str:
        return "analyst" if self.results else "reporter"

    def next_after_analyst(self) -> str:
        return "planner" if self.replan_request else "reporter"

    # --- confidence -----------------------------------------------------------------------------
    def fallbacks(self) -> list[str]:
        """Datasets whose fresh data was lost and replaced by stored data: a human must approve."""
        return [d for d, r in self.reused.items() if r["reason"] == "fallback"]

    def compute_confidence(self) -> float:
        if not self.results:
            return 0.0
        scores = [self.reports[d].score for d in self.accepted if d in self.reports]
        conf = min([(self.report or {}).get("confidence", 1.0), (self.analysis or {}).get("confidence", 1.0),
                    *scores])
        conf -= 0.05 * sum(1 for r in self.reused.values() if r["carried_forward_months"])
        conf -= 0.10 * len(self.fallbacks())
        conf -= 0.10 * len(self.human_overrides)
        return round(max(0.0, min(1.0, conf)), 2)

    # --- persistence ----------------------------------------------------------------------------
    def record(self) -> dict:
        return {
            "run_id": self.run_id, "created_at": self.created_at, "trigger": self.trigger.value,
            "goal": self.goal, "status": self.run_status.value,
            "plan": self.plan.model_dump() if self.plan else None,
            "datasets": {d: {"status": s.value, "attempts": self.attempts.get(d, 0),
                             "sources_tried": self.tried_sources.get(d, []),
                             "score": self.reports[d].score if d in self.reports else None,
                             "reused_from": self.reused.get(d),
                             "decisions": self.decisions.get(d, [])} for d, s in self.status.items()},
            "human_overrides": self.human_overrides, "reused": self.reused, "results": self.results,
            "calc_error": self.calc_error,
            "investigations": self.investigations, "replans": self.replans, "analysis": self.analysis,
            "report": self.report, "confidence": self.confidence, "approved": self.approved,
            "approval_reason": self.approval_reason,
            "published_files": self.published_files, "path": self.path,
        }

    def save(self) -> None:
        self.store.save_run(self.run_id, self.record())
