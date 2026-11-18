import pytest

from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.data.demo_data import demo_cpi, demo_prices
from real_basket.schemas.models import BasketWeights, Category


def test_essential_index_starts_at_100():
    idx = essential_index(demo_prices())
    assert idx.iloc[0] == pytest.approx(100.0)


def test_comparison_has_deviation():
    df = compare_with_cpi(essential_index(demo_prices()), demo_cpi())
    assert "deviation_pp" in df.columns
    assert df["deviation_pp"].dropna().shape[0] == 12


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        BasketWeights(weights={Category.FOOD: 0.5, Category.RENT: 0.2})
