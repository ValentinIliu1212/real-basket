"""Deterministic graph steps (no LLM): gates, quality checks, human review, calculation, release, publish."""

from __future__ import annotations

import json
from pathlib import Path

from real_basket.agents.prompts import DISCLAIMER
from real_basket.core.engine import compute_results, missing_for_basket
from real_basket.core.store import DataStore
from real_basket.core.validation import validate_rows
from real_basket.flow.context import RunContext
from real_basket.schemas.flow import AuditEvent, DatasetStatus, Decision, RunStatus

DEMO_NOTICE = ("**Demo data:** all prices and CPI values of this run are synthetic demo values, "
               "not official statistics.")


def plan_gate(ctx: RunContext) -> str:
    ctx.ensure_plan()
    pending = ctx.with_status(DatasetStatus.PENDING)
    return f"Plan: {ctx.plan.model_dump()}. Datasets to collect: {pending or 'none'}."


def quality_checks(ctx: RunContext) -> str:
    lines = []
    for d in ctx.with_status(DatasetStatus.PENDING):   # collector did not deliver -> counts as attempt
        ctx.attempts[d] = ctx.attempts.get(d, 0) + 1
        if ctx.attempts[d] >= ctx.settings.MAX_SOURCE_ATTEMPTS:
            ctx.status[d] = DatasetStatus.ESCALATED
            ctx.log("guardrail", "not_collected_escalated", dataset=d, attempts=ctx.attempts[d])
        else:
            ctx.log("guardrail", "not_collected", dataset=d, attempts=ctx.attempts[d])
        lines.append(f"- {d}: NOT collected in this round (attempt {ctx.attempts[d]})")
    expected = ctx.expected_periods()
    for d in ctx.with_status(DatasetStatus.COLLECTED):
        report = validate_rows(d, ctx.candidates[d], expected)
        ctx.reports[d] = report
        ctx.log("quality_checks", "checked", dataset=d, source=report.source, score=report.score,
                issues=[i.model_dump() for i in report.issues])
        issues = "; ".join(f"[{i.severity.value}] {i.message}" for i in report.issues) or "no issues"
        lines.append(f"- {d} (source {report.source or 'MISSING'}, attempt {ctx.attempts[d]}, "
                     f"score {report.score}): {issues}")
    return "Quality check results:\n" + "\n".join(lines)


def validation_gate(ctx: RunContext) -> str:
    """Datasets the validator left undecided get a rule-based decision."""
    for d in ctx.with_status(DatasetStatus.COLLECTED):
        decision = Decision.RETRY if ctx.reports[d].has_critical else Decision.ACCEPT
        ctx.apply_decision(d, decision, "no decision by validator - rule-based default", actor="guardrail")
    return "Dataset status: " + ", ".join(f"{d}={s.value}" for d, s in ctx.status.items())


def human_review(ctx: RunContext) -> str:
    lines = []
    for d in ctx.with_status(DatasetStatus.ESCALATED):
        report = ctx.reports.get(d)
        answer = ctx.approver("data", {"run_id": ctx.run_id, "dataset": d,
                                       "report": report.model_dump() if report else None,
                                       "decisions": ctx.decisions.get(d, [])})
        if answer == "accept" and d in ctx.candidates:
            ctx.status[d] = DatasetStatus.ACCEPTED
            ctx.accepted[d] = ctx.candidates[d]
            ctx.human_overrides.append(d)
        else:
            ctx.status[d], answer = DatasetStatus.EXCLUDED, "exclude"
        ctx.log("human", "data_review", dataset=d, decision=answer)
        lines.append(f"- {d}: human decided '{answer}'")
    return "Human review:\n" + "\n".join(lines)


def calculate(ctx: RunContext) -> str:
    # Completeness rule: a dataset lost in this run (excluded / human-excluded) is replaced by the last
    # validated stored data if possible (fallback -> human approval required); otherwise no index.
    for d in ctx.with_status(DatasetStatus.EXCLUDED):
        ctx.reuse_dataset(d, "fallback")
    missing = missing_for_basket(ctx.with_status(DatasetStatus.ACCEPTED), ctx.weights)
    if missing:
        ctx.results = None
        ctx.calc_error = (f"Incomplete basket: no validated data for {missing} (fresh fetch failed and no "
                          "usable stored data). The essential index is only defined for the complete basket.")
        ctx.log("calculation_engine", "refused_incomplete_basket", missing=missing)
        return f"Calculation not possible: {ctx.calc_error}"
    rows = [r for d in ctx.with_status(DatasetStatus.ACCEPTED) for r in ctx.accepted[d]]
    try:
        h = ctx.store.save_dataset(ctx.run_id, rows, ctx.weights)
        ctx.results = compute_results(rows, ctx.weights)
        ctx.calc_error = None
        ctx.log("calculation_engine", "computed", dataset_hash=h, **{k: ctx.results[k] for k in (
            "essential_yoy_pct", "cpi_yoy_pct", "deviation_pp", "excluded_categories")})
        return f"Calculation results (deterministic, dataset hash {h}): {ctx.results}"
    except ValueError as exc:
        ctx.results, ctx.calc_error = None, str(exc)
        ctx.log("calculation_engine", "failed", error=str(exc))
        return f"Calculation not possible: {exc}"


def fallback_report(ctx: RunContext) -> str:
    r = ctx.results
    if not r:
        return f"# RealBasket run {ctx.run_id}\n\nNo index could be calculated: {ctx.calc_error}."
    return (f"# RealBasket – essential inflation {r['period']}\n\n"
            f"Essential inflation {r['essential_yoy_pct']:.2f} % vs. official CPI {r['cpi_yoy_pct']:.2f} % "
            f"→ deviation {r['deviation_pp']:+.2f} pp.")


