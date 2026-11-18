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
from real_basket.data.demo_data import demo_cpi, demo_prices
from real_basket.schemas.models import BasketWeights, Category


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
