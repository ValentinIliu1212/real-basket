from datetime import date

import pytest

from real_basket.agents.tools import fetch_net_salaries
from real_basket.core.income import average_salaries, rent_burden
from real_basket.core.rents import TOTAL_COL
from real_basket.data.demo_data import STATE_NET_SALARIES, demo_net_salaries, demo_regional_rents
from real_basket.reports.pdf_report import generate_salary_report
from real_basket.schemas.models import RegionType

START, MONTHS = date(2021, 12, 1), 60


def test_average_salary_per_state_same_period_as_rents():
    incomes = demo_net_salaries(start=START, months=MONTHS)
    rents = demo_regional_rents(start=START, months=MONTHS, region_type=RegionType.STATE)
    assert {i.period for i in incomes} == {r.period for r in rents}
    table = average_salaries(incomes)
    assert set(table.index) == set(STATE_NET_SALARIES)
    assert list(table.columns) == ["2021", "2022", "2023", "2024", "2025", "2026", TOTAL_COL]


def test_rent_burden_formula():
    incomes = demo_net_salaries(start=START, months=MONTHS)
    rents = demo_regional_rents(start=START, months=MONTHS, region_type=RegionType.STATE)
    burden = rent_burden(rents, incomes, flat_size_m2=70)
    hh_rent = [r.price for r in rents if r.region == "Hamburg"]
    hh_sal = [i.net_salary for i in incomes if i.region == "Hamburg"]
    expected = (sum(hh_rent) / len(hh_rent)) * 70 / (sum(hh_sal) / len(hh_sal)) * 100
    assert burden.loc["Hamburg", TOTAL_COL] == pytest.approx(expected)


def test_salary_tool_and_pdf(tmp_path):
    result = fetch_net_salaries._tool_func()
    assert len(result) == 16 and all(0 < r["rent_burden_pct"] < 100 for r in result)
    f = generate_salary_report(tmp_path, months=MONTHS, end=date(2026, 11, 1))
    assert f.stat().st_size > 0
