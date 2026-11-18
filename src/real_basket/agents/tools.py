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
from real_basket.data.demo_data import demo_cpi, demo_prices, demo_regional_rents
from real_basket.schemas.models import BasketWeights, Category, RegionType


@tool
def fetch_regional_rents(region_type: str = "all", months: int = 13) -> list[dict]:
    """Fetch rent per m2 (net cold, EUR) per German federal state ('bundesland') and/or for the
    largest German cities ('stadt').

    Args:
        region_type: 'bundesland', 'stadt' or 'all'
        months: months of history used for the year-over-year change (default 13)

    Returns:
        One entry per region with latest rent per m2, YoY change in percent and source.
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
