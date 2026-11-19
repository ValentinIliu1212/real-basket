"""Deterministic drill-down used by the chat agent's `investigate_deviation` tool:
category -> item -> region. The agent decides *whether* and *how deep* to drill down; the numbers come from here."""

from __future__ import annotations

import pandas as pd

from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.data.demo_data import demo_regional_rents
from real_basket.schemas.models import BasketWeights, CpiPoint, PricePoint, RegionType


def deviation_breakdown(prices: list[PricePoint], cpi: list[CpiPoint], weights: BasketWeights | None = None) -> dict:
    """Essential index vs CPI for the latest month, incl. the exact contribution of every category.

    contribution_pp: share of the essential YoY rate caused by the category (sums to the essential YoY).
    gap_pp: contribution minus the category's weight x CPI YoY (sums to the deviation).
    Categories are sorted by |gap_pp|, i.e. the biggest driver of the deviation comes first.
    """
    weights = weights or BasketWeights()
    used = {c.value: w for c, w in weights.weights.items() if w > 0}
    comparison = compare_with_cpi(essential_index(prices, weights), cpi).dropna()
    if comparison.empty:
        raise ValueError("Not enough months for a year-over-year comparison (need >= 13)")
    latest, period = comparison.iloc[-1], comparison.index[-1]
    prev = period - pd.DateOffset(months=12)

    cats = category_indices(prices)
    missing = [c for c in used if c not in cats.columns]
    if missing:
        raise ValueError(f"No prices for categories {missing} in this basket")
    ess = (cats[list(used)] * pd.Series(used)).sum(axis=1)
    cpi_yoy = float(latest["cpi_yoy_pct"])
    categories = []
    for c, w in used.items():
        contrib = w * (cats.loc[period, c] - cats.loc[prev, c]) / ess.loc[prev] * 100
        categories.append({
            "category": c, "weight": round(w, 4),
            "yoy_pct": round(float((cats.loc[period, c] / cats.loc[prev, c] - 1) * 100), 2),
            "contribution_pp": round(float(contrib), 2),
            "gap_pp": round(float(contrib - w * cpi_yoy), 2),
        })
    return {
        "period": str(period.date()),
        "essential_yoy_pct": round(float(latest["essential_yoy_pct"]), 2),
        "cpi_yoy_pct": round(cpi_yoy, 2),
        "deviation_pp": round(float(latest["deviation_pp"]), 2),
        "categories": sorted(categories, key=lambda d: -abs(d["gap_pp"])),
    }


def item_changes(prices: list[PricePoint], category: str) -> list[dict]:
    """Year-over-year change of every item of one category at the latest month."""
    result = []
    for item in sorted({p.item for p in prices if p.category.value == category}):
        series = sorted((p for p in prices if p.category.value == category and p.item == item),
                        key=lambda p: p.period)
        if len(series) < 13:
            continue
        last, prev = series[-1], series[-13]
        result.append({"item": item, "period": str(last.period), "price": last.price, "unit": last.unit,
                       "yoy_pct": round((last.price / prev.price - 1) * 100, 2), "source": last.source})
    return sorted(result, key=lambda d: -abs(d["yoy_pct"]))


def real_city_rent_changes(top: int = 5) -> dict | None:
    """Published asking rents of the 15 largest cities (reference PDF, immowelt), Jan vs. Oct 2026; None if
    the reference PDFs are not available."""
    from real_basket.data.real_data import RealDataError, load_real_data

    try:
        cities = load_real_data().city_rents
    except (RealDataError, OSError, ValueError):
        return None
    if not cities:
        return None
    changes = sorted(({"region": c["city"], "bundesland": c["state"], "rent_eur_per_m2": c["rent_oct_eur_m2"],
                       "change_pct": c["change_pct"]} for c in cities), key=lambda d: -d["change_pct"])
    return {"region_type": "stadt", "change": "Okt 2026 vs. Jan 2026 (Angebotskaltmiete)",
            "strongest": changes[:top], "weakest": changes[-top:], "source": cities[0]["source"]}


def regional_rent_changes(region_type: str = "bundesland", months: int = 13, top: int = 5,
                          use_real: bool = True) -> dict:
    """Regions with the strongest / weakest rent increase. Cities: real asking rents from the reference PDF if
    available and `use_real`; federal states: demo data (the reference PDFs contain no verified state series)."""
    if use_real and region_type == RegionType.CITY.value and (real := real_city_rent_changes(top)):
        return real
    rents = demo_regional_rents(months=max(months, 13), region_type=RegionType(region_type))
    by_region: dict[str, list] = {}
    for p in rents:
        by_region.setdefault(p.region, []).append(p)
    changes = []
    for region, pts in by_region.items():
        pts.sort(key=lambda p: p.period)
        changes.append({"region": region, "rent_eur_per_m2": round(pts[-1].price, 2),
                        "change_pct": round((pts[-1].price / pts[-13].price - 1) * 100, 2)})
    changes.sort(key=lambda d: -d["change_pct"])
    return {"region_type": region_type, "change": "ggü. Vorjahresmonat", "strongest": changes[:top],
            "weakest": changes[-top:], "source": "demo"}
