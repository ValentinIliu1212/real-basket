"""Deterministic data quality checks. The Validator agent interprets the report and decides
(accept / retry / exclude / escalate); hard rules are enforced in code, not by the LLM."""

from __future__ import annotations

from collections import defaultdict

from real_basket.schemas.flow import Row, Severity, ValidationIssue, ValidationReport

# Month-over-month change per item considered implausible (critical) / suspicious (warning)
JUMP_LIMITS = {"cpi": (0.05, 0.015)}
DEFAULT_JUMP_LIMITS = (0.50, 0.15)


def validate_rows(dataset: str, rows: list[Row], expected_periods: list[str]) -> ValidationReport:
    issues: list[ValidationIssue] = []

    def add(check: str, severity: Severity, message: str) -> None:
        issues.append(ValidationIssue(check=check, severity=severity, message=message))

    source = rows[0].source if rows else ""
    if not rows:
        add("not_empty", Severity.CRITICAL, "Source returned no data")
        return ValidationReport(dataset=dataset, source=source, rows=0, score=0.0, issues=issues)

    missing_src = sum(1 for r in rows if not r.source)
    if missing_src:
        add("provenance", Severity.CRITICAL, f"{missing_src} rows without source (provenance missing)")

    non_pos = [r for r in rows if r.value <= 0]
    if non_pos:
        add("positive", Severity.CRITICAL, f"{len(non_pos)} non-positive values")

    by_item: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_item[r.item].append(r)

    critical_jump, warn_jump = JUMP_LIMITS.get(dataset, DEFAULT_JUMP_LIMITS)
    expected = set(expected_periods)
    for item, item_rows in by_item.items():
        item_rows.sort(key=lambda r: r.period)
        periods = {r.period for r in item_rows}
        gaps = sorted(expected - periods)
        if gaps:
            add("completeness", Severity.CRITICAL, f"'{item}': {len(gaps)} missing months ({', '.join(gaps[:4])})")
        if len({r.unit for r in item_rows}) > 1:
            add("units", Severity.CRITICAL, f"'{item}': mixed units {sorted({r.unit for r in item_rows})}")
        for prev, cur in zip(item_rows, item_rows[1:]):
            if prev.value <= 0:
                continue
            change = cur.value / prev.value - 1
            if abs(change) > critical_jump:
                add("plausibility", Severity.CRITICAL,
                    f"'{item}' {prev.period}->{cur.period}: {change:+.0%} month-over-month (unit error?)")
            elif abs(change) > warn_jump:
                add("plausibility", Severity.WARNING,
                    f"'{item}' {prev.period}->{cur.period}: {change:+.0%} month-over-month")

    n_crit = sum(i.severity == Severity.CRITICAL for i in issues)
    n_warn = len(issues) - n_crit
    score = max(0.0, 1.0 - 0.4 * n_crit - 0.1 * n_warn)
    return ValidationReport(dataset=dataset, source=source, rows=len(rows), score=round(score, 2), issues=issues)
