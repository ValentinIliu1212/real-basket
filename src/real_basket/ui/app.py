"""Streamlit-Oberfläche. Start: poetry run streamlit run src/real_basket/ui/app.py"""

import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from real_basket.agents.prompts import DISCLAIMER
from real_basket.core import llm
from real_basket.core.income import DEFAULT_FLAT_SIZE_M2, average_salaries, rent_burden
from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.core.investigation import deviation_breakdown
from real_basket.core.rents import TOTAL_COL, average_rents, overall_average
from real_basket.core.settings import get_settings
from real_basket.data.basket import Basket, load_basket, set_data_source
from real_basket.data.demo_data import demo_net_salaries, demo_regional_rents
from real_basket.data.real_data import real_data_dir
from real_basket.schemas.models import CATEGORY_LABEL_DE, BasketWeights, Category, RegionType

ICON = {Category.FOOD: "🍞", Category.RENT: "🏠", Category.ENERGY: "⚡", Category.MOBILITY: "🚆",
        Category.HOUSING_ENERGY: "🏠", Category.HEALTH: "💊", Category.COMMUNICATION: "📱"}
CATEGORY_LABEL = {c.value: f"{ICON[c]} {CATEGORY_LABEL_DE[c]}" for c in Category}
SERIES_LABEL = {"essential_index": "Grundlebenshaltungskosten", "cpi_index": "Verbraucherpreisindex (VPI)",
                "essential_yoy_pct": "Grundlebenshaltungskosten ggü. Vorjahr %", "cpi_yoy_pct": "VPI ggü. Vorjahr %",
                "deviation_pp": "Abweichung (Prozentpunkte)"}
EXAMPLE_QUESTIONS = [
    "Steigen die Grundlebenshaltungskosten schneller als die offizielle Inflation? Warum?",
    "In welchem Bundesland ist die Mietbelastung am höchsten?",
    "Ist „Wohnen / Energie“ in den Referenzberichten die Nettokaltmiete?",
    "In welchen Großstädten sind die Mieten am stärksten gestiegen?",
]
SOURCE_OPTIONS = {"Echte Daten (Referenz-PDFs)": "real", "Demo-Daten (synthetisch)": "demo"}

st.set_page_config(page_title="RealBasket", page_icon="🧺", layout="wide")


def de(value: float, digits: int = 2) -> str:
    """German number format: 1234.5 -> '1.234,50'."""
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --- Cached data ----------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Lese Referenz-PDFs ...")
def get_basket(source: str) -> Basket:
    return load_basket(source)


@st.cache_data
def load_rents(region_type: str):
    return demo_regional_rents(region_type=RegionType(region_type))


@st.cache_data
def load_incomes():
    return demo_net_salaries()


@st.cache_data(show_spinner="Erzeuge PDF-Berichte ...")
def build_pdfs() -> dict[str, bytes]:
    from real_basket.reports.pdf_report import (generate_average_rent_report, generate_cpi_report,
                                                generate_salary_report, generate_yearly_price_reports)

    with tempfile.TemporaryDirectory() as tmp:
        files = [*generate_yearly_price_reports(tmp), generate_average_rent_report(tmp),
                 generate_salary_report(tmp), generate_cpi_report(tmp)]
        return {Path(f).name: Path(f).read_bytes() for f in files}


@st.cache_resource
def knowledge_base():
    from real_basket.knowledge import KnowledgeBase

    return KnowledgeBase()


# --- Sidebar ----------------------------------------------------------------------------------
st.sidebar.header("📊 Datenquelle")
choice = st.sidebar.radio("Warenkorb", list(SOURCE_OPTIONS), label_visibility="collapsed")
basket = get_basket(SOURCE_OPTIONS[choice])
if SOURCE_OPTIONS[choice] == "real" and basket.source != "real":
    st.sidebar.error(f"Echte Daten nicht verfügbar – Demo-Daten werden verwendet. Grund: {basket.error}")
st.sidebar.caption(basket.label)

st.sidebar.header("⚖️ Gewichte des Warenkorbs")
defaults = {c: round(basket.weights.weights[c], 2) for c in basket.categories}
raw = {c: st.sidebar.slider(CATEGORY_LABEL[c.value], 0.0, 1.0, defaults[c], 0.01, key=f"w_{basket.source}_{c.value}")
       for c in basket.categories}
total = sum(raw.values())
if total == 0:
    st.sidebar.error("Mindestens ein Gewicht muss > 0 sein.")
    st.stop()
