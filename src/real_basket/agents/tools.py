"""Strands tools used by the RealBasket agents.

The essential basket comes from `data/basket.py`: real data parsed from the reference PDFs (reports/real-data,
ECLI model calculation, Destatis EVS 2023 + VPI) if available, otherwise synthetic demo data. Every result
carries `data_source` ('real' | 'demo') so the agent can say where the numbers come from.

Rents per federal state and net salaries are still demo data (the reference PDFs contain no verified state
series); rents of the 15 largest cities are real (immowelt, Jan vs. Oct 2026) when the PDFs are available.
"""

from __future__ import annotations

from strands import tool

from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.data.basket import Basket, load_basket
from real_basket.data.demo_data import demo_net_salaries, demo_regional_rents
from real_basket.schemas.models import CATEGORY_LABEL_DE, BasketWeights, Category, RegionType


def _last_months(points: list, months: int) -> list:
    keep = set(sorted({p.period for p in points})[-max(months, 1):])
    return [p for p in points if p.period in keep]


def _basket_info(basket: Basket) -> dict:
    return {"data_source": basket.source, "data_label": basket.label,
            "categories": {c.value: CATEGORY_LABEL_DE[c] for c in basket.categories}}


def _parse_category(basket: Basket, category: str) -> Category | None:
    try:
        cat = Category(category.lower().strip())
    except ValueError:
        return None
    return cat if cat in basket.categories else None


def _category_error(basket: Basket) -> dict:
    return {"error": f"category must be one of {[c.value for c in basket.categories]}", **_basket_info(basket)}


def _real_city_rents() -> list[dict] | None:
    basket = load_basket()
    if basket.real is None or not basket.real.city_rents:
        return None
    return [{"region_type": "stadt", "region": c["city"], "bundesland": c["state"], "period": "2026-10",
             "rent_eur_per_m2": c["rent_oct_eur_m2"], "rent_jan_2026_eur_per_m2": c["rent_jan_eur_m2"],
             "change_pct": c["change_pct"], "change_since": "2026-01", "source": c["source"],
             "data_source": "real"} for c in basket.real.city_rents]


@tool
def fetch_net_salaries(months: int = 12, flat_size_m2: float = 70) -> list[dict]:
    """Fetch the average monthly net salary (EUR, full-time) per German federal state (Bundesland)
    and the rent burden (net cold rent of a flat with `flat_size_m2` in percent of the net salary).

    Args:
        months: number of recent months to average over (default 12)
        flat_size_m2: flat size used for the rent burden (default 70 m2)
    """
    incomes = demo_net_salaries(months=months)
    rents = demo_regional_rents(months=months, region_type=RegionType.STATE)
    result = []
    for state in sorted({i.region for i in incomes}):
        sal = [i.net_salary for i in incomes if i.region == state]
        rent = [r.price for r in rents if r.region == state]
        avg_sal, avg_rent = sum(sal) / len(sal), sum(rent) / len(rent)
        result.append({
            "bundesland": state,
            "avg_net_salary_eur": round(avg_sal, 0),
            "avg_rent_eur_per_m2": round(avg_rent, 2),
            "rent_burden_pct": round(avg_rent * flat_size_m2 / avg_sal * 100, 1),
            "months_averaged": months, "source": "demo",
        })
    return sorted(result, key=lambda r: -r["avg_net_salary_eur"])


@tool
def fetch_regional_rents(region_type: str = "all", months: int = 13) -> list[dict]:
    """Fetch rent per m2 (net cold, EUR) per German federal state ('bundesland') and/or for the
    15 largest German cities ('stadt'). Cities: real asking rents (immowelt, Jan vs. Oct 2026) from the reference
    PDFs if available; federal states: demo data.

    Args:
        region_type: 'bundesland', 'stadt' or 'all'
        months: months of history used for the change of the demo series (default 13)

    Returns:
        One entry per region with latest rent per m2, change in percent, period, source and data_source.
    """
    region_type = region_type.lower()
    real_cities = _real_city_rents() if region_type in ("stadt", "all") else None
    rtype = None if region_type == "all" else RegionType(region_type)
    by_region: dict[tuple[str, str], list] = {}
    for p in demo_regional_rents(months=months, region_type=rtype):
        if real_cities and p.region_type == RegionType.CITY:
            continue
        by_region.setdefault((p.region_type.value, p.region), []).append(p)
    result = list(real_cities or [])
    for (rt, region), pts in by_region.items():
        pts.sort(key=lambda p: p.period)
        first, last = pts[0], pts[-1]
        result.append({
            "region_type": rt, "region": region, "period": str(last.period),
            "rent_eur_per_m2": round(last.price, 2),
            "avg_rent_eur_per_m2": round(sum(p.price for p in pts) / len(pts), 2),
            "change_pct": round((last.price / first.price - 1) * 100, 2),
            "change_since": str(first.period), "source": last.source, "data_source": "demo",
        })
    return sorted(result, key=lambda r: -r["rent_eur_per_m2"])


@tool
def fetch_prices(category: str, months: int = 24) -> dict:
    """Fetch monthly prices / modelled monthly costs (EUR) for one category of the essential basket.

    Args:
        category: a category of the current basket - real data: 'food', 'housing_energy', 'mobility',
                  'health', 'communication'; demo data: 'food', 'rent', 'energy', 'mobility'
        months: number of recent months (default 24)

    Returns:
        Price points with item, period, price, unit and source.
    """
    basket = load_basket()
    cat = _parse_category(basket, category)
    if cat is None:
        return _category_error(basket)
    prices = _last_months([p for p in basket.prices if p.category == cat], months)
    return {**_basket_info(basket), "category": cat.value, "prices": [p.model_dump(mode="json") for p in prices]}


@tool
def fetch_official_cpi(months: int = 24) -> dict:
    """Fetch the official Consumer Price Index (VPI, Destatis) monthly values of the current basket period.

    Args:
        months: number of recent months (default 24)
    """
    basket = load_basket()
    return {**_basket_info(basket), "cpi": [c.model_dump(mode="json") for c in _last_months(basket.cpi, months)]}


@tool
def investigate_deviation(level: str = "category", category: str = "", region_type: str = "bundesland",
                          months: int = 24) -> dict:
    """Drill down into why essential inflation deviates from the CPI (deterministic, latest month).

    Args:
        level: 'category' (contribution and gap to CPI per category in pp), 'item' (YoY per item of
               `category`) or 'region' (regional rents with strongest / weakest increase)
        category: a category of the current basket (for level 'item')
        region_type: 'bundesland' or 'stadt' (for level 'region')
        months: months of history (>= 13)
    """
    from real_basket.core.investigation import deviation_breakdown, item_changes, regional_rent_changes

    months = max(months, 13)
    level = level.lower()
    basket = load_basket()
    if level == "region":
        res = regional_rent_changes(region_type.lower(), months, use_real=basket.source == "real")
        return {**res, "data_source": "demo" if res.get("source") == "demo" else "real"}
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
        weights: optional weights per category of the current basket, e.g. {"food": 0.3, "housing_energy": 0.5,
                 "mobility": 0.2}; normalised to 1. Omit to use the default weights of the basket (real data:
                 expenditure shares of the ECLI reference basket).
        months: number of recent months (>= 13, default 24)

    Returns:
        Latest YoY rates (percent), deviation in percentage points, YoY per category, weights and data source.
    """
    basket = load_basket()
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
