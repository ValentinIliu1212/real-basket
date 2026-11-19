"""PDF-Berichte: ein PDF pro Kalenderjahr mit den Monatspreisen (EUR) der letzten N Monate.

Aufruf: poetry run real-basket-pdf [--months 60] [--out reports]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from real_basket.agents.prompts import DISCLAIMER
from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.core.income import DEFAULT_FLAT_SIZE_M2, average_salaries, rent_burden
from real_basket.core.rents import TOTAL_COL, average_rents, overall_average
from real_basket.data.demo_data import demo_cpi, demo_net_salaries, demo_prices, demo_regional_rents
from real_basket.schemas.models import Category, CpiPoint, PricePoint, RegionType

MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
CATEGORY_DE = {
    Category.FOOD: "Lebensmittel",
    Category.RENT: "Miete",
    Category.ENERGY: "Energie",
    Category.MOBILITY: "Mobilität",
    Category.HOUSING_ENERGY: "Wohnen / Energie",
    Category.HEALTH: "Gesundheit",
    Category.COMMUNICATION: "Kommunikation",
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
        # Durchschnitt über alle Regionen (ungewichtet)
        month_avgs = [sum(v[m] for v in by_region.values() if m in v) / len(by_region) for m in months]
        reg_rows.append(["Ø alle Regionen", format_eur(sum(month_avgs) / len(month_avgs))]
                        + [format_eur(a) for a in month_avgs])
        reg_table = styled(reg_rows, colors.HexColor("#0072BC"), reg_widths)
        reg_table.setStyle(TableStyle([("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 7.5),
                                       ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#0072BC"))]))
        story += [
            PageBreak(),
            Paragraph(f"{title} – {year}", styles["Heading2"]),
            Paragraph(f"Zeitraum: {period_txt} · Angaben in EUR pro m² Wohnfläche, Angebotsmieten",
                      styles["Normal"]),
            Spacer(1, 0.3 * cm),
            reg_table,
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


def generate_average_rent_report(output_dir: str | Path = "reports", months: int = 60,
                                 end: date | None = None) -> Path:
    """PDF mit der durchschnittlichen Miete (EUR/m²) pro Bundesland und Stadt: je Jahr und gesamt."""
    end = (end or date.today()).replace(day=1)
    start = _shift_months(end, -(months - 1))
    rents = demo_regional_rents(start=start, months=months)  # TODO: echte Quelle bei USE_DEMO_DATA=false
    styles = getSampleStyleSheet()
    period_txt = f"{MONTHS_DE[start.month - 1]} {start.year} – {MONTHS_DE[end.month - 1]} {end.year}"

    story = [
        Paragraph("RealBasket – Durchschnittliche Miete pro Bundesland und Stadt", styles["Title"]),
        Paragraph(f"Zeitraum: {period_txt} ({months} Monate) · Angebotsmiete nettokalt in EUR pro m² · "
                  f"Erstellt am {date.today():%d.%m.%Y}", styles["Normal"]),
        Paragraph("<font color='#C0392B'><b>Hinweis: Synthetische Demo-Daten (grobe Größenordnung) – keine "
                  "amtlichen Werte.</b></font>", styles["Normal"]),
    ]
    for rtype, title in ((RegionType.STATE, "Ø Miete nach Bundesland"),
                         (RegionType.CITY, "Ø Miete in den größten Städten")):
        table = average_rents(rents, rtype)
        overall = overall_average(table)
        header = ["Region"] + [c if c == TOTAL_COL else f"Ø {c}" for c in table.columns]
        rows = [header] + [[region] + [format_eur(v) for v in r] for region, r in table.iterrows()]
        rows.append(["Ø alle Regionen"] + [format_eur(v) for v in overall])

        first_w = 4.5 * cm
        other_w = (landscape(A4)[0] - 2 * cm - first_w) / len(table.columns)
        t = Table(rows, colWidths=[first_w] + [other_w] * len(table.columns), repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
            ("FONT", (-1, 1), (-1, -1), "Helvetica-Bold", 8),
            ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0072BC")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F2F6FA")]),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#0072BC")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7BF")),
        ]))
        story += [Spacer(1, 0.5 * cm), Paragraph(title, styles["Heading2"]), t]
    story += [Spacer(1, 0.4 * cm),
              Paragraph("Ø je Jahr = Mittelwert der verfügbaren Monate des Jahres (Rand-Jahre ggf. unvollständig). "
                        "„Ø alle Regionen“ ist ein ungewichteter Mittelwert, nicht nach Einwohnern gewichtet.",
                        styles["Italic"])]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    out_file = out / "realbasket_miete_durchschnitt.pdf"
    SimpleDocTemplate(str(out_file), pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                      topMargin=1 * cm, bottomMargin=1 * cm, title="RealBasket Ø Miete",
                      author="RealBasket").build(story)
    return out_file


def _summary_table(header: list[str], body: list[list[str]], footer: list[str]) -> Table:
    """Tabelle: Region | Werte je Jahr | Ø gesamt (fett) + Fußzeile 'Ø alle Bundesländer'."""
    n_values = len(header) - 1
    first_w = 4.5 * cm
    other_w = (landscape(A4)[0] - 2 * cm - first_w) / n_values
    t = Table([header] + body + [footer], colWidths=[first_w] + [other_w] * n_values, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("FONT", (-1, 1), (-1, -1), "Helvetica-Bold", 8),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0072BC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F2F6FA")]),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#0072BC")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7BF")),
    ]))
    return t


def _format_pct(value: float) -> str:
    return f"{value:.1f} %".replace(".", ",")


def generate_salary_report(output_dir: str | Path = "reports", months: int = 60, end: date | None = None,
                           flat_size_m2: float = DEFAULT_FLAT_SIZE_M2) -> Path:
    """PDF: Ø monatliches Nettogehalt pro Bundesland (je Jahr und gesamt) + Mietbelastungsquote."""
    end = (end or date.today()).replace(day=1)
    start = _shift_months(end, -(months - 1))
    incomes = demo_net_salaries(start=start, months=months)  # TODO: echte Quelle bei USE_DEMO_DATA=false
    rents = demo_regional_rents(start=start, months=months, region_type=RegionType.STATE)
    styles = getSampleStyleSheet()
    period_txt = f"{MONTHS_DE[start.month - 1]} {start.year} – {MONTHS_DE[end.month - 1]} {end.year}"

    salaries = average_salaries(incomes)
    sal_header = ["Bundesland"] + [c if c == TOTAL_COL else f"Ø {c}" for c in salaries.columns]
    sal_body = [[region] + [format_eur(v) for v in row] for region, row in salaries.iterrows()]
    sal_footer = ["Ø alle Bundesländer"] + [format_eur(v) for v in salaries.mean(axis=0)]

    burden = rent_burden(rents, incomes, flat_size_m2)
    bur_body = [[region] + [_format_pct(v) for v in row] for region, row in burden.iterrows()]
    bur_footer = ["Ø alle Bundesländer"] + [_format_pct(v) for v in burden.mean(axis=0)]

    story = [
        Paragraph("RealBasket – Durchschnittliches Nettogehalt pro Bundesland", styles["Title"]),
        Paragraph(f"Zeitraum: {period_txt} ({months} Monate) · Ø monatliches Nettogehalt Vollzeit in EUR · "
                  f"Erstellt am {date.today():%d.%m.%Y}", styles["Normal"]),
        Paragraph("<font color='#C0392B'><b>Hinweis: Synthetische Demo-Daten (grobe Größenordnung, aus "
                  "Bruttoverdiensten abgeleitet) – keine amtlichen Werte.</b></font>", styles["Normal"]),
        Spacer(1, 0.5 * cm),
        Paragraph("Ø Nettogehalt pro Monat", styles["Heading2"]),
        _summary_table(sal_header, sal_body, sal_footer),
        PageBreak(),
        Paragraph(f"Mietbelastung: Anteil der Nettokaltmiete ({flat_size_m2:g} m²) am Nettogehalt",
                  styles["Heading2"]),
        Paragraph(f"Berechnung: Ø Miete €/m² × {flat_size_m2:g} m² ÷ Ø Nettogehalt. Höchste Belastung zuerst.",
                  styles["Normal"]),
        Spacer(1, 0.3 * cm),
        _summary_table(["Bundesland"] + sal_header[1:], bur_body, bur_footer),
        Spacer(1, 0.4 * cm),
        Paragraph("Ø je Jahr = Mittelwert der verfügbaren Monate (Rand-Jahre ggf. unvollständig). "
                  "„Ø alle Bundesländer“ ist ungewichtet (nicht nach Einwohnern gewichtet).", styles["Italic"]),
    ]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    out_file = out / "realbasket_nettogehalt_durchschnitt.pdf"
    SimpleDocTemplate(str(out_file), pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                      topMargin=1 * cm, bottomMargin=1 * cm, title="RealBasket Ø Nettogehalt",
                      author="RealBasket").build(story)
    return out_file


def _year_month_table(values: dict[date, float], years: list[int], fmt) -> Table:
    """Jahr × Monat Matrix (Jan–Dez) + Spalte 'Ø Jahr'."""
    header = ["Jahr"] + MONTHS_DE + ["Ø Jahr"]
    rows = [header]
    for y in years:
        vals = [values.get(date(y, m, 1)) for m in range(1, 13)]
        present = [v for v in vals if v is not None]
        rows.append([str(y)] + [fmt(v) if v is not None else "–" for v in vals]
                    + [fmt(sum(present) / len(present)) if present else "–"])
    first_w = 1.8 * cm
    other_w = (landscape(A4)[0] - 2 * cm - first_w) / 13
    t = Table(rows, colWidths=[first_w] + [other_w] * 13, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("FONT", (-1, 1), (-1, -1), "Helvetica-Bold", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5A6772")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7BF")),
    ]))
    return t


def generate_cpi_report(output_dir: str | Path = "reports", months: int = 60, end: date | None = None) -> Path:
    """PDF: Verbraucherpreisindex (VPI) der letzten `months` Monate – Indexwerte, Inflationsrate ggü.
    Vorjahresmonat und Jahresvergleich mit dem Grundbedarf-Index."""
    end = (end or date.today()).replace(day=1)
    start = _shift_months(end, -(months - 1))
    ext_start = _shift_months(start, -12)  # 12 Monate Vorlauf für Vorjahresvergleich
    # TODO: echte Quelle (Destatis GENESIS 61111-0002) bei USE_DEMO_DATA=false
    cpi = demo_cpi(start=ext_start, months=months + 12)
    comparison = compare_with_cpi(essential_index(demo_prices(start=ext_start, months=months + 12)), cpi)
    comparison = comparison[comparison.index >= pd.Timestamp(start)]

    cpi_values = {c.period: c.index_value for c in cpi if c.period >= start}
    cpi_yoy = {ts.date(): v for ts, v in comparison["cpi_yoy_pct"].items()}
    years = sorted({p.year for p in cpi_values})
    styles = getSampleStyleSheet()
    period_txt = f"{MONTHS_DE[start.month - 1]} {start.year} – {MONTHS_DE[end.month - 1]} {end.year}"

    # Jahresvergleich VPI vs. Grundbedarf
    comparison = comparison.assign(year=comparison.index.year)
    yearly = comparison.groupby("year").agg(
        cpi=("cpi_yoy_pct", "mean"), essential=("essential_yoy_pct", "mean"),
        deviation=("deviation_pp", "mean"), n=("cpi_yoy_pct", "size"))
    cmp_rows = [["Jahr", "Monate", "Ø VPI-Inflation", "Ø Grundbedarf-Inflation", "Abweichung"]]
    for y, r in yearly.iterrows():
        cmp_rows.append([str(y), str(int(r["n"])), _format_pct(r["cpi"]), _format_pct(r["essential"]),
                         f"{r['deviation']:+.1f} pp".replace(".", ",")])
    cmp_rows.append(["Gesamt", str(len(comparison)), _format_pct(comparison["cpi_yoy_pct"].mean()),
                     _format_pct(comparison["essential_yoy_pct"].mean()),
                     f"{comparison['deviation_pp'].mean():+.1f} pp".replace(".", ",")])
    cmp_table = Table(cmp_rows, colWidths=[3 * cm, 2.5 * cm, 4.5 * cm, 5.5 * cm, 4 * cm], hAlign="LEFT")
    cmp_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0072BC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F2F6FA")]),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#0072BC")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7BF")),
    ]))

    story = [
        Paragraph("RealBasket – Verbraucherpreisindex (VPI)", styles["Title"]),
        Paragraph(f"Zeitraum: {period_txt} ({months} Monate) · Basis 2020 = 100 · "
                  f"Erstellt am {date.today():%d.%m.%Y}", styles["Normal"]),
        Paragraph("<font color='#C0392B'><b>Hinweis: Synthetische Demo-Daten (an grobe historische "
                  "Jahresraten angelehnt) – keine amtlichen Werte von Destatis.</b></font>", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("VPI-Indexwerte (2020 = 100)", styles["Heading2"]),
        _year_month_table(cpi_values, years, lambda v: f"{v:.1f}".replace(".", ",")),
        Spacer(1, 0.4 * cm),
        Paragraph("Inflationsrate: Veränderung ggü. Vorjahresmonat in %", styles["Heading2"]),
        _year_month_table(cpi_yoy, years, _format_pct),
        PageBreak(),
        Paragraph("Jahresvergleich: offizielle Inflation (VPI) vs. Grundbedarf-Index", styles["Heading2"]),
        Paragraph("Grundbedarf-Index: Lebensmittel 30 %, Miete 40 %, Energie 15 %, Mobilität 15 %. "
                  "Werte = Ø der monatlichen Veränderungsraten ggü. Vorjahresmonat.", styles["Normal"]),
        Spacer(1, 0.3 * cm),
        cmp_table,
        Spacer(1, 0.5 * cm),
        Paragraph(DISCLAIMER, styles["Italic"]),
        Paragraph("„Ø Jahr“ = Mittelwert der verfügbaren Monate (Rand-Jahre ggf. unvollständig). Die amtliche "
                  "Jahresinflationsrate wird von Destatis aus den Jahresdurchschnitten des Index berechnet.",
                  styles["Italic"]),
    ]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    out_file = out / "realbasket_verbraucherpreisindex.pdf"
    SimpleDocTemplate(str(out_file), pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                      topMargin=1 * cm, bottomMargin=1 * cm, title="RealBasket Verbraucherpreisindex",
                      author="RealBasket").build(story)
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF-Berichte (Preise, Miete, Nettogehalt, VPI) der letzten N Monate.")
    parser.add_argument("--months", type=int, default=60)
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()

    jobs = [
        ("Jahres-PDFs", lambda: generate_yearly_price_reports(args.out, args.months)),
        ("Ø Miete", lambda: [generate_average_rent_report(args.out, args.months)]),
        ("Ø Nettogehalt", lambda: [generate_salary_report(args.out, args.months)]),
        ("Verbraucherpreisindex", lambda: [generate_cpi_report(args.out, args.months)]),
    ]
    for name, job in jobs:
        try:
            for f in job():
                print(f"PDF erstellt: {f.resolve()}")
        except PermissionError as exc:
            print(f"ÜBERSPRUNGEN ({name}): Datei ist gesperrt – bitte im PDF-Viewer schließen. ({exc.filename})")


if __name__ == "__main__":
    main()
