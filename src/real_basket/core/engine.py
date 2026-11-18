"""Deterministic calculation engine of the monitoring flow (no LLM).

Takes the validated, stored dataset and returns reproducible numbers. Recomputing a stored run with
`compute_results` must always give identical results.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pandas as pd

from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.schemas.flow import CATEGORY_DATASETS, Row
from real_basket.schemas.models import BasketWeights, Category, CpiPoint, PricePoint

DEFAULT_WEIGHTS = {"food": 0.30, "rent": 0.40, "energy": 0.15, "mobility": 0.15}


def dataset_hash(rows: list[Row], weights: dict[str, float]) -> str:
    payload = json.dumps({"rows": sorted((r.model_dump() for r in rows),
                                         key=lambda d: (d["dataset"], d["item"], d["period"])),
                          "weights": weights}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def renormalise(weights: dict[str, float], available: list[str]) -> dict[str, float]:
    sub = {k: v for k, v in weights.items() if k in available and v > 0}
    total = sum(sub.values())
    if not total:
        raise ValueError("No weighted category available")
    return {k: v / total for k, v in sub.items()}


def missing_for_basket(datasets: set[str] | list[str], weights: dict[str, float] | None = None) -> list[str]:
    """Datasets still missing for a valid essential index: CPI + every category with weight > 0."""
    weights = weights or DEFAULT_WEIGHTS
    needed = [c for c in CATEGORY_DATASETS if weights.get(c, 0) > 0] + ["cpi"]
    return [d for d in needed if d not in set(datasets)]


def carry_forward(rows: list[Row], expected_periods: list[str], max_months: int) -> tuple[list[Row], int]:
    """Re-use stored rows for the expected periods; fill at most `max_months` trailing months per item
    with the last observed value (source marked '(carried forward)'). Returns (rows, filled months).
    Raises ValueError if the stored data has gaps, starts too late or is too stale."""
    expected = sorted(expected_periods)
    by_item: dict[str, list[Row]] = {}
    for r in rows:
        if r.period in expected:
            by_item.setdefault(r.item, []).append(r)
    if not by_item:
        raise ValueError("stored data does not cover the requested period")
    out: list[Row] = []
    filled = 0
    for item, item_rows in by_item.items():
        item_rows.sort(key=lambda r: r.period)
        have, last = {r.period for r in item_rows}, item_rows[-1].period
        if any(p not in have for p in expected if p <= last):
            raise ValueError(f"'{item}': stored data has gaps or starts after {expected[0]}")
        trailing = [p for p in expected if p > last]
        if len(trailing) > max_months:
            raise ValueError(f"'{item}': stored data ends {last}, {len(trailing)} months stale (max {max_months})")
        out += item_rows
        out += [item_rows[-1].model_copy(update={"period": p, "source": f"{item_rows[-1].source} (carried forward)"})
                for p in trailing]
        filled = max(filled, len(trailing))
    return out, filled


def compute_results(rows: list[Row], weights: dict[str, float] | None = None) -> dict:
    """Essential index vs CPI for the latest month, incl. exact contribution per category.

    The essential index is only defined for the complete basket: every category with weight > 0 and the
    CPI must be present, otherwise a ValueError is raised (no silent re-weighting).
    contribution_pp: share of the essential YoY rate caused by the category (sums to essential YoY).
    gap_pp: contribution minus the category's weight x CPI YoY (sums to the deviation).
    """
    weights = weights or DEFAULT_WEIGHTS
    available = sorted({r.dataset for r in rows if r.dataset in CATEGORY_DATASETS})
    cpi_rows = [r for r in rows if r.dataset == "cpi"]
    missing = missing_for_basket({r.dataset for r in rows}, weights)
    if missing:
        raise ValueError(f"Incomplete basket: no validated data for {missing}. The essential index is only "
                         "defined for the complete basket (no re-weighting).")

    used = renormalise(weights, available)
    prices = [PricePoint(category=Category(r.dataset), item=r.item, period=date.fromisoformat(r.period),
                         price=r.value, unit=r.unit, source=r.source)
              for r in rows if r.dataset in used]
    cpi = [CpiPoint(period=date.fromisoformat(r.period), index_value=r.value, source=r.source) for r in cpi_rows]

    comparison = compare_with_cpi(essential_index(prices, BasketWeights(weights=used)), cpi).dropna()
    if comparison.empty:
        raise ValueError("Not enough months for a year-over-year comparison (need >= 13)")
    latest, period = comparison.iloc[-1], comparison.index[-1]

    cats = category_indices(prices)
    prev_period = period - pd.DateOffset(months=12)
    ess = (cats * pd.Series(used)).sum(axis=1)
    cpi_yoy = float(latest["cpi_yoy_pct"])
    breakdown = {}
    for c, w in used.items():
        contrib = w * (cats.loc[period, c] - cats.loc[prev_period, c]) / ess.loc[prev_period] * 100
        breakdown[c] = {
            "weight": round(w, 4),
            "yoy_pct": round(float((cats.loc[period, c] / cats.loc[prev_period, c] - 1) * 100), 2),
            "contribution_pp": round(float(contrib), 2),
            "gap_pp": round(float(contrib - w * cpi_yoy), 2),
        }

    sources = sorted({r.source for r in rows})
    return {
        "period": str(period.date()),
        "essential_yoy_pct": round(float(latest["essential_yoy_pct"]), 2),
        "cpi_yoy_pct": round(cpi_yoy, 2),
        "deviation_pp": round(float(latest["deviation_pp"]), 2),
        "categories": breakdown,
        "weights_used": {k: round(v, 4) for k, v in used.items()},
        "excluded_categories": [c for c in CATEGORY_DATASETS if c not in used],   # only weight-0 categories
        "sources": sources,
        "demo_data": any(s.startswith("demo") for s in sources),
        "dataset_hash": dataset_hash(rows, weights),
    }
