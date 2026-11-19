"""Index calculation: Laspeyres-style essential living cost index and CPI comparison."""

from __future__ import annotations

import pandas as pd

from real_basket.schemas.models import BasketWeights, CpiPoint, PricePoint


def prices_to_frame(prices: list[PricePoint]) -> pd.DataFrame:
    return pd.DataFrame([p.model_dump() for p in prices])


def category_indices(prices: list[PricePoint], base_period: str | None = None) -> pd.DataFrame:
    """Return a DataFrame (period x category) of category indices (base period = 100).

    Each item is indexed to its base price; items within a category are equally weighted.
    """
    df = prices_to_frame(prices)
    df["category"] = df["category"].map(lambda c: getattr(c, "value", c))
    df["period"] = pd.to_datetime(df["period"])
    base = pd.Timestamp(base_period) if base_period else df["period"].min()

    base_prices = df[df["period"] == base].set_index(["category", "item"])["price"]
    df = df.join(base_prices.rename("base_price"), on=["category", "item"])
    df["relative"] = df["price"] / df["base_price"] * 100
    return df.pivot_table(index="period", columns="category", values="relative", aggfunc="mean").sort_index()


def essential_index(prices: list[PricePoint], weights: BasketWeights) -> pd.Series:
    """Weighted essential living cost index (base period = 100)."""
    cat = category_indices(prices)
    w = pd.Series({k.value: v for k, v in weights.weights.items()})
    w = w.reindex(cat.columns).fillna(0)
    return (cat * w).sum(axis=1) / w.sum()


def compare_with_cpi(essential: pd.Series, cpi: list[CpiPoint]) -> pd.DataFrame:
    """Rebase CPI to the essential base period and compute YoY rates and deviation (pp)."""
    cpi_s = pd.Series({pd.Timestamp(c.period): c.index_value for c in cpi}).sort_index()
    df = pd.DataFrame({"essential_index": essential, "cpi_raw": cpi_s}).dropna()
    df["cpi_index"] = df["cpi_raw"] / df["cpi_raw"].iloc[0] * 100
    df = df.drop(columns="cpi_raw")
    df["essential_yoy_pct"] = df["essential_index"].pct_change(12) * 100
    df["cpi_yoy_pct"] = df["cpi_index"].pct_change(12) * 100
    df["deviation_pp"] = df["essential_yoy_pct"] - df["cpi_yoy_pct"]
    return df
