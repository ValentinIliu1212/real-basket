"""Import of the real data from the reference PDFs (reports/real-data) and the basket selection."""

from pathlib import Path

import pytest

from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.core.investigation import deviation_breakdown
from real_basket.data.basket import load_basket
from real_basket.data.real_data import RealDataError, load_real_data, parse_number
from real_basket.schemas.models import Category

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"
needs_docs = pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")


def test_parse_number():
    assert parse_number("1.137,00 €") == 1137.0
    assert parse_number("-0,4 %") == -0.4
    assert parse_number("100,3") == 100.3


def test_missing_documents_fall_back_to_demo(tmp_path):
    with pytest.raises(RealDataError):
        load_real_data(tmp_path)


@needs_docs
def test_real_dataset_is_complete_and_rechecked():
    ds = load_real_data(REAL_DOCS)
    assert ds.all_checks_ok, [c for c in ds.checks if not c.ok]
    assert len(ds.periods) >= 24 and len(ds.cpi) == len(ds.periods)
    assert set(ds.base_amounts) == {Category.FOOD, Category.HOUSING_ENERGY, Category.MOBILITY, Category.HEALTH,
                                    Category.COMMUNICATION}
    assert sum(ds.weights.weights.values()) == pytest.approx(1.0)
    assert len(ds.city_rents) == 15
    assert all(p.source.endswith(tuple(f"S. {n}" for n in range(1, 20))) for p in ds.prices)


@needs_docs
def test_engine_reproduces_printed_ecli():
    ds = load_real_data(REAL_DOCS)
    ecli = essential_index(ds.prices, ds.weights)
    for period, printed in ds.printed_ecli.items():
        assert float(ecli[str(period)]) == pytest.approx(printed, abs=0.051)
    res = deviation_breakdown(ds.prices, ds.cpi, ds.weights)
    assert sum(c["gap_pp"] for c in res["categories"]) == pytest.approx(res["deviation_pp"], abs=0.05)
    latest = compare_with_cpi(ecli, ds.cpi).dropna().iloc[-1]
    assert res["essential_yoy_pct"] == pytest.approx(latest["essential_yoy_pct"], abs=0.01)


@needs_docs
def test_basket_selection():
    assert load_basket("auto").source == "real"
    demo = load_basket("demo")
    assert demo.source == "demo" and Category.RENT in demo.categories


@needs_docs
def test_tools_follow_selected_data_source():
    from real_basket.agents.tools import calculate_essential_vs_cpi, fetch_regional_rents, investigate_deviation
    from real_basket.data.basket import active_data_source, set_data_source

    try:
        set_data_source("demo")
        assert active_data_source() == "demo"
        assert calculate_essential_vs_cpi._tool_func()["data_source"] == "demo"
        assert all(c["data_source"] == "demo" for c in fetch_regional_rents._tool_func(region_type="stadt"))
        assert investigate_deviation._tool_func("region", region_type="stadt")["data_source"] == "demo"
        set_data_source("real")
        assert calculate_essential_vs_cpi._tool_func()["data_source"] == "real"
        assert investigate_deviation._tool_func("region", region_type="stadt")["data_source"] == "real"
        with pytest.raises(ValueError):
            set_data_source("xyz")
    finally:
        set_data_source(None)


@needs_docs
def test_default_weights_are_exact_expenditure_shares():
    from real_basket.agents.tools import calculate_essential_vs_cpi

    ds = load_real_data(REAL_DOCS)
    res = calculate_essential_vs_cpi._tool_func()
    for cat, amount in ds.base_amounts.items():
        assert res["weights"][cat.value] == round(amount / ds.base_total, 4)
    printed_yoy = ds.printed_ecli_yoy[max(ds.printed_ecli_yoy)]
    assert res["essential_yoy_pct"] == pytest.approx(printed_yoy, abs=0.06)


@needs_docs
def test_tools_use_real_data():
    from real_basket.agents.tools import calculate_essential_vs_cpi, fetch_prices, fetch_regional_rents

    res = calculate_essential_vs_cpi._tool_func()
    assert res["data_source"] == "real" and "housing_energy" in res["weights"]
    custom = calculate_essential_vs_cpi._tool_func(weights={"food": 1, "mobility": 1})
    assert custom["weights"] == {"food": 0.5, "mobility": 0.5}
    assert "error" in fetch_prices._tool_func("rent")
    assert fetch_prices._tool_func("health")["prices"]
    cities = fetch_regional_rents._tool_func(region_type="stadt")
    assert len(cities) == 15 and all(c["data_source"] == "real" for c in cities)
