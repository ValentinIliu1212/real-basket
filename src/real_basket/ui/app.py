"""Streamlit-Oberfläche. Start: poetry run streamlit run src/real_basket/ui/app.py"""

import tempfile
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from real_basket.agents.guardrail import unverified_figures, warning_text
from real_basket.agents.prompts import DISCLAIMER
from real_basket.core import llm
from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.core.investigation import STATE_NOTE, deviation_breakdown, state_rent_coverage
from real_basket.core.settings import get_settings
from real_basket.data.basket import Basket, RealDataError, load_basket
from real_basket.data.real_data import CITY_FLAT_M2, real_data_dir
from real_basket.schemas.models import CATEGORY_LABEL_DE, BasketWeights, Category
from real_basket.ui import monitoring as mon

ICON = {Category.FOOD: "🍞", Category.HOUSING_ENERGY: "🏠", Category.MOBILITY: "🚆", Category.HEALTH: "💊",
        Category.COMMUNICATION: "📱"}
CATEGORY_LABEL = {c.value: f"{ICON[c]} {CATEGORY_LABEL_DE[c]}" for c in Category}
SERIES_LABEL = {"essential_index": "Grundlebenshaltungskosten", "cpi_index": "Verbraucherpreisindex (VPI)",
                "essential_yoy_pct": "Grundlebenshaltungskosten ggü. Vorjahr %", "cpi_yoy_pct": "VPI ggü. Vorjahr %",
                "deviation_pp": "Abweichung (Prozentpunkte)"}
EXAMPLE_QUESTIONS = [
    "Steigen die Grundlebenshaltungskosten schneller als die offizielle Inflation? Warum?",
    "Was kostet eine 75-m²-Wohnung in München im Vergleich zu Leipzig?",
    "Ist „Wohnen / Energie“ in den Referenzberichten die Nettokaltmiete?",
    "In welchen Großstädten sind die Mieten am stärksten gestiegen?",
]

st.set_page_config(page_title="RealBasket", page_icon="🧺", layout="wide")


def de(value: float, digits: int = 2) -> str:
    """German number format: 1234.5 -> '1.234,50'."""
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


MAX_TRACES = 30


def record(trace: mon.Trace) -> None:
    """Store the use-case path of an interaction for the monitoring tab (latest first, per session)."""
    traces = st.session_state.setdefault("traces", [])
    traces.insert(0, trace)
    del traces[MAX_TRACES:]


# --- Cached data ----------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Lese Referenz-PDFs ...")
def get_basket() -> Basket:
    return load_basket()


@st.cache_data(show_spinner="Erzeuge PDF-Berichte ...")
def build_pdfs() -> dict[str, bytes]:
    from real_basket.reports.pdf_report import generate_all

    with tempfile.TemporaryDirectory() as tmp:
        return {Path(f).name: Path(f).read_bytes() for f in generate_all(tmp, get_basket())}


@st.cache_resource
def knowledge_base():
    from real_basket.knowledge import KnowledgeBase

    return KnowledgeBase()


# --- Sidebar ----------------------------------------------------------------------------------
st.sidebar.header("📊 Datenquelle")
try:
    basket = get_basket()
except (RealDataError, OSError, ValueError) as exc:
    st.title("🧺 RealBasket")
    st.error(f"Echte Daten nicht verfügbar: {exc}. Bitte die Referenz-PDFs in `{real_data_dir()}` ablegen "
             "(oder KNOWLEDGE_DIR in `.env` setzen). Es gibt keine Demo-Daten.")
    st.stop()
st.sidebar.caption(f"Echte Daten: {basket.label}")

st.sidebar.header("⚖️ Gewichte des Warenkorbs")
defaults = {c: round(basket.weights.weights[c], 2) for c in basket.categories}
raw = {c: st.sidebar.slider(CATEGORY_LABEL[c.value], 0.0, 1.0, defaults[c], 0.01, key=f"w_{c.value}")
       for c in basket.categories}
total = sum(raw.values())
if total == 0:
    st.sidebar.error("Mindestens ein Gewicht muss > 0 sein.")
    st.stop()
