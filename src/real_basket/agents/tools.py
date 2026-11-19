"""Strands tools used by the RealBasket agents.

All figures are real data parsed deterministically from the reference PDFs (reports/real-data, ECLI model
calculation: Destatis EVS 2023 expenditure + official price indices, VPI; immowelt city rents) and re-checked in
code. There is no synthetic data: if the PDFs are unavailable, every tool returns an `error` instead of numbers.

Not contained in the sources (and therefore not offered): rents per federal state and net salaries.
"""

from __future__ import annotations

from strands import tool

from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.data.basket import Basket, RealDataError, load_basket
from real_basket.schemas.models import CATEGORY_LABEL_DE, BasketWeights, Category


def _last_months(points: list, months: int) -> list:
    keep = set(sorted({p.period for p in points})[-max(months, 1):])
    return [p for p in points if p.period in keep]


def _basket() -> tuple[Basket | None, dict | None]:
    try:
        return load_basket(), None
    except (RealDataError, OSError, ValueError) as exc:
        return None, {"error": f"Echte Daten nicht verfügbar (Referenz-PDFs in reports/real-data): {exc}"}


def _basket_info(basket: Basket) -> dict:
    return {"data_basis": basket.label, "documents": basket.real.documents,
            "checks_passed": f"{sum(c.ok for c in basket.real.checks)}/{len(basket.real.checks)}",
            "categories": {c.value: CATEGORY_LABEL_DE[c] for c in basket.categories}}


def _parse_category(basket: Basket, category: str) -> Category | None:
    try:
        cat = Category(category.lower().strip())
    except ValueError:
        return None
    return cat if cat in basket.categories else None


def _category_error(basket: Basket) -> dict:
    return {"error": f"category must be one of {[c.value for c in basket.categories]}", **_basket_info(basket)}


@tool
def fetch_regional_rents(region_type: str = "stadt") -> dict:
    """Fetch regional rents from the reference PDFs.

    - 'stadt': published asking rents (net cold, EUR/m2, immowelt) of the 15 largest German cities, January vs.
      October 2026, incl. the rent of a 75 m2 flat and the change in percent.
    - 'bundesland': coverage per federal state. The sources contain NO rent per federal state; for each state
      the cities with published rents are listed (city values are not representative for the state).
    - 'all': both.

    Args:
        region_type: 'stadt', 'bundesland' or 'all'
    """
    from real_basket.core.investigation import STATE_NOTE, state_rent_coverage

    basket, err = _basket()
    if err:
        return err
    region_type = region_type.lower().strip()
    if region_type not in ("stadt", "bundesland", "all"):
        return {"error": "region_type must be 'stadt', 'bundesland' or 'all'"}
    ds = basket.real
    result: dict = {"data_basis": basket.label}
    if region_type in ("stadt", "all"):
        result["cities"] = sorted(({
            "region": c["city"], "bundesland": c["state"], "period": "2026-10",
            "rent_eur_per_m2": c["rent_oct_eur_m2"], "rent_jan_2026_eur_per_m2": c["rent_jan_eur_m2"],
            "rent_75m2_eur": c["rent_oct_flat_eur"], "change_pct": c["change_pct"], "change_since": "2026-01",
            "source": c["source"]} for c in ds.city_rents), key=lambda r: -r["rent_eur_per_m2"])
    if region_type in ("bundesland", "all"):
        result["states"] = state_rent_coverage(ds)
        result["state_note"] = STATE_NOTE
    return result


@tool
def fetch_prices(category: str, months: int = 24) -> dict:
    """Fetch the modelled monthly costs (EUR per month) of one expenditure group of the reference basket.

    Args:
        category: 'food', 'housing_energy', 'mobility', 'health' or 'communication'
        months: number of recent months (default 24)

    Returns:
        Price points with item, period, price, unit and source (file and page).
    """
    basket, err = _basket()
    if err:
        return err
    cat = _parse_category(basket, category)
    if cat is None:
        return _category_error(basket)
    prices = _last_months([p for p in basket.prices if p.category == cat], months)
    return {**_basket_info(basket), "category": cat.value, "prices": [p.model_dump(mode="json") for p in prices]}


@tool
def fetch_official_cpi(months: int = 24) -> dict:
    """Fetch the official Consumer Price Index (VPI, Destatis), rebased to November 2024 = 100.

    Args:
        months: number of recent months (default 24)
    """
    basket, err = _basket()
    if err:
        return err
    return {**_basket_info(basket), "cpi": [c.model_dump(mode="json") for c in _last_months(basket.cpi, months)]}