# untouched sliders -> exact (unrounded) default weights, so the dashboard matches the agent and the PDFs
untouched = all(abs(raw[c] - defaults[c]) < 1e-9 for c in basket.categories)
weights = basket.weights if untouched else BasketWeights(weights={c: v / total for c, v in raw.items()})
default_note = ("Standard = Ausgabenanteile des ECLI-Referenzwarenkorbs (Destatis EVS 2023)"
                if basket.source == "real" else "Standard = Demo-Gewichte")
st.sidebar.caption(f"Gewichte werden auf 100 % normiert (Summe: {de(total)}). {default_note}."
                   + ("" if untouched else " Der Agent rechnet mit den Standardgewichten, sofern nicht anders "
                                           "gefragt."))

st.sidebar.header("📄 PDF-Berichte")
ref_pdfs = sorted(real_data_dir().glob("*.pdf")) if real_data_dir().is_dir() else []
if ref_pdfs:
    st.sidebar.caption("Referenzberichte (Quelle der echten Daten):")
    for f in ref_pdfs:
        st.sidebar.download_button(f.name, f.read_bytes(), file_name=f.name, mime="application/pdf",
                                   key=f"ref_{f.name}")
if st.sidebar.button("Demo-Berichte erzeugen (Deutsch, EUR)"):
    st.session_state.pdfs = build_pdfs()
for name, data in st.session_state.get("pdfs", {}).items():
    st.sidebar.download_button(name, data, file_name=name, mime="application/pdf", key=f"dl_{name}")

settings = get_settings()
has_key = llm.is_configured(settings)
st.sidebar.header("⚙️ Status")
st.sidebar.write(("✅" if has_key else "⚠️") + f" Agent: {llm.provider_label(settings)}"
                 + ("" if has_key else " (kein API-Key / Endpoint)"))

# --- Header: the story in one screen --------------------------------------------------------------
st.title("🧺 RealBasket")
st.caption("Was kostet das Leben wirklich? Index der Grundlebenshaltungskosten im Vergleich zum offiziellen "
           "Verbraucherpreisindex (VPI)")

