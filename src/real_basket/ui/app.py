"""Streamlit UI. Run with: poetry run streamlit run src/real_basket/ui/app.py"""

import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from real_basket.agents.prompts import DISCLAIMER
from real_basket.core.income import DEFAULT_FLAT_SIZE_M2, average_salaries, rent_burden
from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.core.investigation import deviation_breakdown
from real_basket.core.rents import TOTAL_COL, average_rents, overall_average
from real_basket.core.settings import get_settings
from real_basket.data.demo_data import demo_cpi, demo_net_salaries, demo_prices, demo_regional_rents
from real_basket.schemas.models import BasketWeights, Category, RegionType

CATEGORY_LABEL = {"food": "🍞 Food", "rent": "🏠 Rent", "energy": "⚡ Energy", "mobility": "🚆 Mobility"}
EXAMPLE_QUESTIONS = [
    "Are basic living costs rising faster than official inflation? Why?",
    "In welchem Bundesland ist die Mietbelastung am höchsten?",
    "Is 'Wohnen / Energie' in the reference reports the net cold rent?",
    "Which rents in the largest cities rose the most?",
]

st.set_page_config(page_title="RealBasket", page_icon="🧺", layout="wide")


# --- Cached data (demo data is deterministic; caching keeps the demo snappy) ---------------------
@st.cache_data
def load_prices():
    return demo_prices()


@st.cache_data
def load_cpi():
    return demo_cpi()


@st.cache_data
def load_rents(region_type: str):
    return demo_regional_rents(region_type=RegionType(region_type))


@st.cache_data
def load_incomes():
    return demo_net_salaries()


@st.cache_data(show_spinner="Generating PDF reports...")
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
st.sidebar.header("Basket weights")
w_food = st.sidebar.slider("Food", 0.0, 1.0, 0.30, 0.05)
w_rent = st.sidebar.slider("Rent", 0.0, 1.0, 0.40, 0.05)
w_energy = st.sidebar.slider("Energy", 0.0, 1.0, 0.15, 0.05)
w_mob = st.sidebar.slider("Mobility", 0.0, 1.0, 0.15, 0.05)
total = w_food + w_rent + w_energy + w_mob
if total == 0:
    st.sidebar.error("At least one weight must be > 0.")
    st.stop()
weights = BasketWeights(weights={
    Category.FOOD: w_food / total, Category.RENT: w_rent / total,
    Category.ENERGY: w_energy / total, Category.MOBILITY: w_mob / total,
})
st.sidebar.caption(f"Weights are normalised to 100 % (raw sum: {total:.2f}). Data: demo")

st.sidebar.header("📄 PDF reports")
if st.sidebar.button("Prepare PDFs (German, EUR)"):
    st.session_state.pdfs = build_pdfs()
for name, data in st.session_state.get("pdfs", {}).items():
    st.sidebar.download_button(name, data, file_name=name, mime="application/pdf", key=f"dl_{name}")

