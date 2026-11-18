from datetime import date

import pytest

from real_basket.data.demo_data import demo_cpi
from real_basket.reports.pdf_report import generate_cpi_report


def test_demo_cpi_is_anchored_and_consistent():
    # same month must have the same value regardless of the series start
    a = {c.period: c.index_value for c in demo_cpi(start=date(2020, 1, 1), months=84)}
    b = {c.period: c.index_value for c in demo_cpi(start=date(2024, 6, 1), months=12)}
    assert a[date(2020, 1, 1)] == 100.0
    assert all(a[p] == v for p, v in b.items())
    # Dec 2022 vs Dec 2021 ~ 6.9 % (demo rate for 2022)
    assert a[date(2022, 12, 1)] / a[date(2021, 12, 1)] - 1 == pytest.approx(0.069, abs=0.002)


def test_cpi_pdf(tmp_path):
    f = generate_cpi_report(tmp_path, months=60, end=date(2026, 11, 1))
    assert f.name == "realbasket_verbraucherpreisindex.pdf" and f.stat().st_size > 0
