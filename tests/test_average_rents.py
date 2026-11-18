from datetime import date

import pytest

from real_basket.core.rents import TOTAL_COL, average_rents, overall_average
from real_basket.data.demo_data import demo_regional_rents
from real_basket.reports.pdf_report import generate_average_rent_report
from real_basket.schemas.models import RegionType


def test_average_per_state_and_year():
    rents = demo_regional_rents(start=date(2024, 1, 1), months=24)
    table = average_rents(rents, RegionType.STATE)
    assert len(table) == 16
    assert list(table.columns) == ["2024", "2025", TOTAL_COL]
    berlin = [p.price for p in rents if p.region == "Berlin" and p.region_type == RegionType.STATE]
    assert table.loc["Berlin", TOTAL_COL] == pytest.approx(sum(berlin) / len(berlin))


def test_city_average_ranking_and_overall():
    table = average_rents(demo_regional_rents(months=12), RegionType.CITY)
    assert len(table) == 15
    assert table.index[0] == "München"
    assert overall_average(table)[TOTAL_COL] == pytest.approx(table[TOTAL_COL].mean())


def test_average_rent_pdf(tmp_path):
    f = generate_average_rent_report(tmp_path, months=60, end=date(2026, 11, 1))
    assert f.name == "realbasket_miete_durchschnitt.pdf" and f.stat().st_size > 0
