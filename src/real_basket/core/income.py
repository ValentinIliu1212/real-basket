"""Durchschnittliches Nettogehalt pro Bundesland und Mietbelastung (Miete / Nettogehalt)."""

from __future__ import annotations

import pandas as pd

from real_basket.core.rents import TOTAL_COL, average_rents
from real_basket.schemas.models import IncomePoint, PricePoint, RegionType

DEFAULT_FLAT_SIZE_M2 = 70


def average_salaries(incomes: list[IncomePoint]) -> pd.DataFrame:
    """Ø monatliches Nettogehalt (EUR) pro Bundesland: eine Spalte pro Jahr plus Gesamtdurchschnitt."""
    df = pd.DataFrame([i.model_dump() for i in incomes])
    df["period"] = pd.to_datetime(df["period"])
    df["year"] = df["period"].dt.year
    table = df.pivot_table(index="region", columns="year", values="net_salary", aggfunc="mean")
    table.columns = [str(c) for c in table.columns]
    table[TOTAL_COL] = df.groupby("region")["net_salary"].mean()
    return table.sort_values(TOTAL_COL, ascending=False)


def rent_burden(rents: list[PricePoint], incomes: list[IncomePoint],
                flat_size_m2: float = DEFAULT_FLAT_SIZE_M2) -> pd.DataFrame:
    """Mietbelastungsquote in % = (Ø Miete €/m² × Wohnfläche) / Ø Nettogehalt, je Bundesland und Jahr."""
    rent_tbl = average_rents(rents, RegionType.STATE)
    salary_tbl = average_salaries(incomes)
    rent_tbl, salary_tbl = rent_tbl.align(salary_tbl, join="inner")
    burden = rent_tbl * flat_size_m2 / salary_tbl * 100
    return burden.sort_values(TOTAL_COL, ascending=False)
