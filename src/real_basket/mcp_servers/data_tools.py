"""Area `data` of the MCP server `realbasket`: reference basket, prices, VPI, index calculation and data checks.

Tools:     get_basket · get_prices · get_cpi · calculate_index · data_checks
Resources: basket://weights · basket://checks
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from real_basket.core.index import category_indices, compare_with_cpi, essential_index, yoy_pct
from real_basket.core.investigation import item_changes
from real_basket.mcp_servers.common import (
    basket_info,
    basket_or_error,
    category_error,
    last_months,
    parse_category,
)
from real_basket.schemas.models import BasketWeights, Category

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = ("data: real data of the essential basket (ECLI model calculation, Destatis EVS 2023 + VPI) parsed "
                "deterministically from the reference PDFs. Never calculate rates yourself; each result names its "
                "data basis, source documents and checks.")


def get_basket() -> dict:
    """Describe the reference basket: data basis, source documents, expenditure groups, default weights
    (expenditure shares) and how many data checks passed."""
    basket, err = basket_or_error()
    if err:
        return err
    return {**basket_info(basket), "weights": {k.value: round(v, 4) for k, v in basket.weights.weights.items()},
            "periods": [f"{p:%Y-%m}" for p in (basket.real.periods[0], basket.real.periods[-1])]}


def get_prices(category: str, months: int = 24) -> dict:
    """Fetch the modelled monthly costs (EUR per month) of one expenditure group of the reference basket.

    Args:
        category: 'food', 'housing_energy', 'mobility', 'health' or 'communication'
        months: number of recent months (default 24)

    Returns:
        Price points with item, period, price, unit and source (file and page), plus a deterministic `summary`
        per item (first / last value of the window, change in percent, YoY of the latest month) - quote these
        numbers instead of calculating changes yourself.
    """
    basket, err = basket_or_error()
    if err:
        return err
    cat = parse_category(basket, category)
    if cat is None:
        return category_error(basket)
    all_points = [p for p in basket.prices if p.category == cat]
    prices = last_months(all_points, months)
    yoy = {i["item"]: i["yoy_pct"] for i in item_changes(all_points, cat.value)}
    summary = []
    for item in sorted({p.item for p in prices}):
        series = sorted((p for p in prices if p.item == item), key=lambda p: p.period)
        first, last = series[0], series[-1]
        summary.append({"item": item, "unit": last.unit, "first_period": f"{first.period:%Y-%m}",
                        "first_value": first.price, "last_period": f"{last.period:%Y-%m}", "last_value": last.price,
                        "change_pct": round((last.price / first.price - 1) * 100, 2),
                        "yoy_pct_latest": yoy.get(item)})
    return {**basket_info(basket), "category": cat.value, "summary": summary,
            "prices": [p.model_dump(mode="json") for p in prices]}


def get_cpi(months: int = 24) -> dict:
    """Fetch the official Consumer Price Index (VPI, Destatis), rebased to November 2024 = 100.

    Args:
        months: number of recent months (default 24)
    """
    basket, err = basket_or_error()
    if err:
        return err
    return {**basket_info(basket), "cpi": [c.model_dump(mode="json") for c in last_months(basket.cpi, months)]}


def calculate_index(weights: dict[str, float] | None = None, months: int = 24) -> dict:
    """Calculate the weighted essential living cost index and compare it with the official CPI (VPI).

    Args:
        weights: optional weights per expenditure group, e.g. {"food": 0.3, "housing_energy": 0.5,
                 "mobility": 0.2}; normalised to 1. Groups that are omitted get weight 0 and are listed in
                 `excluded_categories`. Omit `weights` to use the expenditure shares of the ECLI reference
                 basket (default).
        months: number of recent months returned in `history` (default 24). The index itself is always based on
                the first month of the data (11/2024 = 100), so the latest rates do not depend on `months`.

    Returns:
        Latest YoY rates (percent), deviation in percentage points, YoY per group, weights, excluded groups,
        monthly `history` of the rates and the data basis.
    """
    basket, err = basket_or_error()
    if err:
        return err
    if weights:
        parsed: dict[Category, float] = {}
        for key, value in weights.items():
            cat = parse_category(basket, key)
            if cat is None:
                return category_error(basket)
            parsed[cat] = max(float(value), 0.0)
        total = sum(parsed.values())
        if total <= 0:
            return {"error": "weights must sum to a positive number", **basket_info(basket)}
        w = BasketWeights(weights={c: v / total for c, v in parsed.items()})
    else:
        w = basket.weights
    # full series: the base period (11/2024) fixes the effective weights; slicing happens afterwards
    comparison = compare_with_cpi(essential_index(basket.prices, w), basket.cpi).dropna()
    if comparison.empty:
        return {"error": "not enough months for a year-over-year comparison", **basket_info(basket)}
    cats = category_indices(basket.prices)
    latest = comparison.iloc[-1]
    history = comparison.tail(max(months, 1))
    return {
        "period": str(comparison.index[-1].date()),
        "base_period": f"{basket.real.periods[0]:%Y-%m} = 100",
        "essential_yoy_pct": round(float(latest["essential_yoy_pct"]), 2),
        "cpi_yoy_pct": round(float(latest["cpi_yoy_pct"]), 2),
        "deviation_pp": round(float(latest["deviation_pp"]), 2),
        "deviation_note": "deviation_pp is computed from the unrounded rates; quote it as returned",
        "category_yoy_pct": {c: round(float(v), 2) for c, v in yoy_pct(cats).iloc[-1].items()},
        "weights": {k.value: round(v, 4) for k, v in w.weights.items() if v > 0},
        "excluded_categories": [c.value for c in basket.categories if w.weights.get(c, 0.0) <= 0],
        "history": [{"period": f"{p:%Y-%m}", "essential_yoy_pct": round(float(r["essential_yoy_pct"]), 2),
                     "cpi_yoy_pct": round(float(r["cpi_yoy_pct"]), 2),
                     "deviation_pp": round(float(r["deviation_pp"]), 2)} for p, r in history.iterrows()],
        **basket_info(basket),
    }


def data_checks() -> dict:
    """Results of the deterministic re-checks of the PDF import (sums, gaps, printed ECLI and yearly rates
    recomputed, VPI, city rents, state coverage)."""
    basket, err = basket_or_error()
    if err:
        return err
    checks = [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in basket.real.checks]
    return {**basket_info(basket), "all_ok": all(c["ok"] for c in checks), "checks": checks}


def weights_resource() -> str:
    basket, err = basket_or_error()
    return json.dumps(err or {k.value: v for k, v in basket.weights.weights.items()}, ensure_ascii=False)


def checks_resource() -> str:
    return json.dumps(data_checks(), ensure_ascii=False)


TOOLS = (get_basket, get_prices, get_cpi, calculate_index, data_checks)


def register(server: MCPServer) -> None:
    for fn in TOOLS:
        server.tool()(fn)
    server.resource("basket://weights", name="basket-weights", mime_type="application/json",
                    description="Default weights (expenditure shares) of the reference basket")(weights_resource)
    server.resource("basket://checks", name="basket-checks", mime_type="application/json",
                    description="Results of the re-checks of the reference PDF import")(checks_resource)
