from datetime import date

from real_basket.agents.tools import fetch_regional_rents
from real_basket.data.demo_data import CITY_RENTS, STATE_RENTS, demo_regional_rents
from real_basket.schemas.models import RegionType


def test_all_states_and_cities_present():
    rents = demo_regional_rents(start=date(2025, 1, 1), months=12)
    states = {p.region for p in rents if p.region_type == RegionType.STATE}
    cities = {p.region for p in rents if p.region_type == RegionType.CITY}
    assert len(states) == 16 and states == set(STATE_RENTS)
    assert len(cities) == 15 and cities == set(CITY_RENTS)
    assert all(p.unit == "EUR/m²" for p in rents)


def test_regional_rents_tool_filters_by_type():
    result = fetch_regional_rents._tool_func(region_type="stadt")
    assert len(result) == 15
    assert result[0]["region"] == "München"