settings = get_settings()
has_key = bool(settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-..."))
st.sidebar.header("⚙️ Status")
st.sidebar.write(("✅" if has_key else "⚠️") + f" Agent: {settings.OPENAI_MODEL_ID}"
                 + ("" if has_key else " (no OPENAI_API_KEY)"))

# --- Header: the story in one screen --------------------------------------------------------------
st.title("🧺 RealBasket")
st.caption("What does living really cost? Essential living cost index vs. official Consumer Price Index (CPI)")

prices, cpi = load_prices(), load_cpi()
comparison = compare_with_cpi(essential_index(prices, weights), cpi)
breakdown = deviation_breakdown(prices, cpi, weights)
driver = breakdown["categories"][0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Essential inflation (YoY)", f"{breakdown['essential_yoy_pct']:.2f} %")
c2.metric("Official CPI (YoY)", f"{breakdown['cpi_yoy_pct']:.2f} %")
c3.metric("Deviation", f"{breakdown['deviation_pp']:+.2f} pp")
c4.metric("Biggest driver", CATEGORY_LABEL[driver["category"]], f"{driver['gap_pp']:+.2f} pp", delta_color="inverse")
st.info(f"Stand {pd.Timestamp(breakdown['period']):%m/%Y} · demo data · {DISCLAIMER}")

tab_overview, tab_drivers, tab_rent, tab_income, tab_method, tab_agent = st.tabs(
    ["📈 Index vs. CPI", "🧩 Drivers", "🏠 Miete regional", "💶 Nettogehalt", "📚 Method notes (RAG)",
     "🤖 Ask the agent"])

with tab_overview:
    col_idx, col_yoy = st.columns(2)
    col_idx.plotly_chart(px.line(comparison[["essential_index", "cpi_index"]], title="Index (base month = 100)",
                                 labels={"value": "Index", "period": ""}), width="stretch")
    yoy = comparison[["essential_yoy_pct", "cpi_yoy_pct", "deviation_pp"]].dropna()
    col_yoy.plotly_chart(px.line(yoy, title="YoY rates and deviation", labels={"value": "%", "period": ""}),
                         width="stretch")

with tab_drivers:
    st.caption("Why does essential inflation deviate from the CPI? gap_pp = contribution of the category minus its "
               "weight × CPI rate; the gaps add up to the deviation.")
    drv = pd.DataFrame(breakdown["categories"]).set_index("category")
    drv.index = drv.index.map(CATEGORY_LABEL)
    col_gap, col_cat = st.columns(2)
    col_gap.plotly_chart(px.bar(drv, x=drv.index, y="gap_pp", color="gap_pp", color_continuous_scale="RdBu_r",
                                color_continuous_midpoint=0, title="Contribution to the deviation (pp)",
                                labels={"x": "", "gap_pp": "pp"}), width="stretch")
    col_cat.plotly_chart(px.line(category_indices(prices), title="Index per category (base month = 100)",
                                 labels={"value": "Index", "period": ""}), width="stretch")
    st.dataframe(drv.rename(columns={"weight": "Weight", "yoy_pct": "YoY %", "contribution_pp": "Contribution pp",
                                     "gap_pp": "Gap to CPI pp"}), width="stretch")

with tab_rent:
    level = st.radio("Ebene", ["Bundesländer", "Größte Städte"], horizontal=True)
    rtype = RegionType.STATE if level == "Bundesländer" else RegionType.CITY
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
               "Demo-Daten (grobe Größenordnung)")
    m1, m2, m3 = st.columns(3)
    scope = "Bundesländer" if rtype == RegionType.STATE else "Städte"
    m1.metric(f"Ø Miete alle {scope} (aktuell)", f"{latest_rent.mean():.2f} €/m²")
    m2.metric(f"Ø Miete alle {scope} (Zeitraum)", f"{avg_table[TOTAL_COL].mean():.2f} €/m²")
    m3.metric("Spanne (aktuell)", f"{latest_rent.min():.2f} – {latest_rent.max():.2f} €/m²")
    st.caption("Ø alle Regionen = ungewichteter Mittelwert (nicht nach Einwohnern gewichtet).")
    st.plotly_chart(px.bar(summary, x=summary.index, y="Miete €/m²", color="Veränderung ggü. Vorjahr %",
                           color_continuous_scale="Reds", labels={"x": ""}), width="stretch")
    col_tbl, col_line = st.columns([1, 2])
    col_tbl.dataframe(summary, width="stretch")
    selected = col_line.multiselect("Regionen vergleichen", list(summary.index), default=list(summary.index[:3]))
    if selected:
        col_line.plotly_chart(
            px.line(rent_df[rent_df["region"].isin(selected)], x="period", y="price", color="region",
                    labels={"price": "€/m²", "period": ""}), width="stretch")

    with st.expander(f"Ø Miete pro Jahr – {level}"):
        avg_display = avg_table.copy()
        avg_display.loc["Ø alle Regionen"] = overall_average(avg_table)
        st.dataframe(avg_display.style.format("{:.2f} €"), width="stretch")

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
    i1.metric("Ø Nettogehalt alle Bundesländer", f"{salary_tbl[TOTAL_COL].mean():,.0f} €".replace(",", "."))
    i2.metric("Spanne Nettogehalt",
              f"{salary_tbl[TOTAL_COL].min():,.0f} – {salary_tbl[TOTAL_COL].max():,.0f} €".replace(",", "."))
    i3.metric(f"Ø Mietbelastung ({flat} m²)", f"{burden_tbl[TOTAL_COL].mean():.1f} %")

    col_sal, col_bur = st.columns(2)
    col_sal.plotly_chart(px.bar(salary_tbl, x=salary_tbl.index, y=TOTAL_COL, title="Ø Nettogehalt (€/Monat)",
                                labels={"x": "", TOTAL_COL: "€"}), width="stretch")
    col_bur.plotly_chart(px.bar(burden_tbl, x=burden_tbl.index, y=TOTAL_COL, color=TOTAL_COL,
                                color_continuous_scale="Reds",
                                title=f"Mietbelastung: Miete {flat} m² in % vom Nettogehalt",
                                labels={"x": "", TOTAL_COL: "%"}), width="stretch")

    with st.expander("Ø Nettogehalt und Mietbelastung pro Jahr"):
        sal_display = salary_tbl.copy()
        sal_display.loc["Ø alle Bundesländer"] = salary_tbl.mean(axis=0)
        st.dataframe(sal_display.style.format("{:,.0f} €"), width="stretch")
        bur_display = burden_tbl.copy()
        bur_display.loc["Ø alle Bundesländer"] = burden_tbl.mean(axis=0)
        st.dataframe(bur_display.style.format("{:.1f} %"), width="stretch")

with tab_method:
    st.caption("Retrieval over the method notes and caveats of unstructured reference PDFs (`reports/real-data`). "
               "Context only – figures never come from text search.")
    try:
        kb = knowledge_base()
        kb_status = kb.status()
        k1, k2, k3 = st.columns(3)
        k1.metric("Documents", len(kb_status["documents"]))
        k2.metric("Passages", f"{kb_status['notes']} notes + {kb_status['tables']} tables")
        k3.metric("Retriever", kb_status["retriever"])
        kq = st.text_input("Search", placeholder="e.g. Ist Wohnen / Energie die Nettokaltmiete?")
        if kq:
            hits = kb.search(kq)["passages"]
            for p in hits:
                also = f" · also in {', '.join(p['also_in'])}" if p["also_in"] else ""
                st.markdown(f"**{p['source']} p. {p['page']}** · {p['section']}{also}\n\n> {p['text']}")
            if not hits:
                st.info("No matching passages.")
    except Exception as exc:  # noqa: BLE001 - the dashboard must work without documents
        st.error(f"Method-note index unavailable: {exc}")


def _tools_used(messages: list) -> list[str]:
    names = []
    for msg in messages:
        for block in msg.get("content", []) if isinstance(msg, dict) else []:
            if isinstance(block, dict) and "toolUse" in block:
                names.append(block["toolUse"].get("name", "?"))
    return names


with tab_agent:
    if not has_key:
        st.warning("Set OPENAI_API_KEY in `.env` to chat with the agent.")
    st.session_state.setdefault("messages", [])
    cols = st.columns(len(EXAMPLE_QUESTIONS) + 1)
    for col, q in zip(cols, EXAMPLE_QUESTIONS):
        if col.button(q, width="stretch"):
            st.session_state.pending = q
    if cols[-1].button("🗑️ New chat", width="stretch"):
        st.session_state.messages = []
        st.session_state.pop("agent", None)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools"):
                st.caption("🔧 " + " → ".join(msg["tools"]))

    prompt = st.chat_input("e.g. Are basic living costs rising faster than official inflation?")
    prompt = prompt or st.session_state.pop("pending", None)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        with st.chat_message("assistant"), st.spinner("The agent is choosing tools and analysing..."):
            try:
                if "agent" not in st.session_state:       # one agent per session -> follow-up questions work
                    from real_basket.agents.orchestrator import create_orchestrator

                    st.session_state.agent = create_orchestrator()
                agent = st.session_state.agent
                before = len(agent.messages)
                answer = str(agent(prompt))
                tools = _tools_used(agent.messages[before:])
            except Exception as exc:  # noqa: BLE001 - show the error instead of crashing the demo
                answer, tools = f"⚠️ Agent error: {exc}", []
            st.markdown(answer)
            if tools:
                st.caption("🔧 " + " → ".join(tools))
        st.session_state.messages.append({"role": "assistant", "content": answer, "tools": tools})
