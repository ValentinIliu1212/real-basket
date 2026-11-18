"""PDF-Berichte: ein PDF pro Kalenderjahr mit den Monatspreisen (EUR) der letzten N Monate.

Aufruf: poetry run real-basket-pdf [--months 60] [--out reports]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from real_basket.agents.prompts import DISCLAIMER
from real_basket.data.demo_data import demo_cpi, demo_prices, demo_regional_rents
from real_basket.schemas.models import Category, CpiPoint, PricePoint, RegionType

MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
CATEGORY_DE = {
    Category.FOOD: "Lebensmittel",
    Category.RENT: "Miete",
    Category.ENERGY: "Energie",
    Category.MOBILITY: "Mobilität",
}


def _shift_months(d: date, delta: int) -> date:
    idx = d.year * 12 + d.month - 1 + delta
    return date(idx // 12, idx % 12 + 1, 1)


def format_eur(value: float) -> str:
    """Deutsches Format: 1.234,56 € (Preise < 1 € mit 3 Nachkommastellen)."""
    decimals = 3 if value < 1 else 2
    s = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _build_year_pdf(year: int, prices: list[PricePoint], cpi: list[CpiPoint], out_file: Path,
                    is_demo: bool, regional_rents: list[PricePoint] | None = None) -> None:
    styles = getSampleStyleSheet()
    months = sorted({p.period for p in prices})
    header = ["Kategorie", "Position"] + [MONTHS_DE[m.month - 1] for m in months]

    by_item: dict[tuple[Category, str], dict[date, float]] = defaultdict(dict)
    for p in prices:
        by_item[(p.category, p.item)][p.period] = p.price

    rows = [header]
    for (cat, item), values in sorted(by_item.items(), key=lambda kv: (list(Category).index(kv[0][0]), kv[0][1])):
        rows.append([CATEGORY_DE[cat], item] + [format_eur(values[m]) if m in values else "–" for m in months])

    cpi_by_month = {c.period: c.index_value for c in cpi}
    cpi_row = ["VPI (offiziell)", "Indexwert"] + [
        f"{cpi_by_month[m]:.1f}".replace(".", ",") if m in cpi_by_month else "–" for m in months
    ]

    first_col_w, second_col_w = 2.6 * cm, 5.2 * cm
    month_w = (landscape(A4)[0] - 2 * cm - first_col_w - second_col_w) / max(len(months), 1)
    col_widths = [first_col_w, second_col_w] + [month_w] * len(months)

    def styled(data: list[list[str]], header_color: colors.Color, widths: list[float] | None = None) -> Table:
        t = Table(data, colWidths=widths or col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("BACKGROUND", (0, 0), (-1, 0), header_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7BF")),
        ]))
        return t

    period_txt = f"{MONTHS_DE[months[0].month - 1]} – {MONTHS_DE[months[-1].month - 1]} {year}"
    story = [
        Paragraph(f"RealBasket – Preise für Grundbedarf {year}", styles["Title"]),
        Paragraph(f"Zeitraum: {period_txt} · Alle Preise in Euro (EUR) · Erstellt am "
                  f"{date.today():%d.%m.%Y}", styles["Normal"]),
    ]
    if is_demo:
        story.append(Paragraph("<font color='#C0392B'><b>Hinweis: Synthetische Demo-Daten – keine echten "
                               "Marktpreise.</b></font>", styles["Normal"]))
    story += [
        Spacer(1, 0.4 * cm),
        styled(rows, colors.HexColor("#0072BC")),
        Spacer(1, 0.5 * cm),
        styled([header[:2] + header[2:], cpi_row], colors.HexColor("#5A6772")),
        Spacer(1, 0.5 * cm),
        Paragraph(DISCLAIMER, styles["Italic"]),
    ]

    # --- Miete regional: Bundesländer und größte Städte ---------------------------------------
    reg_first_w, reg_avg_w = 4.0 * cm, 2.2 * cm
    reg_month_w = (landscape(A4)[0] - 2 * cm - reg_first_w - reg_avg_w) / max(len(months), 1)
    reg_widths = [reg_first_w, reg_avg_w] + [reg_month_w] * len(months)
    for rtype, title in ((RegionType.STATE, "Miete pro m² (nettokalt) nach Bundesland"),
                         (RegionType.CITY, "Miete pro m² (nettokalt) in den größten Städten")):
        regional = [p for p in (regional_rents or []) if p.region_type == rtype]
        if not regional:
            continue
        by_region: dict[str, dict[date, float]] = defaultdict(dict)
        for p in regional:
            by_region[p.region][p.period] = p.price
        reg_header = ["Region", "Ø Jahr"] + [MONTHS_DE[m.month - 1] for m in months]
        reg_rows = [reg_header]
        # sortiert nach letztem Monatswert, teuerste Region zuerst
        for region, values in sorted(by_region.items(), key=lambda kv: -kv[1].get(months[-1], 0)):
            vals = [values[m] for m in months if m in values]
            reg_rows.append([region, format_eur(sum(vals) / len(vals))]
                            + [format_eur(values[m]) if m in values else "–" for m in months])
        story += [
            PageBreak(),
            Paragraph(f"{title} – {year}", styles["Heading2"]),
            Paragraph(f"Zeitraum: {period_txt} · Angaben in EUR pro m² Wohnfläche, Angebotsmieten",
                      styles["Normal"]),
            Spacer(1, 0.3 * cm),
            styled(reg_rows, colors.HexColor("#0072BC"), reg_widths),
        ]
        if is_demo:
            story += [Spacer(1, 0.3 * cm),
                      Paragraph("<font color='#C0392B'>Demo-Daten (grobe Größenordnung), keine amtlichen "
                                "Werte.</font>", styles["Normal"])]

    doc = SimpleDocTemplate(str(out_file), pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1 * cm, bottomMargin=1 * cm,
                            title=f"RealBasket Preise {year}", author="RealBasket")
    doc.build(story)


def generate_yearly_price_reports(output_dir: str | Path = "reports", months: int = 60,
                                  end: date | None = None) -> list[Path]:
    """Erzeugt ein PDF pro Kalenderjahr für die letzten `months` Monate (inkl. Endmonat)."""
    end = (end or date.today()).replace(day=1)
    start = _shift_months(end, -(months - 1))

    # TODO: bei USE_DEMO_DATA=false echte Collector verwenden
    prices = demo_prices(start=start, months=months)
    cpi = demo_cpi(start=start, months=months)
    regional_rents = demo_regional_rents(start=start, months=months)
    is_demo = True

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for year in sorted({p.period.year for p in prices}):
        out_file = out / f"realbasket_preise_{year}.pdf"
        _build_year_pdf(year, [p for p in prices if p.period.year == year],
                        [c for c in cpi if c.period.year == year], out_file, is_demo,
                        [r for r in regional_rents if r.period.year == year])
        files.append(out_file)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Ein PDF pro Jahr mit Preisen der letzten N Monate (EUR).")
    parser.add_argument("--months", type=int, default=60)
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()
    for f in generate_yearly_price_reports(args.out, args.months):
        print(f"PDF erstellt: {f.resolve()}")


if __name__ == "__main__":
    main()
