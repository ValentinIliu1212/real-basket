"""Area `analysis` of the MCP server `realbasket`: deviation drivers, drill-down and regional rents.

Tools: investigate_deviation · get_regional_rents

Not contained in the sources (and therefore not offered): rents per federal state and net salaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from real_basket.mcp_servers.common import basket_info, basket_or_error, category_error, parse_category

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = ("analysis: why essential inflation deviates from the VPI (contribution per group in percentage "
                "points, items, city rents) and the rent coverage per federal state. The sources contain no rent "
                "per federal state and no net salaries - never estimate them.")


def get_regional_rents(region_type: str = "stadt") -> dict:
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

    basket, err = basket_or_error()
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


LEVELS = ("category", "item", "region")


def investigate_deviation(level: str = "category", category: str = "", region_type: str = "stadt",
                          months: int = 24) -> dict:
    """Drill down into why essential inflation deviates from the CPI (deterministic, latest month).

    Args:
        level: 'category' (contribution and gap to CPI per group in pp), 'item' (YoY per item of `category`; the
               reference data has one item per group) or 'region' (city rents with strongest / weakest increase;
               'bundesland' returns the coverage only). Any other value returns an error.
        category: an expenditure group (for level 'item')
        region_type: 'stadt' or 'bundesland' (for level 'region')
        months: kept for compatibility; the result always refers to the latest month and the full series
                (base 11/2024 = 100), so it does not depend on `months`
    """
    from real_basket.core.investigation import deviation_breakdown, item_changes, regional_rent_changes

    basket, err = basket_or_error()
    if err:
        return err
    level = level.lower().strip()
    if level not in LEVELS:
        return {"error": f"level must be one of {list(LEVELS)}", **basket_info(basket)}
    if level == "region":
        if region_type.lower() not in ("stadt", "bundesland"):
            return {"error": "region_type must be 'stadt' or 'bundesland'"}
        return {**regional_rent_changes(basket.real, region_type.lower()), "data_basis": basket.label}
    if level == "item":
        cat = parse_category(basket, category)
        if cat is None:
            return category_error(basket)
        return {**basket_info(basket), "category": cat.value, "items": item_changes(basket.prices, cat.value)}
    # breakdown last: its `categories` (drivers per group) must not be overwritten by the labels of basket_info
    info = basket_info(basket)
    return {**info, "category_labels": info.pop("categories"),
            **deviation_breakdown(basket.prices, basket.cpi, basket.weights)}


TOOLS = (investigate_deviation, get_regional_rents)


def register(server: MCPServer) -> None:
    for fn in TOOLS:
        server.tool()(fn)
