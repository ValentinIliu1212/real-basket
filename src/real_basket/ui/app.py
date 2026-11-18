"""Streamlit UI. Run with: poetry run streamlit run src/real_basket/ui/app.py"""

import pandas as pd
import plotly.express as px
import streamlit as st

from real_basket.agents.prompts import DISCLAIMER
from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.core.income import DEFAULT_FLAT_SIZE_M2, average_salaries, rent_burden
from real_basket.core.rents import TOTAL_COL, average_rents, overall_average
from real_basket.data.demo_data import demo_cpi, demo_net_salaries, demo_prices, demo_regional_rents
from real_basket.schemas.models import BasketWeights, Category, RegionType

st.set_page_config(page_title="RealBasket", page_icon="🧺", layout="wide")
st.title("🧺 RealBasket")
st.caption("Essential living cost index vs. official Consumer Price Index (CPI)")
st.info(DISCLAIMER)

# --- Sidebar: basket weights -------------------------------------------------
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

# --- Dashboard ---------------------------------------------------------------
prices = demo_prices()
comparison = compare_with_cpi(essential_index(prices, weights), demo_cpi())
latest = comparison.dropna().iloc[-1]

c1, c2, c3 = st.columns(3)
c1.metric("Essential inflation (YoY)", f"{latest['essential_yoy_pct']:.2f} %")
c2.metric("Official CPI (YoY)", f"{latest['cpi_yoy_pct']:.2f} %")
c3.metric("Deviation", f"{latest['deviation_pp']:+.2f} pp")

tab_idx, tab_yoy, tab_cat, tab_rent, tab_income, tab_flow, tab_agent = st.tabs(
    ["Index", "YoY rates", "Categories", "🏠 Miete regional", "💶 Nettogehalt", "🔄 Monitoring runs",
     "🤖 Ask the agent"])
with tab_idx:
    st.plotly_chart(px.line(comparison[["essential_index", "cpi_index"]], labels={"value": "Index (base=100)"}),
                    use_container_width=True)
with tab_yoy:
    yoy = comparison[["essential_yoy_pct", "cpi_yoy_pct", "deviation_pp"]].dropna()
    st.plotly_chart(px.line(yoy, labels={"value": "%"}), use_container_width=True)
with tab_cat:
    st.plotly_chart(px.line(category_indices(prices), labels={"value": "Index (base=100)"}),
                    use_container_width=True)

with tab_rent:
    level = st.radio("Ebene", ["Bundesländer", "Größte Städte"], horizontal=True)
    rtype = RegionType.STATE if level == "Bundesländer" else RegionType.CITY
    regional_rents = demo_regional_rents(region_type=rtype)
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
                           color_continuous_scale="Reds", labels={"x": ""}), use_container_width=True)
    col_tbl, col_line = st.columns([1, 2])
    col_tbl.dataframe(summary, use_container_width=True)
    selected = col_line.multiselect("Regionen vergleichen", list(summary.index), default=list(summary.index[:3]))
    if selected:
        col_line.plotly_chart(
            px.line(rent_df[rent_df["region"].isin(selected)], x="period", y="price", color="region",
                    labels={"price": "€/m²", "period": ""}), use_container_width=True)

    st.subheader(f"Ø Miete pro Jahr – {level}")
    avg_display = avg_table.copy()
    avg_display.loc["Ø alle Regionen"] = overall_average(avg_table)
    st.dataframe(avg_display.style.format("{:.2f} €"), use_container_width=True)

