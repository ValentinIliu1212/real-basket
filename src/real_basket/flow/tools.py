"""Tools of the flow agents. `FlowTools` holds the logic (plain Python, unit-testable);
`strands_toolsets` wraps it as Strands tools per agent role."""

from __future__ import annotations

from strands import tool

from real_basket.core.investigation import category_breakdown, item_changes, regional_rent_changes
from real_basket.data.sources import SourceUnavailableError, get_source, sources_for
from real_basket.flow.context import RunContext
from real_basket.schemas.flow import CATEGORY_DATASETS, DATASETS, DatasetStatus, Decision, RunPlan

OUTPUTS = ("chat", "dashboard", "pdf", "alert")


class FlowTools:
    def __init__(self, ctx: RunContext):
        self.ctx = ctx

    # --- shared ---------------------------------------------------------------------------------
    def run_state(self) -> dict:
        c = self.ctx
        s = c.settings
        return {
            "run_id": c.run_id, "trigger": c.trigger.value, "goal": c.goal,
            "plan": c.plan.model_dump() if c.plan else None,
            "datasets": {d: {"status": st.value, "attempts": c.attempts.get(d, 0),
                             "max_attempts": s.MAX_SOURCE_ATTEMPTS,
                             "sources_tried": c.tried_sources.get(d, []),
                             "quality": c.reports[d].model_dump() if d in c.reports else None}
                         for d, st in c.status.items()},
            "replan_request": c.replan_request, "replans_used": c.replans, "max_replans": s.MAX_REPLANS,
            "investigation_steps_used": c.investigation_steps,
            "results_available": c.results is not None, "analysis": c.analysis,
        }

    # --- planner --------------------------------------------------------------------------------
    def memory(self) -> dict:
        m = self.ctx.memory
        return {"source_reliability": {s.name: m.reliability(s.name, s.prior_reliability)
                                       for d in DATASETS for s in sources_for(d)},
                "recent_runs": m.recent_runs()}

    def list_sources(self, dataset: str = "") -> list[dict]:
        c = self.ctx
        datasets = [dataset] if dataset else list(DATASETS)
        return [{"dataset": s.dataset, "source": s.name, "description": s.description,
                 "available": s.available(), "reliability": c.memory.reliability(s.name, s.prior_reliability),
                 "tried_in_this_run": s.name in c.tried_sources.get(s.dataset, [])}
                for d in datasets for s in sources_for(d)]

    def submit_plan(self, datasets: list[str], months: int, focus: str, investigation_depth: int,
                    rationale: str) -> str:
        try:
            plan = RunPlan(datasets=[d.lower() for d in datasets], months=months, focus=focus,
                           investigation_depth=investigation_depth, rationale=rationale)
        except ValueError as exc:
            return f"Rejected: {exc}"
        return self.ctx.set_plan(plan)

    # --- collector ------------------------------------------------------------------------------
    def fetch(self, dataset: str, source: str) -> dict:
        c = self.ctx
        dataset = dataset.lower()
        if c.status.get(dataset) != DatasetStatus.PENDING:
            return {"error": f"'{dataset}' is not pending (status: {c.status.get(dataset)}). Nothing to do."}
        try:
            src = get_source(source)
        except KeyError as exc:
            return {"error": str(exc)}
        if src.dataset != dataset:
            return {"error": f"Source '{source}' does not provide '{dataset}'."}
        if c.attempts.get(dataset, 0) >= c.settings.MAX_SOURCE_ATTEMPTS:
            return {"error": f"Attempt limit reached for '{dataset}'; it will be escalated to a human."}

        c.attempts[dataset] = c.attempts.get(dataset, 0) + 1
        c.tried_sources.setdefault(dataset, []).append(source)
        try:
            rows = src.fetch(c.plan.months, attempt=c.attempts[dataset], end=c.end)
        except SourceUnavailableError as exc:
            c.memory.record_source(source, ok=False)
            c.log("collector", "fetch_failed", dataset=dataset, source=source, error=str(exc))
            return {"error": f"{exc}. Try an alternative source."}
        raw = c.store.save_raw(c.run_id, dataset, source, c.attempts[dataset], rows)
        c.candidates[dataset] = rows
        c.status[dataset] = DatasetStatus.COLLECTED
        c.log("collector", "fetched", dataset=dataset, source=source, rows=len(rows), snapshot=raw.name)
        periods = sorted({r.period for r in rows})
        return {"dataset": dataset, "source": source, "rows": len(rows),
                "items": sorted({r.item for r in rows}),
                "period_range": [periods[0], periods[-1]] if periods else None,
                "snapshot": raw.name}

    # --- validator ------------------------------------------------------------------------------
    def decide(self, dataset: str, decision: str, reason: str) -> str:
        try:
            dec = Decision(decision.lower())
        except ValueError:
            return f"Unknown decision '{decision}'. Use accept, retry, exclude or escalate."
        return self.ctx.apply_decision(dataset.lower(), dec, reason, actor="validator")

    # --- analyst --------------------------------------------------------------------------------
    def results(self) -> dict:
        c = self.ctx
        if not c.results:
            return {"error": f"No results: {c.calc_error}"}
        cov = c.coverage()
        return {**c.results, "excluded_categories": cov["excluded"], "out_of_scope_categories": cov["out_of_scope"],
                "deviation_threshold_pp": c.settings.DEVIATION_THRESHOLD_PP,
                "investigation_required": abs(c.results["deviation_pp"]) > c.settings.DEVIATION_THRESHOLD_PP}

    def investigate(self, level: str, category: str = "", region_type: str = "bundesland") -> dict:
        c = self.ctx
        limit = min(max(c.plan.investigation_depth, 1), c.settings.MAX_INVESTIGATION_STEPS)
        if not c.results:
            return {"error": "No results to investigate."}
        if c.investigation_steps >= limit:
            return {"error": f"Investigation budget ({limit} steps) used up. Conclude with what you have."}
        level = level.lower()
        if level == "category":
            data = category_breakdown(c.results)
        elif level == "item":
            if category not in c.accepted or category not in CATEGORY_DATASETS:
                return {"error": f"No accepted data for category '{category}'."}
            data = item_changes(c.accepted[category], category)
        elif level == "region":
            if region_type not in ("bundesland", "stadt"):
                return {"error": "region_type must be 'bundesland' or 'stadt'."}
            data = regional_rent_changes(region_type, c.plan.months, c.end)
        else:
            return {"error": "level must be 'category', 'item' or 'region'."}
        c.investigation_steps += 1
        entry = {"step": c.investigation_steps, "level": level, "category": category,
                 "region_type": region_type if level == "region" else "", "data": data}
        c.investigations.append(entry)
        c.log("analyst", "investigated", level=level, category=category, step=c.investigation_steps)
        return entry

    def request_more_data(self, datasets: list[str], reason: str, months: int = 0) -> str:
        c = self.ctx
        if c.replans >= c.settings.MAX_REPLANS:
            return "Rejected: re-planning budget used up. Conclude with the available data."
        c.replans += 1
        c.replan_request = {"datasets": [d.lower() for d in datasets if d.lower() in DATASETS],
                            "months": months or None, "reason": reason}
        c.log("analyst", "replan_requested", **c.replan_request)
        return "Re-planning requested. Finish now; the planner will take over."

    def submit_analysis(self, summary: str, drivers: list[str], confidence: float) -> str:
        c = self.ctx
        if not c.results:
            return "Rejected: no results available."
        if abs(c.results["deviation_pp"]) > c.settings.DEVIATION_THRESHOLD_PP and c.investigation_steps == 0:
            return (f"Rejected: deviation {c.results['deviation_pp']:+.2f} pp exceeds the threshold of "
                    f"{c.settings.DEVIATION_THRESHOLD_PP} pp. Investigate first (tool `investigate`).")
        c.analysis = {"summary": summary, "drivers": drivers, "confidence": max(0.0, min(1.0, confidence))}
        c.log("analyst", "analysis_submitted", **c.analysis)
        return "Analysis stored."

    # --- reporter -------------------------------------------------------------------------------
    def submit_report(self, markdown: str, outputs: list[str], confidence: float) -> str:
        chosen = [o.lower() for o in outputs if o.lower() in OUTPUTS] or ["chat"]
        self.ctx.report = {"markdown": markdown, "outputs": chosen, "confidence": max(0.0, min(1.0, confidence))}
        self.ctx.log("reporter", "report_submitted", outputs=chosen, confidence=confidence)
        return f"Report stored. Outputs: {chosen}. Disclaimer and provenance are appended automatically."