def final_markdown(ctx: RunContext) -> str:
    body = (ctx.report or {}).get("markdown") or fallback_report(ctx)
    r = ctx.results or {}
    parts = [body.strip()]
    if r.get("demo_data", True):
        parts.append(DEMO_NOTICE)
    datasets = ", ".join(f"{d}: {s.value}" for d, s in ctx.status.items())
    reused = "; ".join(
        f"{d} from run {r['from_run']} ({r['reason']}"
        + (f", last {r['carried_forward_months']} month(s) carried forward" if r["carried_forward_months"] else "")
        + ")" for d, r in ctx.reused.items())
    parts.append("---\n**Provenance** · run `{}` · confidence {} · dataset hash `{}` · sources: {} · datasets: {}{}{}"
                 .format(ctx.run_id, ctx.compute_confidence(), r.get("dataset_hash", "-"),
                         ", ".join(r.get("sources", [])) or "-", datasets,
                         f" · re-used stored data: {reused}" if reused else "",
                         f" · human overrides: {', '.join(ctx.human_overrides)}" if ctx.human_overrides else ""))
    parts.append(f"*{DISCLAIMER}*")
    return "\n\n".join(parts)


def release_gate(ctx: RunContext) -> str:
    if ctx.report is None:
        ctx.report = {"markdown": fallback_report(ctx), "outputs": ["chat"], "confidence": 0.5}
        ctx.log("guardrail", "fallback_report", reason="reporter submitted no report")
    ctx.report["final_markdown"] = final_markdown(ctx)
    ctx.confidence = ctx.compute_confidence()
    if not ctx.results:
        ctx.approved, ctx.run_status = False, RunStatus.FAILED
        ctx.log("guardrail", "not_released", reason=ctx.calc_error)
        return "Not released: no results."
    fallbacks = ctx.fallbacks()
    if ctx.confidence >= ctx.settings.CONFIDENCE_THRESHOLD and not fallbacks:
        ctx.approved = True
        ctx.log("guardrail", "auto_released", confidence=ctx.confidence)
        return f"Released automatically (confidence {ctx.confidence})."
    reason = (f"stored data replaces lost fresh data for {fallbacks}" if fallbacks
              else f"confidence {ctx.confidence} below {ctx.settings.CONFIDENCE_THRESHOLD}")
    ctx.approval_reason = reason
    answer = ctx.approver("publish", {"run_id": ctx.run_id, "confidence": ctx.confidence, "reason": reason,
                                      "markdown": ctx.report["final_markdown"]})
    ctx.approved = answer
    ctx.run_status = {True: RunStatus.RUNNING, False: RunStatus.REJECTED}.get(answer, RunStatus.PENDING_APPROVAL)
    ctx.log("human", "publish_review", confidence=ctx.confidence, reason=reason, decision=str(answer))
    return f"Human approval required ({reason}); human decision: {answer}."


def publish(ctx: RunContext) -> str:
    ctx.save()
    files = publish_run(ctx.store, ctx.run_id)
    record = ctx.store.load_run(ctx.run_id)
    ctx.published_files, ctx.run_status = files, RunStatus(record["status"])
    ctx.log("publisher", "published", files=files, outputs=ctx.report.get("outputs", []))
    return f"Published: {files}"


def publish_run(store: DataStore, run_id: str, approved_by: str | None = None) -> list[str]:
    """Write the outputs chosen by the reporter. Also used by the UI to release pending runs."""
    record = store.load_run(run_id)
    report = record["report"] or {}
    md = report.get("final_markdown", "")
    files = [str(store.write_text(run_id, "report.md", md))]
    outputs = report.get("outputs", [])
    if "pdf" in outputs:
        files.append(str(_write_pdf(store.run_dir(run_id) / "report.pdf", md)))
    if "alert" in outputs:
        alert = {"run_id": run_id, "results": record.get("results"), "summary": (record.get("analysis") or {})}
        files.append(str(store.write_text(run_id, "alert.json", json.dumps(alert, ensure_ascii=False, indent=2))))
    record.update(status=RunStatus.PUBLISHED.value, approved=True, published_files=files)
    if approved_by:
        record["approved_by"] = approved_by
        store.append_audit(run_id, AuditEvent(actor="human", action="approved",
                                              detail={"by": approved_by, "files": files}))
    store.save_run(run_id, record)
    return files


def reject_run(store: DataStore, run_id: str, rejected_by: str, reason: str = "") -> None:
    """Human rejects a pending run: nothing is published, the decision is audited."""
    record = store.load_run(run_id)
    record.update(status=RunStatus.REJECTED.value, approved=False, rejected_by=rejected_by)
    store.save_run(run_id, record)
    store.append_audit(run_id, AuditEvent(actor="human", action="rejected",
                                          detail={"by": rejected_by, "reason": reason}))


def _write_pdf(path: Path, markdown: str) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    story = []
    for line in markdown.splitlines():
        text = line.strip().replace("**", "").replace("`", "").replace("*", "")
        if not text or text == "---":
            story.append(Spacer(1, 6))
            continue
        style = styles["Heading1"] if text.startswith("# ") else styles["Heading2"] if text.startswith("#") \
            else styles["BodyText"]
        text = text.lstrip("#- ").replace("&", "&amp;").replace("<", "&lt;")
        story.append(Paragraph(("• " if line.strip().startswith("- ") else "") + text, style))
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return path
