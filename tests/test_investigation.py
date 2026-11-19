import pytest

from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.core.investigation import deviation_breakdown, item_changes, regional_rent_changes
from real_basket.data.demo_data import demo_cpi, demo_prices
from real_basket.schemas.models import BasketWeights, Category


def test_breakdown_gaps_add_up_to_the_deviation():
    res = deviation_breakdown(demo_prices(), demo_cpi())
    cats = res["categories"]
    assert {c["category"] for c in cats} == {"food", "rent", "energy", "mobility"}
    assert sum(c["contribution_pp"] for c in cats) == pytest.approx(res["essential_yoy_pct"], abs=0.05)
    assert sum(c["gap_pp"] for c in cats) == pytest.approx(res["deviation_pp"], abs=0.05)
    assert abs(cats[0]["gap_pp"]) == max(abs(c["gap_pp"]) for c in cats)     # biggest driver first


def test_breakdown_matches_index_for_custom_weights():
    w = BasketWeights(weights={Category.FOOD: 0.5, Category.RENT: 0.5, Category.ENERGY: 0, Category.MOBILITY: 0})
    res = deviation_breakdown(demo_prices(), demo_cpi(), w)
    latest = compare_with_cpi(essential_index(demo_prices(), w), demo_cpi()).dropna().iloc[-1]
    assert res["deviation_pp"] == pytest.approx(latest["deviation_pp"], abs=0.01)
    assert {c["category"] for c in res["categories"]} == {"food", "rent"}


def test_item_and_region_drill_down():
    items = item_changes(demo_prices(), "energy")
    assert items and all("yoy_pct" in i for i in items)
    for rtype in ("stadt", "bundesland"):
        regions = regional_rent_changes(rtype)
        assert regions["strongest"][0]["change_pct"] >= regions["weakest"][-1]["change_pct"]


def test_investigate_tool_levels():
    from real_basket.agents.tools import investigate_deviation
    from real_basket.data.basket import load_basket

    basket = load_basket()
    res = investigate_deviation("category")
    assert res["categories"] and res["data_source"] == basket.source
    assert investigate_deviation("item", basket.categories[0].value)["items"]
    assert "error" in investigate_deviation("item", "x")