prices, cpi = basket.prices, basket.cpi
comparison = compare_with_cpi(essential_index(prices, weights), cpi)
breakdown = deviation_breakdown(prices, cpi, weights)
driver = breakdown["categories"][0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Grundlebenshaltungskosten (ggü. Vorjahr)", f"{de(breakdown['essential_yoy_pct'])} %")
c2.metric("Offizieller VPI (ggü. Vorjahr)", f"{de(breakdown['cpi_yoy_pct'])} %")
c3.metric("Abweichung", f"{'+' if breakdown['deviation_pp'] >= 0 else ''}{de(breakdown['deviation_pp'])} PP")
c4.metric("Größter Treiber", CATEGORY_LABEL[driver["category"]],
          f"{'+' if driver['gap_pp'] >= 0 else ''}{de(driver['gap_pp'])} PP", delta_color="inverse")
data_note = "echte Daten" if basket.source == "real" else "Demo-Daten"
st.info(f"Stand {pd.Timestamp(breakdown['period']):%m/%Y} · {data_note} · {DISCLAIMER}")

if basket.real is not None:
    ok = basket.real.all_checks_ok
    with st.expander(("✅" if ok else "⚠️") + f" Datenprüfung: {sum(c.ok for c in basket.real.checks)} von "
                     f"{len(basket.real.checks)} Prüfungen bestanden · {len(basket.real.documents)} Referenz-PDFs"):
        st.caption("Die Zahlen werden deterministisch aus den Tabellen der Referenz-PDFs gelesen (kein LLM) und im "
                   "Code nachgerechnet.")
        st.dataframe(pd.DataFrame([{"": "✅" if c.ok else "❌", "Prüfung": c.name, "Details": c.detail}
                                   for c in basket.real.checks]), hide_index=True, width="stretch")
        base = pd.DataFrame([{"Ausgabengruppe": CATEGORY_LABEL_DE[c], "Basisbetrag €/Monat (11/2024)": de(v),
                              "Gewicht": f"{de(v / basket.real.base_total * 100, 1)} %"}
                             for c, v in basket.real.base_amounts.items()])
        st.dataframe(base, hide_index=True, width="stretch")
        st.caption("Quellen: " + ", ".join(basket.real.documents))

tab_overview, tab_drivers, tab_rent, tab_income, tab_method, tab_agent = st.tabs(
    ["📈 Index vs. VPI", "🧩 Einflussfaktoren", "🏠 Miete regional", "💶 Nettogehalt", "📚 Methodenhinweise (RAG)",
     "🤖 Chat mit RealBasket"])

with tab_overview:
    col_idx, col_yoy = st.columns(2)
    base_month = f"{comparison.index[0]:%m/%Y}"
    col_idx.plotly_chart(px.line(comparison[["essential_index", "cpi_index"]].rename(columns=SERIES_LABEL),
                                 title=f"Index ({base_month} = 100)",
                                 labels={"value": "Index", "period": "", "variable": ""}), width="stretch")
    yoy = comparison[["essential_yoy_pct", "cpi_yoy_pct", "deviation_pp"]].dropna().rename(columns=SERIES_LABEL)
    col_yoy.plotly_chart(px.line(yoy, title="Veränderung ggü. Vorjahresmonat und Abweichung",
                                 labels={"value": "% bzw. PP", "period": "", "variable": ""}), width="stretch")
    if basket.real is not None:
        monthly = pd.DataFrame([p.model_dump() for p in prices]).pivot_table(index="period", columns="item",
                                                                              values="price")
        st.plotly_chart(px.area(monthly, title="Modellierte monatliche Kosten des Referenzwarenkorbs (€/Monat)",
                                labels={"value": "€/Monat", "period": "", "item": "Ausgabengruppe"}),
                        width="stretch")

with tab_drivers:
    st.caption("Warum weichen die Grundlebenshaltungskosten vom VPI ab? Beitrag zur Abweichung = Beitrag der "
               "Kategorie zur Teuerung minus Gewicht × VPI-Rate; die Beiträge ergeben zusammen die Abweichung.")
    drv = pd.DataFrame(breakdown["categories"]).set_index("category")
    drv.index = drv.index.map(CATEGORY_LABEL)
    col_gap, col_cat = st.columns(2)
    col_gap.plotly_chart(px.bar(drv, x=drv.index, y="gap_pp", color="gap_pp", color_continuous_scale="RdBu_r",
                                color_continuous_midpoint=0, title="Beitrag zur Abweichung (Prozentpunkte)",
                                labels={"x": "", "gap_pp": "PP"}), width="stretch")
    cat_idx = category_indices(prices).rename(columns=CATEGORY_LABEL)
    col_cat.plotly_chart(px.line(cat_idx, title=f"Index je Kategorie ({base_month} = 100)",
                                 labels={"value": "Index", "period": "", "category": "Kategorie"}), width="stretch")
    st.dataframe(drv.rename(columns={"weight": "Gewicht", "yoy_pct": "ggü. Vorjahr %",
                                     "contribution_pp": "Beitrag zur Teuerung PP",
                                     "gap_pp": "Beitrag zur Abweichung PP"}), width="stretch")

with tab_rent:
    level = st.radio("Ebene", ["Bundesländer", "Größte Städte"], horizontal=True)
    rtype = RegionType.STATE if level == "Bundesländer" else RegionType.CITY
    real_cities = basket.real.city_rents if basket.real is not None and rtype == RegionType.CITY else []
    if real_cities:
        city_df = pd.DataFrame(real_cities).set_index("city")
        summary = pd.DataFrame({
            "Bundesland": city_df["state"],
            "Miete Jan 2026 €/m²": city_df["rent_jan_eur_m2"],
            "Miete Okt 2026 €/m²": city_df["rent_oct_eur_m2"],
            "Veränderung %": city_df["change_pct"],
        }).sort_values("Miete Okt 2026 €/m²", ascending=False)
        st.caption("Angebotskaltmiete pro m² der 15 größten Städte, Januar vs. Oktober 2026 · echte Daten: "
                   f"{real_cities[0]['source']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Ø Miete alle Städte (Okt 2026)", f"{de(summary['Miete Okt 2026 €/m²'].mean())} €/m²")
        m2.metric("Ø Veränderung Jan–Okt 2026", f"{de(summary['Veränderung %'].mean(), 1)} %")
        m3.metric("Spanne (Okt 2026)", f"{de(summary['Miete Okt 2026 €/m²'].min())} – "
                                       f"{de(summary['Miete Okt 2026 €/m²'].max())} €/m²")
        st.plotly_chart(px.bar(summary, x=summary.index, y="Miete Okt 2026 €/m²", color="Veränderung %",
                               color_continuous_scale="Reds", labels={"city": ""}), width="stretch")
        st.dataframe(summary, width="stretch")
    else:
        regional_rents = load_rents(rtype.value)
        avg_table = average_rents(regional_rents, rtype)
        rent_df = pd.DataFrame([p.model_dump() for p in regional_rents])
        rent_df["period"] = pd.to_datetime(rent_df["period"])
        last, prev = rent_df["period"].max(), rent_df["period"].max() - pd.DateOffset(months=12)
        latest_rent = rent_df[rent_df["period"] == last].set_index("region")["price"]
        prev_rent = rent_df[rent_df["period"] == prev].set_index("region")["price"]
        summary = pd.DataFrame({
            "Miete €/m²": latest_rent.round(2),
            "Ø Miete €/m² (Zeitraum)": avg_table[TOTAL_COL].round(2),
            "Veränderung ggü. Vorjahr %": ((latest_rent / prev_rent - 1) * 100).round(2),
        }).sort_values("Miete €/m²", ascending=False)

        first = rent_df["period"].min()
        st.caption(f"Angebotsmiete nettokalt pro m², Stand {last:%m/%Y}, Ø über {first:%m/%Y}–{last:%m/%Y} · "
                   "Demo-Daten (grobe Größenordnung; die Referenzberichte enthalten keine verifizierten "
                   "Monatsreihen je Bundesland)")
        m1, m2, m3 = st.columns(3)
        scope = "Bundesländer" if rtype == RegionType.STATE else "Städte"
        m1.metric(f"Ø Miete alle {scope} (aktuell)", f"{de(latest_rent.mean())} €/m²")
        m2.metric(f"Ø Miete alle {scope} (Zeitraum)", f"{de(avg_table[TOTAL_COL].mean())} €/m²")
        m3.metric("Spanne (aktuell)", f"{de(latest_rent.min())} – {de(latest_rent.max())} €/m²")
        st.caption("Ø alle Regionen = ungewichteter Mittelwert (nicht nach Einwohnern gewichtet).")
        st.plotly_chart(px.bar(summary, x=summary.index, y="Miete €/m²", color="Veränderung ggü. Vorjahr %",
                               color_continuous_scale="Reds", labels={"x": "", "region": ""}), width="stretch")
        col_tbl, col_line = st.columns([1, 2])
        col_tbl.dataframe(summary, width="stretch")
        selected = col_line.multiselect("Regionen vergleichen", list(summary.index),
                                        default=list(summary.index[:3]))
        if selected:
            col_line.plotly_chart(
                px.line(rent_df[rent_df["region"].isin(selected)], x="period", y="price", color="region",
                        labels={"price": "€/m²", "period": "", "region": "Region"}), width="stretch")

        with st.expander(f"Ø Miete pro Jahr – {level}"):
            avg_display = avg_table.copy()
            avg_display.loc["Ø alle Regionen"] = overall_average(avg_table)
            st.dataframe(avg_display.style.format("{:.2f} €", decimal=","), width="stretch")

with tab_income:
    incomes = load_incomes()
    state_rents = load_rents(RegionType.STATE.value)
    salary_tbl = average_salaries(incomes)
    flat = st.slider("Wohnfläche für Mietbelastung (m²)", 30, 120, DEFAULT_FLAT_SIZE_M2, 5)
    burden_tbl = rent_burden(state_rents, incomes, flat)

    inc_first, inc_last = min(i.period for i in incomes), max(i.period for i in incomes)
    st.caption(f"Ø monatliches Nettogehalt (Vollzeit) pro Bundesland, {inc_first:%m/%Y}–{inc_last:%m/%Y} · "
               "Demo-Daten (grobe Größenordnung)")
    i1, i2, i3 = st.columns(3)
    i1.metric("Ø Nettogehalt alle Bundesländer", f"{de(salary_tbl[TOTAL_COL].mean(), 0)} €")
    i2.metric("Spanne Nettogehalt",
              f"{de(salary_tbl[TOTAL_COL].min(), 0)} – {de(salary_tbl[TOTAL_COL].max(), 0)} €")
    i3.metric(f"Ø Mietbelastung ({flat} m²)", f"{de(burden_tbl[TOTAL_COL].mean(), 1)} %")

    col_sal, col_bur = st.columns(2)
    col_sal.plotly_chart(px.bar(salary_tbl, x=salary_tbl.index, y=TOTAL_COL, title="Ø Nettogehalt (€/Monat)",
                                labels={"x": "", "region": "", TOTAL_COL: "€"}), width="stretch")
    col_bur.plotly_chart(px.bar(burden_tbl, x=burden_tbl.index, y=TOTAL_COL, color=TOTAL_COL,
                                color_continuous_scale="Reds",
                                title=f"Mietbelastung: Miete {flat} m² in % vom Nettogehalt",
                                labels={"x": "", "region": "", TOTAL_COL: "%"}), width="stretch")

    with st.expander("Ø Nettogehalt und Mietbelastung pro Jahr"):
        sal_display = salary_tbl.copy()
        sal_display.loc["Ø alle Bundesländer"] = salary_tbl.mean(axis=0)
        st.dataframe(sal_display.style.format("{:,.0f} €", decimal=",", thousands="."), width="stretch")
        bur_display = burden_tbl.copy()
        bur_display.loc["Ø alle Bundesländer"] = burden_tbl.mean(axis=0)
        st.dataframe(bur_display.style.format("{:.1f} %", decimal=","), width="stretch")

with tab_method:
    st.caption("Suche in den Methodenhinweisen und Einschränkungen der unstrukturierten Referenz-PDFs "
               "(`reports/real-data`). Nur Kontext – Zahlen stammen nie aus der Textsuche.")
    try:
        kb = knowledge_base()
        kb_status = kb.status()
        k1, k2, k3 = st.columns(3)
        k1.metric("Dokumente", len(kb_status["documents"]))
        k2.metric("Textstellen", f"{kb_status['notes']} Hinweise + {kb_status['tables']} Tabellen")
        k3.metric("Suchverfahren", kb_status["retriever"])
        if not kb_status["documents"]:
            st.warning(f"Keine PDFs gefunden in `{kb.doc_dir}`. Bitte die Referenzberichte dort ablegen "
                       "(oder KNOWLEDGE_DIR in `.env` setzen).")
        kq = st.text_input("Suche", placeholder="z. B. Ist Wohnen / Energie die Nettokaltmiete?")
        if kq:
            hits = kb.search(kq)["passages"]
            for p in hits:
                also = f" · auch in {', '.join(p['also_in'])}" if p["also_in"] else ""
                st.markdown(f"**{p['source']} S. {p['page']}** · {p['section']}{also}\n\n> {p['text']}")
            if not hits:
                st.info("Keine passenden Textstellen gefunden.")
    except Exception as exc:  # noqa: BLE001 - the dashboard must work without documents
        st.error(f"Index der Methodenhinweise nicht verfügbar: {exc}")


def _tools_used(messages: list) -> list[str]:
    names = []
    for msg in messages:
        for block in msg.get("content", []) if isinstance(msg, dict) else []:
            if isinstance(block, dict) and "toolUse" in block:
                names.append(block["toolUse"].get("name", "?"))
    return names


with tab_agent:
    if not has_key:
        st.warning("Für den Chat in `.env` setzen: OPENAI_API_KEY (OpenAI) oder OPENAI_API_TYPE=azure + "
                   "AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY + AZURE_COMPLETION_MODEL (Azure).")
    st.caption(f"Datenbasis des Agenten: {basket.label} (Auswahl in der Seitenleiste). Antworten auf Deutsch.")
    st.session_state.setdefault("messages", [])
    if st.session_state.get("agent_source") not in (None, basket.source):
        # data source switched -> fresh chat, otherwise the memory would mix real and demo numbers
        st.session_state.messages = []
        st.session_state.pop("agent", None)
        st.info("Datenquelle gewechselt – neuer Chat gestartet.")
    st.session_state.agent_source = basket.source
    cols = st.columns(len(EXAMPLE_QUESTIONS) + 1)
    for col, q in zip(cols, EXAMPLE_QUESTIONS):
        if col.button(q, width="stretch"):
            st.session_state.pending = q
    if cols[-1].button("🗑️ Neuer Chat", width="stretch"):
        st.session_state.messages = []
        st.session_state.pop("agent", None)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools"):
                st.caption("🔧 " + " → ".join(msg["tools"]))

    prompt = st.chat_input("z. B. Steigen die Grundlebenshaltungskosten schneller als die offizielle Inflation?")
    prompt = prompt or st.session_state.pop("pending", None)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        with st.chat_message("assistant"), st.spinner("Der Agent wählt Werkzeuge und analysiert ..."):
            try:
                if "agent" not in st.session_state:       # one agent per session -> follow-up questions work
                    from real_basket.agents.orchestrator import create_orchestrator

                    st.session_state.agent = create_orchestrator()
                agent = st.session_state.agent
                set_data_source(basket.source)      # the agent's tools use the data source of the sidebar
                before = len(agent.messages)
                answer = str(agent(prompt))
                tools = _tools_used(agent.messages[before:])
            except Exception as exc:  # noqa: BLE001 - show the error instead of crashing the demo
                answer, tools = f"⚠️ Fehler des Agenten: {exc}", []
            st.markdown(answer)
            if tools:
                st.caption("🔧 " + " → ".join(tools))
        st.session_state.messages.append({"role": "assistant", "content": answer, "tools": tools})
