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


def compute_results(rows: list[Row], weights: dict[str, float] | None = None) -> dict:
    """Essential index vs CPI for the latest month, incl. exact contribution per category.

    contribution_pp: share of the essential YoY rate caused by the category (sums to essential YoY).
    gap_pp: contribution minus the category's weight x CPI YoY (sums to the deviation).
    """
    weights = weights or DEFAULT_WEIGHTS
    available = sorted({r.dataset for r in rows if r.dataset in CATEGORY_DATASETS})
    cpi_rows = [r for r in rows if r.dataset == "cpi"]
    if not cpi_rows or not available:
        raise ValueError("Need the CPI and at least one essential category")

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
        "excluded_categories": [c for c in CATEGORY_DATASETS if c not in used],
        "sources": sources,
        "demo_data": any(s.startswith("demo") for s in sources),
        "dataset_hash": dataset_hash(rows, weights),
    }
