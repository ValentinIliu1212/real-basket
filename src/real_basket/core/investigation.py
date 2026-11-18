"""Deterministic drill-down used by the Analyst agent's investigation loop:
category -> item -> region. The agent decides *whether* and *how deep* to drill down."""

from __future__ import annotations

from datetime import date

from real_basket.data.demo_data import demo_regional_rents
from real_basket.data.sources import period_range
from real_basket.schemas.flow import Row
from real_basket.schemas.models import RegionType


def category_breakdown(results: dict) -> list[dict]:
    """Categories sorted by their contribution to the deviation from the CPI (gap_pp)."""
    return sorted(({"category": c, **v} for c, v in results["categories"].items()),
                  key=lambda d: -abs(d["gap_pp"]))


def item_changes(rows: list[Row], category: str) -> list[dict]:
    """Year-over-year change of every item of one category at the latest month."""
    result = []
    items = sorted({r.item for r in rows if r.dataset == category})
    for item in items:
        series = sorted((r for r in rows if r.dataset == category and r.item == item), key=lambda r: r.period)
        if len(series) < 13:
            continue
        last, prev = series[-1], series[-13]
        result.append({"item": item, "period": last.period, "price": last.value, "unit": last.unit,
                       "yoy_pct": round((last.value / prev.value - 1) * 100, 2), "source": last.source})
    return sorted(result, key=lambda d: -abs(d["yoy_pct"]))


def regional_rent_changes(region_type: str = "bundesland", months: int = 13, end: date | None = None,
                          top: int = 5) -> dict:
    """Regions with the strongest / weakest rent increase (YoY). Source: demo regional rents."""
    start, _ = period_range(max(months, 13), end)
    rents = demo_regional_rents(start, max(months, 13), RegionType(region_type))
    by_region: dict[str, list] = {}
    for p in rents:
        by_region.setdefault(p.region, []).append(p)
    changes = []
    for region, pts in by_region.items():
        pts.sort(key=lambda p: p.period)
        changes.append({"region": region, "rent_eur_per_m2": round(pts[-1].price, 2),
                        "yoy_pct": round((pts[-1].price / pts[-13].price - 1) * 100, 2)})
    changes.sort(key=lambda d: -d["yoy_pct"])
    return {"region_type": region_type, "strongest": changes[:top], "weakest": changes[-top:],
            "source": "demo"}