with tab_income:
    incomes = demo_net_salaries()
    state_rents = demo_regional_rents(region_type=RegionType.STATE)
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
                                labels={"x": "", TOTAL_COL: "€"}), use_container_width=True)
    col_bur.plotly_chart(px.bar(burden_tbl, x=burden_tbl.index, y=TOTAL_COL, color=TOTAL_COL,
                                color_continuous_scale="Reds",
                                title=f"Mietbelastung: Miete {flat} m² in % vom Nettogehalt",
                                labels={"x": "", TOTAL_COL: "%"}), use_container_width=True)

    st.subheader("Ø Nettogehalt pro Jahr")
    sal_display = salary_tbl.copy()
    sal_display.loc["Ø alle Bundesländer"] = salary_tbl.mean(axis=0)
    st.dataframe(sal_display.style.format("{:,.0f} €"), use_container_width=True)
    st.subheader(f"Mietbelastung pro Jahr ({flat} m²)")
    bur_display = burden_tbl.copy()
    bur_display.loc["Ø alle Bundesländer"] = burden_tbl.mean(axis=0)
    st.dataframe(bur_display.style.format("{:.1f} %"), use_container_width=True)

with tab_flow:
    from real_basket.core.store import DataStore
    from real_basket.flow.runner import DEFAULT_GOALS
    from real_basket.schemas.flow import Trigger

    st.caption("Non-deterministic monitoring flow: agents plan, choose sources, validate (with retries), "
               "investigate and report; numbers come from the deterministic engine. "
               "See docs/process-redesign.md.")
    store = DataStore()
    with st.form("start_run"):
        f1, f2 = st.columns([1, 3])
        trig = Trigger(f1.selectbox("Trigger", [t.value for t in Trigger]))
        goal = f2.text_input("Goal (empty = default for the trigger)")
        auto = st.checkbox("Auto-approve (demo only: human decisions are taken automatically)")
        if st.form_submit_button("▶ Start monitoring run"):
            from real_basket.flow.graph import auto_approver, deferred_approver, run_flow

            with st.spinner("Agents are planning, collecting, validating and analysing..."):
                ctx = run_flow(goal or DEFAULT_GOALS[trig], trigger=trig,
                               approver=auto_approver if auto else deferred_approver,
                               weights={c.value: w for c, w in weights.weights.items()}, store=store)
            st.success(f"Run {ctx.run_id}: {ctx.run_status.value} (confidence {ctx.confidence})")

    runs = store.list_runs()
    if not runs:
        st.info("No runs yet.")
    for run in runs[:10]:
        res = run.get("results") or {}
        title = (f"{run['run_id']} · {run['trigger']} · **{run['status']}** · confidence {run.get('confidence')}"
                 + (f" · deviation {res['deviation_pp']:+.2f} pp" if res else ""))
        with st.expander(title, expanded=run["status"] == "pending_approval"):
            st.write("**Goal:** " + run["goal"])
            st.write("**Path:** " + " → ".join(run.get("path", [])))
            st.dataframe(pd.DataFrame([{"dataset": d, "status": v["status"], "attempts": v["attempts"],
                                        "sources tried": ", ".join(v["sources_tried"]), "score": v["score"]}
                                       for d, v in run.get("datasets", {}).items()]),
                         use_container_width=True, hide_index=True)
            if run["status"] == "pending_approval":
                st.warning("Confidence below threshold – a human must approve before publishing.")
                from real_basket.flow.steps import publish_run, reject_run

                reason = st.text_input("Reason (optional, stored in the audit trail)", key=f"why_{run['run_id']}")
                a1, a2 = st.columns(2)
                if a1.button("✅ Approve & publish", key=f"ok_{run['run_id']}"):
                    publish_run(store, run["run_id"], approved_by="dashboard")
                    st.rerun()
                if a2.button("❌ Reject", key=f"no_{run['run_id']}"):
                    reject_run(store, run["run_id"], rejected_by="dashboard", reason=reason)
                    st.rerun()
            st.markdown((run.get("report") or {}).get("final_markdown", "_no report_"))
            if st.checkbox("Show audit trail", key=f"audit_{run['run_id']}"):
                st.dataframe(pd.DataFrame(store.load_audit(run["run_id"])).astype(str), use_container_width=True)

with tab_agent:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).markdown(msg["content"])
    if prompt := st.chat_input("e.g. Are basic living costs rising faster than official inflation?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        with st.chat_message("assistant"), st.spinner("Agents are collecting and analysing prices..."):
            from real_basket.agents.orchestrator import create_orchestrator

            answer = str(create_orchestrator()(prompt))
            st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})