# untouched sliders -> exact (unrounded) default weights, so the dashboard matches the agent and the PDFs
untouched = all(abs(raw[c] - defaults[c]) < 1e-9 for c in basket.categories)
weights = basket.weights if untouched else BasketWeights(weights={c: v / total for c, v in raw.items()})
st.sidebar.caption(f"Gewichte werden auf 100 % normiert (Summe: {de(total)}). Standard = Ausgabenanteile des "
                   "ECLI-Referenzwarenkorbs (Destatis EVS 2023)."
                   + ("" if untouched else " Der Agent rechnet mit den Standardgewichten, sofern nicht anders "
                                           "gefragt."))

st.sidebar.header("📄 PDF-Berichte")
ref_pdfs = sorted(real_data_dir().glob("*.pdf")) if real_data_dir().is_dir() else []
if ref_pdfs:
    st.sidebar.caption("Referenzberichte (Quelle der echten Daten):")
    for f in ref_pdfs:
        st.sidebar.download_button(f.name, f.read_bytes(), file_name=f.name, mime="application/pdf",
                                   key=f"ref_{f.name}")
if st.sidebar.button("RealBasket-Berichte erzeugen (Deutsch, EUR)"):
    t0 = time.perf_counter()
    try:
        st.session_state.pdfs = build_pdfs()
        record(mon.pdf_trace(list(st.session_state.pdfs), time.perf_counter() - t0))
    except Exception as exc:  # recorded for monitoring, then shown as usual
        record(mon.pdf_trace([], time.perf_counter() - t0, error=str(exc)))
        raise
for name, data in st.session_state.get("pdfs", {}).items():
    st.sidebar.download_button(name, data, file_name=name, mime="application/pdf", key=f"dl_{name}")

settings = get_settings()
issues = llm.config_issues(settings)
has_key = not issues["errors"]
st.sidebar.header("⚙️ Status")
st.sidebar.write(("✅" if has_key else "⚠️") + f" Agent: {llm.provider_label(settings)}"
                 + ("" if has_key else " (nicht konfiguriert)"))
for problem in issues["errors"] + issues["warnings"]:
    st.sidebar.caption(f"⚠️ {problem}")

# --- Header: the story in one screen --------------------------------------------------------------
st.title("🧺 RealBasket")
st.caption("Was kostet das Leben wirklich? Index der Grundlebenshaltungskosten im Vergleich zum offiziellen "
           "Verbraucherpreisindex (VPI)")

prices, cpi = basket.prices, basket.cpi
t0 = time.perf_counter()
comparison = compare_with_cpi(essential_index(prices, weights), cpi)
breakdown = deviation_breakdown(prices, cpi, weights)
dashboard_sig = tuple(round(v, 4) for v in raw.values())
if st.session_state.get("dashboard_sig") != dashboard_sig:   # first load or weights changed (not every rerun)
    record(mon.dashboard_trace("dashboard_sig" in st.session_state, sum(c.ok for c in basket.real.checks),
                               len(basket.real.checks), time.perf_counter() - t0))
    st.session_state.dashboard_sig = dashboard_sig
