"""Streamlit UI. Run with: poetry run streamlit run src/real_basket/ui/app.py"""

import pandas as pd
import plotly.express as px
import streamlit as st

from real_basket.agents.prompts import DISCLAIMER
from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.core.rents import TOTAL_COL, average_rents, overall_average
from real_basket.data.demo_data import demo_cpi, demo_prices, demo_regional_rents
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

tab_idx, tab_yoy, tab_cat, tab_rent, tab_agent = st.tabs(
    ["Index", "YoY rates", "Categories", "🏠 Miete regional", "🤖 Ask the agent"])
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