@tool
def investigate_deviation(level: str = "category", category: str = "", region_type: str = "stadt",
                          months: int = 24) -> dict:
    """Drill down into why essential inflation deviates from the CPI (deterministic, latest month).

    Args:
        level: 'category' (contribution and gap to CPI per group in pp), 'item' (YoY per item of `category`) or
               'region' (city rents with strongest / weakest increase; 'bundesland' returns the coverage only)
        category: an expenditure group (for level 'item')
        region_type: 'stadt' or 'bundesland' (for level 'region')
        months: months of history (>= 13)
    """
    from real_basket.core.investigation import deviation_breakdown, item_changes, regional_rent_changes

    basket, err = _basket()
    if err:
        return err
    months = max(months, 13)
    level = level.lower()
    if level == "region":
        if region_type.lower() not in ("stadt", "bundesland"):
            return {"error": "region_type must be 'stadt' or 'bundesland'"}
        return {**regional_rent_changes(basket.real, region_type.lower()), "data_basis": basket.label}
    prices = _last_months(basket.prices, months)
    if level == "item":
        cat = _parse_category(basket, category)
        if cat is None:
            return _category_error(basket)
        return {**_basket_info(basket), "category": cat.value, "items": item_changes(prices, cat.value)}
    return {**deviation_breakdown(prices, _last_months(basket.cpi, months), basket.weights), **_basket_info(basket)}


@tool
def search_methodology(query: str, year: int = 0) -> dict:
    """Search method notes and caveats in the reference documents (German PDF reports on the ECLI model
    calculation). Returns passages with file, page and section. Use for methodological questions, e.g. what
    'Wohnen / Energie' contains, modelled vs. measured data, which federal states have verified rent series.
    Never take figures from the passages.

    Args:
        query: search terms; German keywords work best (e.g. 'Nettokaltmiete Wohnen Energie')
        year: only documents of this year (0 = all)
    """
    from real_basket.knowledge import KnowledgeBase

    try:
        res = KnowledgeBase().search(query, year=year or None)
    except Exception as exc:  # noqa: BLE001 - the chat must keep working without documents
        return {"error": f"Method-note search failed: {exc}"}
    return {"query": query, "retriever": res["retriever"], "note": res["note"],
            "passages": [{"cite": f"{p['source']} p. {p['page']}",
                          **{k: p[k] for k in ("section", "text", "also_in")}} for p in res["passages"]]}


@tool
def calculate_essential_vs_cpi(weights: dict[str, float] | None = None, months: int = 24) -> dict:
    """Calculate the weighted essential living cost index and compare it with the official CPI (VPI).

    Args:
        weights: optional weights per expenditure group, e.g. {"food": 0.3, "housing_energy": 0.5,
                 "mobility": 0.2}; normalised to 1. Omit to use the expenditure shares of the ECLI reference
                 basket (default).
        months: number of recent months (>= 13, default 24)

    Returns:
        Latest YoY rates (percent), deviation in percentage points, YoY per group, weights and data basis.
    """
    basket, err = _basket()
    if err:
        return err
    if weights:
        parsed: dict[Category, float] = {}
        for key, value in weights.items():
            cat = _parse_category(basket, key)
            if cat is None:
                return _category_error(basket)
            parsed[cat] = max(float(value), 0.0)
        total = sum(parsed.values())
        if total <= 0:
            return {"error": "weights must sum to a positive number", **_basket_info(basket)}
        w = BasketWeights(weights={c: v / total for c, v in parsed.items()})
    else:
        w = basket.weights
    months = max(months, 13)
    prices = _last_months(basket.prices, months)
    comparison = compare_with_cpi(essential_index(prices, w), _last_months(basket.cpi, months)).dropna()
    if comparison.empty:
        return {"error": "not enough months for a year-over-year comparison", **_basket_info(basket)}
    cats = category_indices(prices)
    latest = comparison.iloc[-1]
    return {
        "period": str(comparison.index[-1].date()),
        "essential_yoy_pct": round(float(latest["essential_yoy_pct"]), 2),
        "cpi_yoy_pct": round(float(latest["cpi_yoy_pct"]), 2),
        "deviation_pp": round(float(latest["deviation_pp"]), 2),
        "category_yoy_pct": {c: round(float(v), 2) for c, v in (cats.pct_change(12).iloc[-1] * 100).items()},
        "weights": {k.value: round(v, 4) for k, v in w.weights.items()},
        **_basket_info(basket),
    }