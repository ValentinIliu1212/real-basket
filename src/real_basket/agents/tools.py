"""Strands tools used by the RealBasket agents.

TODO (hackathon): replace demo implementations with real collectors, e.g.
- food: supermarket price APIs / web scraping
- rent: rental portals, Mietspiegel data
- energy: Bundesnetzagentur / comparison portals
- mobility: fuel price API (Tankerkoenig), public transport tariffs
- CPI: Destatis GENESIS API (table 61111-0002) or Eurostat HICP
"""

from __future__ import annotations

from strands import tool

from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.data.demo_data import demo_cpi, demo_net_salaries, demo_prices, demo_regional_rents
from real_basket.schemas.models import BasketWeights, Category, RegionType


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
    largest German cities ('stadt').

    Args:
        region_type: 'bundesland', 'stadt' or 'all'
        months: months of history used for the year-over-year change (default 13)

    Returns:
        One entry per region with latest rent per m2, average rent per m2 over the period
        (avg_rent_eur_per_m2), YoY change in percent and source.
    """
    rtype = None if region_type.lower() == "all" else RegionType(region_type.lower())
    rents = demo_regional_rents(months=months, region_type=rtype)
    by_region: dict[tuple[str, str], list] = {}
    for p in rents:
        by_region.setdefault((p.region_type.value, p.region), []).append(p)
    result = []
    for (rt, region), pts in by_region.items():
        pts.sort(key=lambda p: p.period)
        first, last = pts[0], pts[-1]
        result.append({
            "region_type": rt, "region": region, "period": str(last.period),
            "rent_eur_per_m2": round(last.price, 2),
            "avg_rent_eur_per_m2": round(sum(p.price for p in pts) / len(pts), 2),
            "change_pct": round((last.price / first.price - 1) * 100, 2),
            "change_since": str(first.period), "source": last.source,
        })
    return sorted(result, key=lambda r: -r["rent_eur_per_m2"])


@tool
def fetch_prices(category: str, months: int = 24) -> list[dict]:
    """Fetch monthly prices for one essential living cost category.

    Args:
        category: one of 'food', 'rent', 'energy', 'mobility'
        months: number of months to fetch (default 24)

    Returns:
        List of price points with item, period, price, unit and source.
    """
    prices = demo_prices(months=months, category=Category(category.lower()))
    return [p.model_dump(mode="json") for p in prices]


@tool
def fetch_official_cpi(months: int = 24) -> list[dict]:
    """Fetch the official Consumer Price Index (CPI) monthly values.

    Args:
        months: number of months to fetch (default 24)
    """
    return [c.model_dump(mode="json") for c in demo_cpi(months=months)]


CLEAN_DEMO_SOURCES = {"food": "demo-price-comparison", "rent": "demo-mietspiegel",
                      "energy": "demo-bnetza-monitoring", "mobility": "demo-transport-tariffs",
                      "cpi": "demo-destatis"}


@tool
def investigate_deviation(level: str = "category", category: str = "", region_type: str = "bundesland",
                          months: int = 24) -> dict:
    """Drill down into why essential inflation deviates from the CPI (deterministic, latest month).

    Args:
        level: 'category' (contribution and gap to CPI per category in pp), 'item' (YoY per item of
               `category`) or 'region' (regional rents with strongest / weakest increase)
        category: 'food', 'rent', 'energy' or 'mobility' (for level 'item')
        region_type: 'bundesland' or 'stadt' (for level 'region')
        months: months of history (>= 13)
    """
    from real_basket.core.engine import compute_results
    from real_basket.core.investigation import category_breakdown, item_changes, regional_rent_changes
    from real_basket.data.sources import get_source

    months = max(months, 13)
    level = level.lower()
    if level == "region":
        return regional_rent_changes(region_type.lower(), months)
    rows = [r for name in CLEAN_DEMO_SOURCES.values() for r in get_source(name).fetch(months)]
    if level == "item":
        if category.lower() not in ("food", "rent", "energy", "mobility"):
            return {"error": "category must be food, rent, energy or mobility"}
        return {"category": category.lower(), "items": item_changes(rows, category.lower()), "source": "demo"}
    results = compute_results(rows)
    return {"period": results["period"], "deviation_pp": results["deviation_pp"],
            "categories": category_breakdown(results), "source": "demo"}


@tool
def run_monitoring_flow(goal: str) -> dict:
    """Start a full monitoring run (multi-agent flow: planning, source selection, validation loop,
    investigation, report, release gate). Slow; only use when the user explicitly asks for a fresh,
    validated run. Low-confidence reports wait for human approval in the dashboard.

    Args:
        goal: what the run should find out
    """
    from real_basket.flow.graph import run_flow
    from real_basket.schemas.flow import Trigger

    ctx = run_flow(goal, trigger=Trigger.QUESTION)
    return {"run_id": ctx.run_id, "status": ctx.run_status.value, "confidence": ctx.confidence,
            "path": ctx.path, "datasets": {d: s.value for d, s in ctx.status.items()},
            "report": (ctx.report or {}).get("final_markdown", "")}


@tool
def calculate_essential_vs_cpi(
    food_weight: float = 0.30,
    rent_weight: float = 0.40,
    energy_weight: float = 0.15,
    mobility_weight: float = 0.15,
    months: int = 24,
) -> dict:
    """Calculate the weighted essential living cost index and compare it with the official CPI.

    Weights must sum to 1.0. Returns latest YoY rates (percent), deviation in percentage points
    and the YoY change per category.
    """
    weights = BasketWeights(weights={
        Category.FOOD: food_weight, Category.RENT: rent_weight,
        Category.ENERGY: energy_weight, Category.MOBILITY: mobility_weight,
    })
    prices = demo_prices(months=months)
    comparison = compare_with_cpi(essential_index(prices, weights), demo_cpi(months=months))
    cats = category_indices(prices)
    latest = comparison.dropna().iloc[-1]
    return {
        "period": str(comparison.dropna().index[-1].date()),
        "essential_yoy_pct": round(float(latest["essential_yoy_pct"]), 2),
        "cpi_yoy_pct": round(float(latest["cpi_yoy_pct"]), 2),
        "deviation_pp": round(float(latest["deviation_pp"]), 2),
        "category_yoy_pct": {c: round(float(v), 2) for c, v in (cats.pct_change(12).iloc[-1] * 100).items()},
        "weights": {k.value: v for k, v in weights.weights.items()},
        "data_source": "demo",
    }
