from pathlib import Path

import pytest

from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.core.investigation import deviation_breakdown, item_changes, regional_rent_changes
from real_basket.data.basket import load_basket
from real_basket.schemas.models import BasketWeights, Category

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"
pytestmark = pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")

ALL = {"food", "housing_energy", "mobility", "health", "communication"}


def test_breakdown_gaps_add_up_to_the_deviation():
    b = load_basket()
    res = deviation_breakdown(b.prices, b.cpi, b.weights)
    cats = res["categories"]
    assert {c["category"] for c in cats} == ALL
    assert sum(c["contribution_pp"] for c in cats) == pytest.approx(res["essential_yoy_pct"], abs=0.05)
    assert sum(c["gap_pp"] for c in cats) == pytest.approx(res["deviation_pp"], abs=0.05)
    assert abs(cats[0]["gap_pp"]) == max(abs(c["gap_pp"]) for c in cats)     # biggest driver first


def test_breakdown_matches_index_for_custom_weights():
    b = load_basket()
    w = BasketWeights(weights={Category.FOOD: 0.5, Category.HOUSING_ENERGY: 0.5, Category.MOBILITY: 0})
    res = deviation_breakdown(b.prices, b.cpi, w)
    latest = compare_with_cpi(essential_index(b.prices, w), b.cpi).dropna().iloc[-1]
    assert res["deviation_pp"] == pytest.approx(latest["deviation_pp"], abs=0.01)
    assert {c["category"] for c in res["categories"]} == {"food", "housing_energy"}


def test_item_and_region_drill_down():
    b = load_basket()
    items = item_changes(b.prices, "housing_energy")
    assert items and all("yoy_pct" in i for i in items)
    cities = regional_rent_changes(b.real, "stadt")
    assert cities["strongest"][0]["change_pct"] >= cities["weakest"][-1]["change_pct"]
    states = regional_rent_changes(b.real, "bundesland")
    assert states["verified_state_series"] is False and len(states["coverage"]) == 16
    assert "strongest" not in states                     # no state rents are invented


def test_investigate_tool_levels():
    from real_basket.agents.tools import investigate_deviation

    basket = load_basket()
    res = investigate_deviation("category")
    assert res["data_basis"] == basket.label
    assert {c["category"] for c in res["categories"]} == ALL           # drivers, not the label dict
    assert res["category_labels"]["mobility"] == "Verkehr"
    assert investigate_deviation("item", basket.categories[0].value)["items"]
    assert "error" in investigate_deviation("item", "x")
    assert "error" in investigate_deviation("item", "rent")


def test_unknown_level_is_an_error_not_the_category_breakdown():
    from real_basket.agents.tools import investigate_deviation

    for level in ("items", "kategorie", ""):
        res = investigate_deviation(level, "food")
        assert "error" in res and "categories" in res and "deviation_pp" not in res, level
    assert "deviation_pp" in investigate_deviation(" Category ")


def test_tool_results_do_not_depend_on_months():
    """Review bug: slicing the prices before indexing moved the base month (months=13 gave 2,91 % instead of
    2,93 %). The index is now always based on the first month (11/2024 = 100)."""
    from real_basket.agents.tools import calculate_index, investigate_deviation

    ref = calculate_index()
    ref_drv = investigate_deviation("category")
    for months in (1, 13, 18, 24, 100):
        res = calculate_index(months=months)
        for key in ("essential_yoy_pct", "cpi_yoy_pct", "deviation_pp", "category_yoy_pct"):
            assert res[key] == ref[key], (months, key)
        assert investigate_deviation("category", months=months)["categories"] == ref_drv["categories"]
    assert ref["base_period"].startswith("2024-11")
    assert len(calculate_index(months=3)["history"]) == 3
    assert ref["history"][-1]["deviation_pp"] == ref["deviation_pp"]


def test_calculate_index_reports_excluded_categories():
    from real_basket.agents.tools import calculate_index

    res = calculate_index(weights={"food": 1, "housing_energy": 1})
    assert set(res["excluded_categories"]) == ALL - {"food", "housing_energy"}
    assert calculate_index()["excluded_categories"] == []


def test_breakdown_normalises_unvalidated_weights():
    b = load_basket()
    raw = BasketWeights.model_construct(weights={Category.FOOD: 2.0, Category.HOUSING_ENERGY: 2.0})
    res = deviation_breakdown(b.prices, b.cpi, raw)
    assert sum(c["weight"] for c in res["categories"]) == pytest.approx(1.0)
    assert sum(c["gap_pp"] for c in res["categories"]) == pytest.approx(res["deviation_pp"], abs=0.05)


def test_breakdown_needs_the_month_one_year_earlier():
    b = load_basket()
    latest = max(p.period for p in b.prices)
    prev = latest.replace(year=latest.year - 1)
    # without t-12 the latest month has no YoY rate: the breakdown names the month it refers to instead
    res = deviation_breakdown([p for p in b.prices if p.period != prev], b.cpi, b.weights)
    assert res["period"] != str(latest)
    assert sum(c["gap_pp"] for c in res["categories"]) == pytest.approx(res["deviation_pp"], abs=0.05)
    first_year = [p for p in b.prices if p.period < b.prices[0].period.replace(year=b.prices[0].period.year + 1)]
    with pytest.raises(ValueError):                                  # < 13 months: no YoY at all
        deviation_breakdown(first_year, b.cpi, b.weights)


def test_item_changes_compare_by_date_with_gaps():
    b = load_basket()
    prices = [p for p in b.prices if p.category == Category.FOOD]
    latest = max(p.period for p in prices)
    prev = latest.replace(year=latest.year - 1)
    expected = item_changes(prices, "food")[0]["yoy_pct"]
    with_gap = [p for p in prices if p.period != prev.replace(month=prev.month % 12 + 1)]    # a month removed
    assert item_changes(with_gap, "food")[0]["yoy_pct"] == expected                      # still the same month
    assert item_changes([p for p in prices if p.period != prev], "food") == []          # no t-12 -> no rate
