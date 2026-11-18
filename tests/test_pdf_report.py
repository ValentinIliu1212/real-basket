from datetime import date

from real_basket.reports.pdf_report import format_eur, generate_yearly_price_reports


def test_format_eur():
    assert format_eur(1234.5) == "1.234,50 €"
    assert format_eur(0.4) == "0,400 €"


def test_one_pdf_per_year(tmp_path):
    files = generate_yearly_price_reports(tmp_path, months=60, end=date(2026, 11, 1))
    assert [f.name for f in files] == [f"realbasket_preise_{y}.pdf" for y in range(2021, 2027)]
    assert all(f.stat().st_size > 0 for f in files)
