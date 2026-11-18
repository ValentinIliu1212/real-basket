"""Durchschnittsmieten pro Bundesland und Stadt."""

from __future__ import annotations

import pandas as pd

from real_basket.schemas.models import PricePoint, RegionType

TOTAL_COL = "Ø gesamt"


def rents_to_frame(rents: list[PricePoint]) -> pd.DataFrame:
    df = pd.DataFrame([p.model_dump() for p in rents])
    df["period"] = pd.to_datetime(df["period"])
    df["region_type"] = df["region_type"].map(lambda r: getattr(r, "value", r))
    return df


def average_rents(rents: list[PricePoint], region_type: RegionType | None = None) -> pd.DataFrame:
    """Durchschnittliche Miete (EUR/m²) pro Region: eine Spalte pro Jahr plus Gesamtdurchschnitt.

    Index: Region. Sortiert nach Gesamtdurchschnitt (teuerste zuerst).
    """
    df = rents_to_frame(rents)
    if region_type:
        df = df[df["region_type"] == region_type.value]
    df["year"] = df["period"].dt.year
    table = df.pivot_table(index="region", columns="year", values="price", aggfunc="mean")
    table.columns = [str(c) for c in table.columns]
    table[TOTAL_COL] = df.groupby("region")["price"].mean()
    return table.sort_values(TOTAL_COL, ascending=False)


def overall_average(table: pd.DataFrame) -> pd.Series:
    """Ungewichteter Durchschnitt über alle Regionen (nicht nach Einwohnern gewichtet)."""
    return table.mean(axis=0)
