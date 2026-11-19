from datetime import date

import pandas as pd
import pytest

from real_basket.core.index import compare_with_cpi, essential_index, normalised_weights, yoy_pct
from real_basket.schemas.models import BasketWeights, Category, CpiPoint, PricePoint


def _months(n: int) -> list[date]:
    return [date(2024 + (10 + i) // 12, (10 + i) % 12 + 1, 1) for i in range(n)]


def _prices(n: int = 24) -> list[PricePoint]:
    """Tiny in-test series (never used by the app): food +0.5 %/month, mobility flat."""
    return [PricePoint(item=cat.value, category=cat, period=m, price=price * (1 + rate) ** i, unit="EUR/Monat",
                       source="test")
            for i, m in enumerate(_months(n))
            for cat, price, rate in ((Category.FOOD, 300.0, 0.005), (Category.MOBILITY, 200.0, 0.0))]


def _cpi(n: int = 24) -> list[CpiPoint]:
    return [CpiPoint(period=m, index_value=100 * 1.002 ** i, source="test") for i, m in enumerate(_months(n))]


WEIGHTS = BasketWeights(weights={Category.FOOD: 0.6, Category.MOBILITY: 0.4})


def test_essential_index_starts_at_100():
    assert essential_index(_prices(), WEIGHTS).iloc[0] == pytest.approx(100.0)


def test_comparison_has_deviation():
    df = compare_with_cpi(essential_index(_prices(), WEIGHTS), _cpi())
    assert "deviation_pp" in df.columns
    assert df["deviation_pp"].dropna().shape[0] == 12


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        BasketWeights(weights={Category.FOOD: 0.5, Category.HOUSING_ENERGY: 0.2})


def test_yoy_is_matched_by_date_not_position():
    """A missing month must give NaN for the affected rate, never a comparison with the wrong month."""
    prices = [p for p in _prices(25) if p.period != date(2025, 3, 1)]      # gap in 03/2025
    cpi = [c for c in _cpi(25) if c.period != date(2025, 3, 1)]
    df = compare_with_cpi(essential_index(prices, WEIGHTS), cpi)
    assert pd.isna(df.loc["2026-03-01", "essential_yoy_pct"])               # 03/2025 missing -> no rate
    expected = (df.loc["2026-04-01", "essential_index"] / df.loc["2025-04-01", "essential_index"] - 1) * 100
    assert df.loc["2026-04-01", "essential_yoy_pct"] == pytest.approx(expected)
    assert list(yoy_pct(pd.Series([100.0, 110.0], index=pd.to_datetime(["2024-01-01", "2025-01-01"])))) == \
        pytest.approx([float("nan"), 10.0], nan_ok=True)


def test_slicing_before_indexing_changes_the_rate():
    """Why tools must index the full series: a later base month changes the effective weights (review bug)."""
    full = essential_index(_prices(), WEIGHTS)
    sliced_prices = [p for p in _prices() if p.period >= date(2025, 3, 1)]
    rebased = essential_index(sliced_prices, WEIGHTS)                       # base 03/2025 -> other weights
    assert (rebased.iloc[-1] / rebased.iloc[-13]) != pytest.approx(full.iloc[-1] / full.iloc[-13], abs=1e-9)


def test_positive_weight_without_prices_is_an_error():
    w = BasketWeights(weights={Category.FOOD: 0.5, Category.HEALTH: 0.5})  # no health prices in _prices()
    with pytest.raises(ValueError, match="health"):
        essential_index(_prices(), w)


def test_weights_are_normalised_defensively():
    unvalidated = BasketWeights.model_construct(weights={Category.FOOD: 3.0, Category.MOBILITY: 2.0})
    assert normalised_weights(unvalidated, ["food", "mobility"]).to_dict() == {"food": 0.6, "mobility": 0.4}
    pd.testing.assert_series_equal(essential_index(_prices(), unvalidated), essential_index(_prices(), WEIGHTS))