def strands_toolsets(ft: FlowTools) -> dict[str, list]:
    @tool
    def get_run_state() -> dict:
        """Current state of the monitoring run: plan, dataset status, attempts, quality reports, budgets."""
        return ft.run_state()

    @tool
    def get_memory() -> dict:
        """Memory from earlier runs: reliability per source (0-1) and summaries of recent runs."""
        return ft.memory()

    @tool
    def list_sources(dataset: str = "") -> list[dict]:
        """List alternative data sources (availability, reliability, already tried in this run).

        Args:
            dataset: 'food', 'rent', 'energy', 'mobility', 'cpi' or '' for all
        """
        return ft.list_sources(dataset)

    @tool
    def submit_plan(datasets: list[str], months: int, focus: str, investigation_depth: int,
                    rationale: str) -> str:
        """Submit the plan for this run.

        Args:
            datasets: subset of ['food', 'rent', 'energy', 'mobility', 'cpi'] (cpi is always added)
            months: months of history to collect (13-60; >= 13 needed for year-over-year rates)
            focus: short description of what this run should focus on
            investigation_depth: max drill-down steps the analyst may use (0-4)
            rationale: why this plan fits the trigger, goal and memory
        """
        return ft.submit_plan(datasets, months, focus, investigation_depth, rationale)

    @tool
    def fetch_from_source(dataset: str, source: str) -> dict:
        """Fetch one pending dataset from one source. Stores a raw snapshot (provenance).

        Args:
            dataset: 'food', 'rent', 'energy', 'mobility' or 'cpi'
            source: source name from list_sources
        """
        return ft.fetch(dataset, source)

    @tool
    def submit_decision(dataset: str, decision: str, reason: str) -> str:
        """Decide about a collected dataset.

        Args:
            dataset: dataset name
            decision: 'accept', 'retry' (alternative source), 'exclude' or 'escalate' (human review)
            reason: short justification
        """
        return ft.decide(dataset, decision, reason)

    @tool
    def get_results() -> dict:
        """Deterministic calculation results: essential vs CPI YoY, deviation, per-category contribution
        (contribution_pp) and gap to CPI (gap_pp), excluded categories, sources, demo flag."""
        return ft.results()

    @tool
    def investigate(level: str, category: str = "", region_type: str = "bundesland") -> dict:
        """Drill down into the deviation (costs one investigation step).

        Args:
            level: 'category' (gap per category), 'item' (YoY per item of `category`) or
                   'region' (strongest / weakest regional rent increases)
            category: category for level 'item'
            region_type: 'bundesland' or 'stadt' for level 'region'
        """
        return ft.investigate(level, category, region_type)

    @tool
    def request_more_data(datasets: list[str], reason: str, months: int = 0) -> str:
        """Ask the planner to re-plan and re-collect data (limited budget).

        Args:
            datasets: datasets to re-collect
            reason: why the current data is insufficient
            months: optional new history length (0 = unchanged)
        """
        return ft.request_more_data(datasets, reason, months)

    @tool
    def submit_analysis(summary: str, drivers: list[str], confidence: float) -> str:
        """Store the analysis.

        Args:
            summary: 2-4 sentences interpreting the result
            drivers: main drivers of the deviation, most important first
            confidence: your confidence in the analysis (0-1)
        """
        return ft.submit_analysis(summary, drivers, confidence)

    @tool
    def submit_report(markdown: str, outputs: list[str], confidence: float) -> str:
        """Store the final report.

        Args:
            markdown: the report in Markdown (numbers only from get_results / analysis)
            outputs: channels from ['chat', 'dashboard', 'pdf', 'alert']
            confidence: your confidence that the report is correct and well supported (0-1)
        """
        return ft.submit_report(markdown, outputs, confidence)

    return {
        "planner": [get_run_state, get_memory, list_sources, submit_plan],
        "collector": [get_run_state, list_sources, fetch_from_source],
        "validator": [get_run_state, submit_decision],
        "analyst": [get_results, investigate, request_more_data, submit_analysis],
        "reporter": [get_run_state, get_results, submit_report],
    }