driver = breakdown["categories"][0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Grundlebenshaltungskosten (ggü. Vorjahr)", f"{de(breakdown['essential_yoy_pct'])} %")
c2.metric("Offizieller VPI (ggü. Vorjahr)", f"{de(breakdown['cpi_yoy_pct'])} %")
c3.metric("Abweichung", f"{'+' if breakdown['deviation_pp'] >= 0 else ''}{de(breakdown['deviation_pp'])} PP",
          help="Aus den ungerundeten Raten berechnet; kann daher um 0,01 PP von der Differenz der gerundeten "
               "Werte abweichen.")
c4.metric("Größter Einflussfaktor", CATEGORY_LABEL[driver["category"]],
          f"{'+' if driver['gap_pp'] >= 0 else ''}{de(driver['gap_pp'])} PP", delta_color="inverse")
st.info(f"Stand {pd.Timestamp(breakdown['period']):%m/%Y} · echte Daten (ECLI-Referenzwarenkorb, Destatis) · "
        f"{DISCLAIMER}")

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

tab_overview, tab_drivers, tab_rent, tab_method, tab_agent, tab_monitor = st.tabs(
    ["📈 Index vs. VPI", "🧩 Einflussfaktoren", "🏠 Miete Städte", "📚 Methodenhinweise (RAG)",
     "🤖 Chat mit RealBasket", "🛰️ Monitoring"])

with tab_overview:
    col_idx, col_yoy = st.columns(2)
    base_month = f"{comparison.index[0]:%m/%Y}"
    col_idx.plotly_chart(px.line(comparison[["essential_index", "cpi_index"]].rename(columns=SERIES_LABEL),
                                 title=f"Index ({base_month} = 100)",
                                 labels={"value": "Index", "period": "", "variable": ""}), width="stretch")
    yoy = comparison[["essential_yoy_pct", "cpi_yoy_pct", "deviation_pp"]].dropna().rename(columns=SERIES_LABEL)
    col_yoy.plotly_chart(px.line(yoy, title="Veränderung ggü. Vorjahresmonat und Abweichung",
                                 labels={"value": "% bzw. PP", "period": "", "variable": ""}), width="stretch")
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
    real_cities = basket.real.city_rents
    if not real_cities:
        st.warning("Keine Stadtmieten in den Referenz-PDFs gefunden.")
    else:
        city_df = pd.DataFrame(real_cities).set_index("city")
        summary = pd.DataFrame({
            "Bundesland": city_df["state"],
            "Miete Jan 2026 €/m²": city_df["rent_jan_eur_m2"],
            "Miete Okt 2026 €/m²": city_df["rent_oct_eur_m2"],
            f"{CITY_FLAT_M2} m² Okt 2026 €": city_df["rent_oct_flat_eur"],
            "Veränderung %": city_df["change_pct"],
        }).sort_values("Miete Okt 2026 €/m²", ascending=False)
        st.caption(f"Angebotskaltmiete pro m² der {len(summary)} größten Städte, Januar vs. Oktober 2026 · echte "
                   f"Daten: {real_cities[0]['source']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Ø Miete alle Städte (Okt 2026)", f"{de(summary['Miete Okt 2026 €/m²'].mean())} €/m²")
        m2.metric("Ø Veränderung Jan–Okt 2026", f"{de(summary['Veränderung %'].mean(), 1)} %")
        m3.metric("Spanne (Okt 2026)", f"{de(summary['Miete Okt 2026 €/m²'].min())} – "
                                       f"{de(summary['Miete Okt 2026 €/m²'].max())} €/m²")
        st.caption("Ø alle Städte = ungewichteter Mittelwert (nicht nach Einwohnern gewichtet).")
        st.plotly_chart(px.bar(summary, x=summary.index, y="Miete Okt 2026 €/m²", color="Veränderung %",
                               color_continuous_scale="Reds", labels={"city": ""}), width="stretch")
        st.dataframe(summary, width="stretch")

    st.subheader("Abdeckung je Bundesland")
    st.info(STATE_NOTE)
    coverage = state_rent_coverage(basket.real)
    st.dataframe(pd.DataFrame([{
        "Bundesland": s["bundesland"], "Verifizierte Landesreihe": "nein",
        "Städte mit veröffentlichter Miete (Okt 2026)":
            ", ".join(f"{c['city']} ({de(c['rent_eur_per_m2'])} €/m²)" for c in s["cities"]) or "–",
        "Quelle": s["source"]} for s in coverage]), hide_index=True, width="stretch")

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
            t0 = time.perf_counter()
            res = kb.search(kq)
            hits = res["passages"]
            if st.session_state.get("last_kq") != kq:          # record new searches only, not every rerun
                record(mon.rag_trace(kq, res["retriever"], len(hits), time.perf_counter() - t0))
                st.session_state.last_kq = kq
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
    st.caption(f"Datenbasis des Agenten: {basket.label} (echte Daten der Referenz-PDFs). Antworten auf Deutsch.")
    st.session_state.setdefault("messages", [])
    cols = st.columns(len(EXAMPLE_QUESTIONS) + 1)
    for col, q in zip(cols, EXAMPLE_QUESTIONS):
        if col.button(q, width="stretch"):
            st.session_state.pending = q
    if cols[-1].button("🗑️ Neuer Chat", width="stretch"):
        st.session_state.messages = []
        old_agent = st.session_state.pop("agent", None)
        if old_agent is not None and hasattr(old_agent, "cleanup"):
            old_agent.cleanup()               # stops the MCP server subprocess of the old session
        record(mon.new_chat_trace(old_agent is not None))

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools"):
                st.caption("🔧 " + " → ".join(msg["tools"]))
            if msg.get("check"):
                st.warning(msg["check"])

    prompt = st.chat_input("z. B. Steigen die Grundlebenshaltungskosten schneller als die offizielle Inflation?")
    prompt = prompt or st.session_state.pop("pending", None)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        check = ""
        t0, created, turn, figures, error = time.perf_counter(), False, [], [], ""
        with st.chat_message("assistant"), st.spinner("Der Agent wählt Werkzeuge und analysiert ..."):
            try:
                if "agent" not in st.session_state:       # one agent per session -> follow-up questions work
                    from real_basket.agents.orchestrator import create_orchestrator

                    created = True                        # set first: a failed start shows up in the trace
                    st.session_state.agent = create_orchestrator()
                agent = st.session_state.agent
                before = len(agent.messages)
                try:
                    answer = str(agent(prompt))
                finally:
                    turn = list(agent.messages[before:])  # messages of this turn -> use-case path (monitoring)
                tools = _tools_used(turn)
                # guardrail: every figure must come from a tool result of the conversation
                figures = unverified_figures(answer, agent.messages, prompt)
                check = warning_text(figures)
            except Exception as exc:  # noqa: BLE001 - show the error instead of crashing the demo
                answer, tools, error = f"⚠️ Fehler des Agenten: {exc}", [], str(exc)
            record(mon.chat_trace(prompt, turn, "" if error else answer, figures, time.perf_counter() - t0,
                                  error, created))
            st.markdown(answer)
            if tools:
                st.caption("🔧 " + " → ".join(tools))
            if check:
                st.warning(check)
        st.session_state.messages.append({"role": "assistant", "content": answer, "tools": tools, "check": check})

# --- Monitoring: use-case path of every interaction (rendered last -> includes the chat turn of this run) ---
with tab_monitor:
    st.caption("Architektur wie im README (Abschnitt Architecture). Jede Interaktion – Dashboard laden / Gewichte "
               "ändern, Methodensuche, PDF-Berichte, Chatfrage, neuer Chat – wird mit ihrem Use-Case-Pfad "
               "aufgezeichnet: nummerierte Kanten = Reihenfolge der Schritte, gestrichelt = Rückgabe.")
    traces: list[mon.Trace] = st.session_state.get("traces", [])
    if traces:
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Aufgezeichnete Vorgänge", len(traces))
        h2.metric("Chatfragen", sum(t.kind == "Chat" for t in traces))
        h3.metric("Tool-Aufrufe (MCP)", sum(s.action == "tools/call" for t in traces for s in t.steps))
        h4.metric("Mit Warnung / Fehler", sum(t.status != "ok" for t in traces))
    by_id = {t.id: t for t in traces}
    overview = "🗺️ Gesamtarchitektur (ohne Pfad)"
    chosen = st.selectbox("Vorgang", [0, *by_id], index=1 if traces else 0,
                          format_func=lambda i: by_id[i].label if i in by_id else overview)
    selected = by_id.get(chosen)
    if selected is not None and selected.note:
        st.info(selected.note)
    st.graphviz_chart(mon.to_dot(selected), width="stretch")
    if selected is not None:
        st.dataframe(pd.DataFrame(selected.rows()), hide_index=True, width="stretch")
    if traces:
        with st.expander(f"Verlauf ({len(traces)} Vorgänge, neueste zuerst)"):
            st.dataframe(pd.DataFrame([{"Zeit": f"{t.started:%H:%M:%S}", "Status": mon.STATUS_ICON[t.status],
                                        "Vorgang": t.kind, "Titel": t.title, "Schritte": len(t.steps),
                                        "Dauer s": None if t.duration_s is None else round(t.duration_s, 2),
                                        "Info": t.note} for t in traces]), hide_index=True, width="stretch")
        if st.button("🧹 Verlauf leeren"):
            st.session_state.traces = []
            st.rerun()
