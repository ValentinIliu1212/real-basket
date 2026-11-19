"""Build the architecture slide decks (German and English): current state and the MCP/A2A target proposal.

Run:  poetry run python docs/architecture/build_decks.py
Output (next to this script):
  - RealBasket_Architektur_Ist.pptx                 / RealBasket_Architecture_Current.pptx
  - RealBasket_Architektur_Vorschlag_MCP_A2A.pptx   / RealBasket_Architecture_Proposal_MCP_A2A.pptx

The slides are written in German; the English decks translate every text via `texts_en.EN`
(German text -> English text; `texts_en.SAME` lists language-neutral texts). A German text without translation
stops the build with a list of the missing texts.

Figures (result box, number of data checks) are NOT typed in: `facts()` computes them from the reference PDFs at
build time with the same code as dashboard and agent, so the slides cannot go stale. Test counts are not shown
(they change with every commit).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(OUT.parents[1] / "src"))
from texts_en import EN, GROUPS_EN, SAME

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
TEAL = RGBColor(0x2A, 0x9D, 0x8F)
PURPLE = RGBColor(0x6D, 0x4C, 0x9F)
ORANGE = RGBColor(0xE7, 0x6F, 0x51)
SAND = RGBColor(0xF4, 0xD3, 0x8C)
LIGHT = RGBColor(0xEE, 0xF2, 0xF7)
GREY = RGBColor(0x6B, 0x72, 0x80)
DARK = RGBColor(0x1F, 0x29, 0x37)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FOOTER = "RealBasket · Architektur · Stand November 2026"


# --- language ---------------------------------------------------------------------------------------
class Raw(str):
    """Text that is already in the target language (or code) and must not be translated again."""


LANG = "de"
MISSING: list[str] = []
USED: set[str] = set()


def tr(text: str) -> str:
    if LANG == "de" or isinstance(text, Raw) or text in SAME or not re.search(r"[A-Za-zÄÖÜäöüß]", text):
        return text
    if text not in EN:
        MISSING.append(text)
        return text
    USED.add(text)
    return EN[text]


def bi(de: str, en: str) -> Raw:
    """Generated text in both languages (contains figures, so it cannot be a key of texts_en.EN)."""
    return Raw(de if LANG == "de" else en)


def fmt_num(value: float, sign: bool = True) -> str:
    """+2,93 (de) / +2.93 (en)"""
    text = f"{value:{'+' if sign else ''}.2f}"
    return text.replace(".", ",") if LANG == "de" else text


# --- figures from the reference data (computed at build time) ----------------------------------------
FACTS: dict = {}


def facts() -> dict:
    """Latest result and data checks, computed with the same code as dashboard and agent (no typed-in numbers)."""
    from real_basket.core.investigation import deviation_breakdown
    from real_basket.data.basket import load_basket
    from real_basket.schemas.models import CATEGORY_LABEL_DE, Category

    b = load_basket()
    res = deviation_breakdown(b.prices, b.cpi, b.weights)
    driver = res["categories"][0]
    return {"period": f"{b.real.periods[-1]:%m/%Y}", "essential": res["essential_yoy_pct"],
            "cpi": res["cpi_yoy_pct"], "deviation": res["deviation_pp"], "driver_gap": driver["gap_pp"],
            "driver_de": CATEGORY_LABEL_DE[Category(driver["category"])], "driver_en": GROUPS_EN[driver["category"]],
            "checks": len(b.real.checks), "checks_ok": sum(c.ok for c in b.real.checks)}


# --- helpers ---------------------------------------------------------------------------------------
def new_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs


def _runs(paragraph, text: str, size: float, color: RGBColor, bold: bool = False, font: str | None = None):
    run = paragraph.add_run()
    run.text = tr(text)
    run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, color
    if font:
        run.font.name = font
    return run


def textbox(s, x, y, w, h, lines, size=16, color=DARK, bold=False, align=PP_ALIGN.LEFT, font=None):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        _runs(p, line, size, color, bold, font)
    return tf


def bullets(s, x, y, w, h, items, size=18):
    """items: str (level 0) or (str, 1) for a sub-bullet."""
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        text, level = item if isinstance(item, tuple) else (item, 0)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        _runs(p, Raw(("      – " if level else "• ") + tr(text)), size - 3 * level, GREY if level else DARK)
    return tf


def title_slide(prs, title, subtitle):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = NAVY
    bg.line.fill.background()
    textbox(s, 0.8, 2.5, 11.7, 1.3, title, 40, WHITE, True)
    textbox(s, 0.8, 3.8, 11.7, 1.2, subtitle, 20, SAND)
    textbox(s, 0.8, 6.6, 11.7, 0.5, FOOTER, 12, LIGHT)
    return s


def slide(prs, title, subtitle=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.9))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    textbox(s, 0.5, 0.14, 12.3, 0.65, title, 26, WHITE, True)
    if subtitle:
        textbox(s, 0.5, 0.92, 12.3, 0.35, subtitle, 13, GREY)
    textbox(s, 0.5, 7.08, 9, 0.35, FOOTER, 10, GREY)
    textbox(s, 11.8, 7.08, 1.0, 0.35, str(len(prs.slides)), 10, GREY, align=PP_ALIGN.RIGHT)
    return s


def box(s, x, y, w, h, title, body=(), fill=LIGHT, fg=None, size=13, border=None, dashed=False,
        align=PP_ALIGN.CENTER, font=None):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = 0.08
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.shadow.inherit = False
    if border is not None:
        sh.line.color.rgb = border
        sh.line.width = Pt(1.25)
        if dashed:
            sh.line.dash_style = MSO_LINE.DASH
    else:
        sh.line.fill.background()
    fg = fg or (WHITE if fill in (NAVY, TEAL, PURPLE, ORANGE) else DARK)
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for side in ("margin_left", "margin_right"):
        setattr(tf, side, Inches(0.08))
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    p.alignment = align
    if title:
        _runs(p, title, size, fg, True, font)
    for line in body:
        p = tf.add_paragraph()
        p.alignment = align
        _runs(p, Raw(line) if font else line, size - 2, fg, False, font)    # code (font set) is not translated
    return sh


def arrow(s, x1, y1, x2, y2, color=GREY, dashed=False, label=None, both=False, lx=None, ly=None):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(1.75)
    if dashed:
        c.line.dash_style = MSO_LINE.DASH
    ln = c.line._get_or_add_ln()
    if both:
        ln.append(ln.makeelement(qn("a:headEnd"), {"type": "triangle"}))
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle"}))
    if label:
        textbox(s, lx if lx is not None else (x1 + x2) / 2 + 0.05, ly if ly is not None else (y1 + y2) / 2 - 0.15,
                2.2, 0.3, label, 10, color)
    return c


def table(s, x, y, w, rows, col_w, size=12, row_h=0.42):
    shape = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w),
                               Inches(row_h * len(rows)))
    tbl = shape.table
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = tbl.cell(i, j)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if i == 0 else (LIGHT if i % 2 else WHITE)
            cell.margin_left = cell.margin_right = Inches(0.08)
            _runs(cell.text_frame.paragraphs[0], value, size, WHITE if i == 0 else DARK, i == 0)
    return tbl


def flow(s, steps, y=1.6, h=2.2, fills=None, size=13):
    """Numbered process steps left to right with arrows."""
    n, gap, x0, total = len(steps), 0.35, 0.5, 12.3
    w = (total - gap * (n - 1)) / n
    for i, (title, body) in enumerate(steps):
        x = x0 + i * (w + gap)
        fill = (fills or [TEAL])[i % len(fills or [TEAL])]
        box(s, x, y, w, h, Raw(f"{i + 1}  {tr(title)}"), body, fill, size=size)
        if i < n - 1:
            arrow(s, x + w + 0.03, y + h / 2, x + w + gap - 0.03, y + h / 2, NAVY)


def legend(s, items, y=6.62):
    x = 0.5
    for label, fill in items:
        box(s, x, y, 0.3, 0.3, "", (), fill, border=GREY if fill == LIGHT else None)
        textbox(s, x + 0.35, y - 0.03, 2.4, 0.35, label, 11, GREY)
        x += 2.55


# --- deck 1: current architecture ----------------------------------------------------------------
def current_deck() -> Presentation:
    prs = new_deck()
    title_slide(prs, "RealBasket – Ist-Architektur",
                "Agentischer Index der Grundlebenshaltungskosten im Vergleich zum amtlichen VPI\n"
                "Streamlit · Strands Agents · MCP · Azure OpenAI · deterministische Rechenkerne")

    f = FACTS
    s = slide(prs, "Was RealBasket heute leistet")
    bullets(s, 0.5, 1.3, 8.0, 5.6, [
        "Index der Grundlebenshaltungskosten (ECLI-Warenkorb, 5 Ausgabengruppen) vs. amtlicher VPI",
        "Echte Daten: deterministisch aus den PDF-Tabellen in reports/real-data geparst",
        (bi(f"{f['checks']} Nachrechen-Prüfungen (Summen, Lücken, ECLI, Jahresraten, VPI, Stadtmieten, Länder)",
            f"{f['checks']} re-checks (sums, gaps, ECLI, yearly rates, CPI, city rents, federal states)"), 1),
        ("Keine Demo-Daten, kein Fallback: ohne PDFs Fehlermeldung statt Zahlen", 1),
        "Einflussfaktoren: Beitrag jeder Ausgabengruppe zur Abweichung in Prozentpunkten",
        "Mieten der 15 größten Städte (Jan vs. Okt 2026); je Bundesland nur Abdeckung",
        "Methodenhinweise per RAG (BM25 + Embeddings), Zitate mit Datei und Seite",
        "Chat mit RealBasket: Strands-Agent auf Azure OpenAI (gpt-4o), Antworten auf Deutsch",
        "Alle Werkzeuge im MCP-Server realbasket (ein Prozess, Bereiche data · analysis · knowledge)",
        "Grundsatz: Zahlen nur aus deterministischen Tools; ein Guardrail prüft jede Zahl der Antwort",
    ], 15)
    box(s, 8.9, 1.5, 3.9, 3.6, bi(f"Ergebnis {f['period']} (echte Daten)", f"Result {f['period']} (real data)"),
        ["", bi(f"Grundbedarf: {fmt_num(f['essential'])} %", f"Essentials: {fmt_num(f['essential'])} %"),
         bi(f"VPI: {fmt_num(f['cpi'])} %", f"CPI: {fmt_num(f['cpi'])} %"),
         bi(f"Abweichung: {fmt_num(f['deviation'])} PP", f"Deviation: {fmt_num(f['deviation'])} pp"), "",
         "Größter Einflussfaktor:", bi(f"{f['driver_de']} ({fmt_num(f['driver_gap'])} PP)",
                                       f"{f['driver_en']} ({fmt_num(f['driver_gap'])} pp)")], TEAL, size=17)
    textbox(s, 8.9, 5.25, 3.9, 0.8, "Quelle: ECLI-Modellrechnung 2024–2026, Basis Nov 2024 = 100; Abweichung aus "
            "ungerundeten Raten, Werte beim Erstellen der Folien berechnet", 11, GREY)

    s = slide(prs, "Komponenten", "Streamlit hostet Dashboard und Agenten; die Werkzeuge laufen im MCP-Server "
              "realbasket (Subprozess, stdio); nur das LLM ist extern")
    box(s, 0.5, 1.35, 12.3, 0.7, "Streamlit-UI  (ui/app.py)",
        [("Index vs. VPI · Einflussfaktoren · Miete Städte · Methodenhinweise · "
          "Chat mit RealBasket · Sidebar: Gewichte & PDF-Berichte")], NAVY, size=14)
    box(s, 0.5, 2.4, 4.0, 1.0, "Orchestrator-Agent (Strands)",
        ["REALBASKET-ORCHESTRATOR · agents/orchestrator.py", "MCPClient · agents/mcp_clients.py"], TEAL)
    box(s, 5.0, 2.4, 3.6, 1.0, "Azure OpenAI",
        ["gpt-4o (Completion)", "text-embedding-3-large"], ORANGE)
    box(s, 9.4, 2.4, 3.4, 1.0, "Zahlen-Guardrail",
        ["agents/guardrail.py", "Zahlen der Antwort vs. Tool-Ergebnisse"], LIGHT, border=TEAL, size=12)
    box(s, 0.5, 3.75, 4.0, 1.0, "MCP-Server realbasket  (mcp_servers/)",
        ["data: get_basket · get_prices · get_cpi · calculate_index · data_checks",
         "analysis: investigate_deviation · get_regional_rents",
         "knowledge: search_methodology · list_documents"], PURPLE, size=11)
    box(s, 5.0, 3.75, 3.6, 1.0, "Prompts  (agents/prompts.py)",
        ["Deutsch · Disclaimer · nur echte Daten, keine Schätzungen"], LIGHT, border=GREY, size=12)
    box(s, 9.4, 3.75, 3.4, 1.0, "PDF-Berichte",
        ["reports/pdf_report.py (reportlab)"], LIGHT, border=GREY, size=12)
    box(s, 0.5, 5.05, 2.55, 1.05, "Rechenkern  core/",
        ["index.py", "investigation.py"], LIGHT, border=NAVY, size=12)
    box(s, 3.25, 5.05, 2.6, 1.05, "Daten  data/",
        ["real_data.py (Parser + Prüfungen)", "basket.py (nur echte Daten)"], LIGHT, border=NAVY, size=12)
    box(s, 6.05, 5.05, 2.55, 1.05, "Wissensbasis  knowledge/",
        ["ingest · BM25 + Embedding", "(RRF) · index.json"], LIGHT, border=NAVY, size=12)
    box(s, 9.4, 5.05, 3.4, 1.05, "Konfiguration",
        ["core/settings.py · core/llm.py", ".env im Projektordner"], LIGHT, border=GREY, size=12)
    box(s, 3.25, 6.3, 5.35, 0.45, "reports/real-data/*.pdf  –  ECLI-Modellrechnung 2024 · 2025 · 2026",
        (), LIGHT, border=GREY, dashed=True, size=11)
    arrow(s, 2.5, 2.05, 2.5, 2.4, NAVY, label="Chat", lx=2.6, ly=2.05)
    arrow(s, 4.75, 2.05, 4.75, 5.05, NAVY, label="Dashboard (ohne LLM)", lx=4.8, ly=4.75)
    arrow(s, 8.95, 2.05, 9.4, 4.0, NAVY, label="PDF", lx=8.7, ly=3.35)
    arrow(s, 11.1, 2.05, 11.1, 2.4, NAVY, label="Antwort prüfen", lx=11.2, ly=2.05)
    arrow(s, 4.5, 2.9, 5.0, 2.9, ORANGE, both=True)
    arrow(s, 2.5, 3.4, 2.5, 3.75, PURPLE, label="MCP (stdio / HTTP)", lx=2.6, ly=3.42)
    arrow(s, 1.5, 4.75, 1.5, 5.05, GREY)
    arrow(s, 3.6, 4.75, 3.9, 5.05, GREY)
    arrow(s, 4.3, 4.75, 6.6, 5.05, GREY)
    arrow(s, 3.25, 5.55, 3.05, 5.55, GREY)
    arrow(s, 4.5, 6.1, 4.5, 6.3, GREY)
    arrow(s, 7.3, 6.1, 7.3, 6.3, GREY)

    s = slide(prs, "Ablauf einer Chat-Frage",
              "Beispiel: „Steigen die Grundlebenshaltungskosten stärker als der VPI?“")
    flow(s, [
        ("Frage", ["Nutzer fragt im Tab", "„Chat mit RealBasket“"]),
        ("Orchestrator", ["Streamlit ruft den Agenten", "in-process auf; MCP-Server", "startet als Subprozess"]),
        ("Planung", ["gpt-4o wählt die Tools", "(Function Calling über", "die MCP-Tool-Schemas)"]),
        ("Rechnen", ["MCP-Tools rechnen deter-", "ministisch (core/, data/)", "bzw. suchen Hinweise"]),
        ("Antwort", ["Deutsch, Zahlen aus Tools,", "Quellen „Datei S. N“,", "Disclaimer"]),
        ("Prüfung", ["Guardrail gleicht jede", "Zahl mit den Tool-", "Ergebnissen ab"]),
    ], y=1.7, h=2.3, fills=[NAVY, TEAL, ORANGE, PURPLE, NAVY, TEAL], size=13)
    bullets(s, 0.5, 4.5, 12.3, 2.4, [
        ("Dashboard-Tabs (Index vs. VPI, Einflussfaktoren) rufen core/ und data/ direkt auf – ohne LLM, "
         "deshalb identische Zahlen in Dashboard und Chat"),
        ("Nur echte Daten: Mieten je Bundesland und Nettogehälter sind nicht in den Quellen – der Agent sagt das, "
         "statt zu schätzen"),
        "Unveränderte Gewichts-Regler → exakte Warenkorbgewichte aus den PDFs",
    ], 16)

    s = slide(prs, "Datenpipeline", "Zwei getrennte Pfade: Zahlen (deterministisch) und Methodenhinweise (RAG)")
    box(s, 0.5, 2.9, 2.0, 1.3, "Referenz-PDFs", ["reports/real-data", "2024 · 2025 · 2026"], NAVY)
    textbox(s, 2.7, 1.35, 10, 0.4, "Zahlenpfad", 15, TEAL, True)
    textbox(s, 2.7, 4.55, 10, 0.4, "Hinweispfad (RAG)", 15, PURPLE, True)
    num = [("Text extrahieren", ["ingest.extract_pages", "(pypdf)"]),
           ("Tabellen parsen", ["Basiswarenkorb · Monats-", "kosten · ECLI/VPI · Mieten"]),
           (bi(f"{FACTS['checks']} Prüfungen", f"{FACTS['checks']} checks"),
            ["Summen · Lücken · ECLI", "VPI · Mieten · Länder"]),
           ("Warenkorb", ["load_basket()", "nur echte Daten"]),
           ("Rechenkern", ["Index · Abweichung", "Einflussfaktoren"])]
    rag = [("Passagen", ["Hinweise + Text-", "Tabellenzellen"]),
           ("Bereinigen", ["Zahlen verworfen,", "Duplikate zusammengeführt"]),
           ("Index", ["index.json", "+ Embeddings"]),
           ("Suche", ["BM25 + Embedding", "(Reciprocal Rank Fusion)"]),
           ("Zitat", ["Datei + Seite", "„auch in …“"])]
    for row, (y, items, fill) in enumerate([(1.8, num, TEAL), (5.0, rag, PURPLE)]):
        for i, (t, b) in enumerate(items):
            x = 3.0 + i * 2.0
            box(s, x, y, 1.75, 1.3, t, b, fill, size=12)
            if i:
                arrow(s, x - 0.25, y + 0.65, x, y + 0.65, NAVY)
        arrow(s, 2.5, 3.55, 3.0, y + 0.65, NAVY)
    textbox(s, 3.0, 3.2, 9.8, 0.6, "Kein Fallback: PDFs fehlen oder nicht lesbar → RealDataError; Dashboard "
            "zeigt den Fehler, Tools liefern {\"error\": …} – es gibt keine Demo-Daten", 12, GREY)
    textbox(s, 3.0, 6.4, 9.8, 0.6, "Ohne LLM-Zugang: reine BM25-Suche (offline) mit deutscher Stammformbildung "
            "und Glossar Englisch → Deutsch", 12, GREY)

    s = slide(prs, "Technologie-Stack")
    table(s, 0.5, 1.4, 12.3, [
        ["Schicht", "Technologie", "Rolle"],
        ["UI", "Streamlit, Plotly", "Dashboard, Chat, PDF-Download"],
        ["Agenten", "Strands Agents SDK (OpenAIModel / AzureOpenAIModel)", "Orchestrator-Agent + Zahlen-Guardrail"],
        ["Werkzeuge", "MCP Python SDK (MCPServer), Strands MCPClient", "Ein MCP-Server realbasket, stdio / HTTP"],
        ["LLM", "Azure OpenAI: gpt-4o, text-embedding-3-large", "Planung, Formulierung, Embeddings"],
        ["Daten", "pypdf, pandas, pydantic", "PDF-Parsing, Prüfungen, Modelle"],
        ["Wissen", "eigener BM25 + Embedding-Retriever, index.json", "Methodenhinweise mit Zitaten"],
        ["Berichte", "reportlab", "PDF-Berichte"],
        ["Konfiguration", "pydantic-settings, .env (Projektordner)", "Azure-Einstellungen, KNOWLEDGE_DIR"],
        ["Qualität / Build", "pytest (inkl. MCP-Contract-Tests), ruff, Poetry, GitHub Actions",
         "Tests, Lint, CI, Abhängigkeiten"],
    ], [2.3, 5.6, 4.4], size=14, row_h=0.52)

    s = slide(prs, "Stärken und Grenzen")
    box(s, 0.5, 1.35, 6.0, 0.55, "Stärken", (), TEAL, size=16)
    bullets(s, 0.5, 2.0, 6.0, 4.9, [
        "Einfach: ein Deployment, ein MCP-Server-Prozess – ideal für die Demo",
        "Werkzeuge per MCP wiederverwendbar (Claude Desktop, VS Code)",
        "Deterministische, nachgeprüfte Zahlen; LLM nur für Sprache",
        "Dashboard und Chat nutzen denselben Rechenkern",
        "Nur echte, nachgerechnete Daten – keine synthetischen Werte",
        "Offline nutzbar ohne LLM (Dashboard, BM25-Suche, PDFs)",
        "Automatische Tests inkl. MCP-Contract-Tests, Lint und CI",
    ], 16)
    box(s, 6.8, 1.35, 6.0, 0.55, "Grenzen", (), ORANGE, size=16)
    bullets(s, 6.8, 2.0, 6.0, 4.9, [
        "Ein MCP-Server für alle Bereiche: gemeinsame Rechte, gemeinsame Skalierung",
        "Agent läuft im Streamlit-Prozess: skaliert nur mit der UI; Dashboard nutzt core/ direkt",
        "Guardrail prüft Zahlen, nicht Aussagen (falsche Zuordnung bleibt möglich)",
        "Datenstand fix (PDFs bis 10/2026), keine Live-Anbindung (Destatis)",
        "Keine Mieten je Bundesland, keine Nettogehälter in den Quellen",
        "Kein Auth-/Mandantenkonzept, Schlüssel in .env",
    ], 16)
    return prs


# --- deck 2: MCP / A2A proposal ------------------------------------------------------------------
def proposal_deck() -> Presentation:
    prs = new_deck()
    title_slide(prs, "RealBasket – Zielarchitektur mit MCP und A2A",
                "Vorschlag: Werkzeuge und Daten per MCP, Agenten als A2A-Dienste\n"
                "Phase 1 umgesetzt: ein MCP-Server realbasket mit den Bereichen data · analysis · knowledge")

    s = slide(prs, "Warum MCP und A2A?")
    bullets(s, 0.5, 1.3, 6.3, 5.6, [
        "Wiederverwendung: RealBasket-Daten und -Rechnungen in Copilot, Claude Desktop oder VS Code nutzbar",
        "Interoperabilität: andere Agenten (z. B. von Partnern) fragen RealBasket per A2A",
        "Entkopplung: Agenten und Werkzeuge einzeln versionieren, deployen und skalieren",
        "Klare Verträge: Tool-Schemas (MCP) und Agent Cards (A2A) statt Python-Importen",
        "Determinismus bleibt: Zahlen kommen weiterhin nur aus den Rechen-Tools",
    ], 17)
    box(s, 7.2, 1.4, 5.6, 2.4, "MCP – Model Context Protocol",
        ["Agent ↔ Werkzeuge & Daten", "", "Tools (Funktionen) · Resources (Dokumente, Daten)",
         "Prompts (Vorlagen)", "Transport: stdio (lokal) · Streamable HTTP"], PURPLE, size=16)
    box(s, 7.2, 4.1, 5.6, 2.4, "A2A – Agent2Agent-Protokoll",
        ["Agent ↔ Agent", "", "Agent Card (Fähigkeiten, Endpunkt, Auth)",
         "Tasks · Nachrichten · Artefakte", "JSON-RPC über HTTPS · SSE-Streaming"], TEAL, size=16)

    s = slide(prs, "Zielarchitektur", "Clients → Orchestrator (A2A) → Fach-Agenten (A2A) → MCP-Server realbasket → "
              "Datenquellen")
    for x, (t, b) in zip((0.5, 3.6, 6.7, 9.8), [("Streamlit-UI", ["Dashboard + Chat · A2A-Client"]),
                                                ("Microsoft Teams / Copilot", ["A2A-Client"]),
                                                ("Partner-Agenten", ["z. B. Verbraucherberatung · A2A"]),
                                                ("Claude Desktop / VS Code", ["MCP-Host"])]):
        box(s, x, 1.35, 2.9, 0.65, t, b, NAVY, size=12)
    box(s, 0.5, 2.3, 1.8, 0.8, "Azure OpenAI", ["gpt-4o · Embeddings"], ORANGE, size=12)
    box(s, 2.6, 2.3, 6.2, 0.8, "Orchestrator-Agent (Strands)",
        ["A2A-Server + A2A-Client · Antwort auf Deutsch mit Disclaimer"], TEAL, size=13)
    textbox(s, 0.5, 3.12, 9.5, 0.3, "A2A  ·  JSON-RPC über HTTPS  ·  Agent Cards  ·  Tasks  ·  SSE-Streaming",
            11, TEAL, True)
    agents = [("Price-Collector", ["Preise je Gruppe"]), ("Abweichungs-Analyst", ["Einflussfaktoren, Mieten"]),
              ("Methodik-Agent", ["RAG, Zitate"]), ("Report-Agent", ["PDF-Berichte"])]
    for i, (t, b) in enumerate(agents):
        box(s, 0.5 + i * 2.4, 3.45, 2.2, 0.75, t, b, TEAL, size=12)
    textbox(s, 0.5, 4.22, 12.3, 0.3, "MCP-Server realbasket (ein Prozess, ein Modul je Bereich)  ·  stdio / "
            "Streamable HTTP  ·  Tools · Resources · Prompts", 11, PURPLE, True)
    box(s, 0.4, 4.5, 9.9, 1.1, "", (), LIGHT, border=PURPLE)
    servers = [("Bereich data ✓", ["get_prices · get_cpi", "calculate_index · data_checks"]),
               ("Bereich analysis ✓", ["investigate_deviation", "get_regional_rents"]),
               ("Bereich knowledge ✓", ["search_methodology", "Resource doc://…/seite"]),
               ("Bereich report (geplant)", ["render_pdf", "Resource report://…"]),
               ("destatis-genesis (neu)", ["eigener Server", "get_vpi_table · Live-VPI"])]
    for i, (t, b) in enumerate(servers):
        planned = "geplant" in t or "neu" in t
        box(s, 0.5 + i * 2.5, 4.55, 2.3, 1.0, t, b, LIGHT if planned else PURPLE, size=12,
            border=PURPLE if planned else None, dashed=planned)
    sources = [("reports/real-data/*.pdf", ["ECLI 2024–2026 · VPI"]), ("Stadtmieten (in den PDFs)",
                                                                       ["15 Städte, immowelt"]),
               ("Vektorindex", ["index.json / Vector Store"]), ("Externe APIs", ["Destatis GENESIS · Mietportale"])]
    for x, (t, b) in zip((0.5, 3.6, 6.7, 9.8), sources):
        box(s, x, 5.85, 2.9, 0.65, t, b, LIGHT, border=GREY, size=12)
    # clients -> orchestrator
    arrow(s, 1.95, 2.0, 3.3, 2.3, NAVY)
    arrow(s, 5.05, 2.0, 5.05, 2.3, NAVY)
    arrow(s, 8.15, 2.0, 7.9, 2.3, NAVY)
    arrow(s, 11.5, 2.0, 11.5, 4.55, PURPLE, dashed=True, label="MCP direkt", lx=11.55, ly=3.2)
    arrow(s, 2.6, 2.7, 2.3, 2.7, ORANGE, both=True)
    # orchestrator -> agents
    for x_from, x_to in ((3.0, 1.6), (4.5, 4.0), (6.4, 6.4), (8.5, 8.8)):
        arrow(s, x_from, 3.1, x_to, 3.45, TEAL)
    # agents -> MCP servers
    for x_from, x_to in ((1.6, 1.65), (3.6, 1.9), (4.4, 4.15), (6.4, 6.65), (8.8, 9.15)):
        arrow(s, x_from, 4.2, x_to, 4.55, PURPLE)
    # MCP servers -> sources
    for x_from, x_to in ((1.3, 1.6), (2.2, 3.9), (4.15, 4.6), (6.65, 8.15), (11.65, 11.25)):
        arrow(s, x_from, 5.55, x_to, 5.85, GREY)
    legend(s, [("Clients", NAVY), ("A2A-Agenten", TEAL), ("MCP-Server", PURPLE), ("LLM", ORANGE),
               ("Datenquellen", LIGHT)])

    s = slide(prs, "MCP-Server realbasket im Detail", "Ein Server-Prozess, ein Modul je Bereich – dünne Hüllen um "
              "core/, data/, knowledge/ (src/real_basket/mcp_servers/)")
    table(s, 0.5, 1.45, 12.3, [
        ["Bereich (Modul)", "Tools", "Resources / Prompts", "Status"],
        ["data (data_tools.py)", ("get_basket() · get_prices(category, months) · get_cpi(months) · "
                                  "calculate_index(weights, months) · data_checks()"),
         "basket://weights · basket://checks", "umgesetzt"],
        ["analysis (analysis_tools.py)", ("investigate_deviation(level, category, region_type, months) · "
                                          "get_regional_rents(region_type)"), "–", "umgesetzt"],
        ["knowledge (knowledge_tools.py)", "search_methodology(query, year) · list_documents()",
         "doc://{datei}/seite/{n} · Prompt hinweis_zitieren", "umgesetzt"],
        ["report (geplant)", "render_pdf(kind, year)", "report://{name}.pdf", "offen (reports/pdf_report.py)"],
        ["destatis-genesis (eigener Server)", "get_vpi_table(code, from, to)", "–",
         "offen (GENESIS-API, Token)"],
    ], [2.8, 4.9, 2.7, 1.9], size=12, row_h=0.75)
    textbox(s, 0.5, 6.25, 12.3, 0.7, "Start: poetry run real-basket-mcp [--transport streamable-http --port 8001] "
            "[--areas data,analysis]. Nur echte Daten: jedes Tool liefert Datenbasis, Quell-PDFs und Prüfergebnisse "
            "mit; fehlen die PDFs, kommt ein Fehler statt Zahlen.", 13, GREY)

    s = slide(prs, "Ein MCP-Server statt mehrerer", "Entscheidung für den Hackathon – Aufteilung bleibt jederzeit "
              "möglich")
    box(s, 0.5, 1.35, 6.0, 0.55, "Warum ein Server", (), TEAL, size=16)
    bullets(s, 0.5, 2.0, 6.0, 4.4, [
        "MCP erlaubt beliebig viele Tools, Resources und Prompts je Server",
        "Ein Prozess: PDFs werden nur einmal geparst, schnellerer Start",
        "Ein Eintrag in Claude Desktop / VS Code, eine URL (MCP_URL)",
        "Weniger Betrieb und Konfiguration für die Demo",
        "Fach-Agenten erhalten per Filter nur ihre Tools (z. B. nur data)",
    ], 16)
    box(s, 6.8, 1.35, 6.0, 0.55, "Wann aufteilen", (), ORANGE, size=16)
    bullets(s, 6.8, 2.0, 6.0, 4.4, [
        "Least Privilege: nur knowledge braucht den LLM-Schlüssel (Embeddings)",
        "Unabhängige Skalierung, z. B. Berichte (report)",
        "Externe Quellen mit eigenem Token (destatis-genesis)",
        "Andere Teams übernehmen einzelne Bereiche",
        "Technisch: --areas bzw. ein Einstiegspunkt je Bereich – Tool-Namen bleiben gleich",
    ], 16)

    s = slide(prs, "A2A-Agenten im Detail", "Jeder Agent veröffentlicht eine Agent Card unter "
              "/.well-known/agent-card.json")
    table(s, 0.5, 1.45, 12.3, [
        ["Agent", "Skills (Agent Card)", "nutzt MCP-Bereiche", "Ergebnis (Artefakt)"],
        ["Orchestrator", "Lebenshaltung vs. VPI erklären · Fragen an Fach-Agenten verteilen",
         "– (delegiert)", "Antwort auf Deutsch + Disclaimer"],
        ["Price-Collector", "Preise je Ausgabengruppe sammeln und zusammenfassen", "data",
         "Preisübersicht je Gruppe"],
        ["Abweichungs-Analyst", "Einflussfaktoren · Stadtmieten · Abdeckung je Bundesland",
         "data, analysis", "Beiträge in PP, Tabellen"],
        ["Methodik-Agent", "Methodenhinweise und Grenzen mit Zitat erklären", "knowledge",
         "Zitate (Datei, Seite)"],
        ["Report-Agent", "PDF-Berichte erstellen", "report, data", "PDF als Artefakt"],
    ], [2.4, 4.6, 2.8, 2.5], size=13, row_h=0.72)
    textbox(s, 0.5, 6.0, 12.3, 0.9, "Lang laufende Aufgaben (z. B. Berichte) als A2A-Task mit Status-Updates "
            "per SSE; Ergebnisse als Artefakte statt Freitext.", 13, GREY)

    s = slide(prs, "Ablauf einer Frage in der Zielarchitektur",
              "Beispiel: „Warum liegt der Grundbedarf über dem VPI und was sagt die Methodik dazu?“")
    flow(s, [
        ("Client", ["Streamlit / Teams sendet", "A2A-Nachricht an den", "Orchestrator"]),
        ("Planung", ["Orchestrator liest Agent", "Cards und verteilt", "Teilaufgaben"]),
        ("Analyse", ["Abweichungs-Analyst ruft", "calculate_index und", "investigate_deviation (MCP)"]),
        ("Methodik", ["Methodik-Agent ruft", "search_methodology (MCP),", "parallel zur Analyse"]),
        ("Zusammenführen", ["Orchestrator kombiniert", "Artefakte, prüft", "Quellen + Prüfungen"]),
        ("Antwort", ["Deutsch, Zahlen + Zitate,", "Disclaimer, gestreamt", "per SSE"]),
    ], y=1.7, h=2.3, fills=[NAVY, TEAL, PURPLE, PURPLE, TEAL, NAVY], size=13)
    bullets(s, 0.5, 4.5, 12.3, 2.4, [
        "Die Zahlen stammen ausschließlich aus MCP-Tools – kein Agent rechnet selbst",
        "Unabhängige Teilaufgaben laufen parallel (Analyse und Methodik)",
        "Durchgängiges Tracing über A2A- und MCP-Grenzen (OpenTelemetry, in Strands integriert)",
    ], 16)

    s = slide(prs, "Abbildung Ist → Ziel", "Stand November 2026: Phase 1 (MCP) umgesetzt, Phase 2 (A2A) offen")
    table(s, 0.5, 1.4, 12.3, [
        ["Vorher", "Ziel", "Protokoll", "Status"],
        ["agents/tools.py: fetch_prices, fetch_official_cpi, calculate_essential_vs_cpi",
         "MCP-Server realbasket, Bereich data", "MCP", "umgesetzt"],
        ["agents/tools.py: investigate_deviation, fetch_regional_rents",
         "Bereich analysis (get_regional_rents)", "MCP", "umgesetzt"],
        ["agents/tools.py: search_methodology + knowledge/", "Bereich knowledge (Tools, Resource, Prompt)",
         "MCP", "umgesetzt"],
        ["ui/app.py: PDF-Download über reports/pdf_report.py", "Bereich report + Report-Agent",
         "MCP / A2A", "offen"],
        ["Collector-Sub-Agent (entfernt 11/2026; get_prices liefert die Zusammenfassung)",
         "Price-Collector als eigener Dienst, sobald es Live-Quellen gibt", "A2A", "offen"],
        ["Orchestrator im Streamlit-Prozess", "Orchestrator-Dienst (A2A-Server)", "A2A", "offen"],
        ["Streamlit ruft den Agenten direkt auf", "Streamlit als A2A-Client; Dashboard über MCP",
         "A2A / MCP", "offen"],
        ["core/, data/, Tests", "unverändert; Tests inkl. MCP-Contract-Tests, CI", "–", "umgesetzt"],
    ], [5.0, 4.2, 1.3, 1.8], size=13, row_h=0.58)

    s = slide(prs, "Umsetzung mit Strands und dem MCP-SDK", "Links umgesetzt (mcp_servers/server.py), "
              "Mitte und rechts Skizze für Phase 2")
    code = [
        ("MCP-Server realbasket (umgesetzt)", [
            "server = MCPServer(\"realbasket\")",
            "for area in (data_tools,",
            "             analysis_tools,",
            "             knowledge_tools):",
            "    area.register(server)",
            "",
            "server.run(\"stdio\")",
            "# or \"streamable-http\",",
            "#      port=8001"]),
        ("Fach-Agent als A2A-Dienst mit MCP-Tools", [
            "mcp = MCPClient(url=",
            "    \"http://realbasket-mcp:8001/mcp\")",
            "with mcp:",
            "    collector = Agent(",
            "        name=\"price-collector\",",
            "        model=create_model(),",
            "        tools=mcp.list_tools_sync())",
            "    A2AServer(agent=collector,",
            "              port=9001).serve()"]),
        ("Orchestrator ruft A2A-Agenten", [
            "agents = A2AClientToolProvider(",
            "    known_agent_urls=[",
            "        \"http://collector:9001\",",
            "        \"http://analyst:9002\",",
            "        \"http://methodik:9003\"])",
            "",
            "orchestrator = Agent(",
            "    system_prompt=ORCHESTRATOR_PROMPT,",
            "    tools=agents.tools)"]),
    ]
    for i, (t, lines) in enumerate(code):
        x = 0.5 + i * 4.15
        box(s, x, 1.45, 4.0, 0.5, t, (), PURPLE if i == 0 else TEAL, size=13)
        box(s, x, 2.0, 4.0, 3.9, "", lines, LIGHT, border=GREY, size=13, align=PP_ALIGN.LEFT, font="Consolas")
    textbox(s, 0.5, 6.1, 12.3, 0.8, "Pakete: mcp (MCPServer, stdio / Streamable HTTP) · strands.tools.mcp.MCPClient · "
            "Phase 2: strands-agents[a2a] (A2AServer) · strands-agents-tools (A2AClientToolProvider)", 12, GREY)

    s = slide(prs, "Querschnittsthemen")
    for i, (t, items, fill) in enumerate([
        ("Sicherheit", ["Entra ID / OAuth 2.1 für MCP-HTTP und A2A", "Auth-Schemata in der Agent Card",
                        "Schlüssel in Azure Key Vault statt .env",
                        "Least Privilege: Bereiche bei Bedarf als eigene Server (--areas)"], NAVY),
        ("Determinismus & Qualität", ["Zahlen nur aus MCP-Tools", "Prüfergebnisse als Resource",
                                      "Contract-Tests je Tool-Schema (umgesetzt)",
                                      "Zahlen-Guardrail für Antworten (umgesetzt)"], TEAL),
        ("Betrieb", ["Je Dienst ein Container (Azure Container Apps)", "Health-Checks, unabhängige Skalierung",
                     "OpenTelemetry-Tracing über alle Hops", "Versionierte Agent Cards und Tools"], PURPLE),
    ]):
        x = 0.5 + i * 4.15
        box(s, x, 1.4, 4.0, 0.6, t, (), fill, size=17)
        bullets(s, x, 2.15, 4.0, 4.7, items, 16)

    s = slide(prs, "Roadmap und Empfehlung")
    for i, (t, b, fill) in enumerate([
        ("Phase 1 · umgesetzt ✓", ["Ein MCP-Server realbasket", "Bereiche data · analysis · knowledge",
                                   "Agent nutzt MCPClient (stdio / HTTP)", "Tests + CI grün",
                                   "Nutzbar in Claude Desktop / VS Code"], PURPLE),
        ("Phase 2 · nach dem Hackathon", ["Bereich report + Report-Agent", "Collector, Analyst, Methodik als",
                                          "A2A-Dienste mit Agent Cards", "Orchestrator als A2A-Server",
                                          "Streamlit als A2A-Client"], TEAL),
        ("Phase 3 · Produktion", ["destatis-genesis-MCP (Live-VPI)", "Neue Quellen: Ländermieten, Gehälter",
                                  "Entra ID, Key Vault, Container Apps", "OpenTelemetry, Monitoring"], NAVY),
    ]):
        x = 0.5 + i * 4.15
        box(s, x, 1.4, 4.0, 2.9, t, ["", *b], fill, size=16)
        if i < 2:
            arrow(s, x + 4.0, 2.85, x + 4.15, 2.85, NAVY)
    box(s, 0.5, 4.6, 6.0, 0.5, "Vorteile", (), TEAL, size=15)
    bullets(s, 0.5, 5.15, 6.0, 1.9, ["Wiederverwendbar und interoperabel", "Einzeln skalier- und deploybar",
                                    "Klare Schnittstellen, gleicher Rechenkern"], 14)
    box(s, 6.8, 4.6, 6.0, 0.5, "Aufwand / Risiken", (), ORANGE, size=15)
    bullets(s, 6.8, 5.15, 6.0, 1.9, ["Mehr Dienste, mehr Betrieb", "Zusätzliche Latenz je Netzwerk-Hop",
                                    "Auth und Versionierung nötig – für den Hackathon genügt Phase 1"], 14)
    return prs


DECKS = {
    "de": {"current": "RealBasket_Architektur_Ist.pptx", "proposal": "RealBasket_Architektur_Vorschlag_MCP_A2A.pptx"},
    "en": {"current": "RealBasket_Architecture_Current.pptx",
           "proposal": "RealBasket_Architecture_Proposal_MCP_A2A.pptx"},
}


def main() -> None:
    global LANG
    FACTS.update(facts())
    built = {}
    for lang, files in DECKS.items():
        LANG = lang
        built[files["current"]], built[files["proposal"]] = current_deck(), proposal_deck()
    LANG = "de"
    if MISSING:
        missing = "\n".join(f"    {t!r}: \"\"," for t in dict.fromkeys(MISSING))
        raise SystemExit(f"{len(set(MISSING))} texts without English translation (add to texts_en.py):\n"
                         f"{missing}")
    locked = []
    for name, prs in built.items():
        try:
            prs.save(OUT / name)
        except PermissionError:
            locked.append(name)
    if locked:
        raise SystemExit(f"Close these files in PowerPoint and run again: {', '.join(locked)}")
    unused = sorted(set(EN) - USED)
    if unused:
        print(f"Note: {len(unused)} unused entries in texts_en.EN (can be removed): {unused}")
    print(f"Decks (de, en) written to {OUT} - result {FACTS['period']}: {FACTS['essential']} % vs. "
          f"{FACTS['cpi']} %, {FACTS['checks_ok']}/{FACTS['checks']} checks")


if __name__ == "__main__":
    main()
