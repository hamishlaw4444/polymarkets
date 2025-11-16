# app.py
# Main Streamlit entry point - shows Overview

import numpy as np
import altair as alt
import streamlit as st

from data_loader import load_markets, download_csv_button, refresh_data_button
from filters import apply_global_filters
from model_api import attach_superforecaster_estimates

st.set_page_config(
    page_title="Overview",
    layout="wide",
)

st.title("Overview")
st.caption("Home / Overview")

# Data management buttons in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### Data Management")
refresh_data_button()
download_csv_button()
st.sidebar.markdown("---")

# Overview-specific toggle
only_positive_liq_vol = st.sidebar.checkbox(
    "Only markets with >0 liquidity and 24h volume",
    value=True,
    help="When checked, hides markets that have zero liquidity or zero 24h volume.",
)

# Load data
df = load_markets()

if df.empty:
    st.error("No data available. Please click 'Refresh Data' to fetch data from the API.")
    st.stop()

# Apply model estimates (placeholder for now)
df = attach_superforecaster_estimates(df)

# Apply filters
filtered_df = apply_global_filters(df)

# Optional overview filter: only markets with positive liquidity and volume
if only_positive_liq_vol:
    if "liquidity_num" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["liquidity_num"].fillna(0) > 0]
    if "volume_24h" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["volume_24h"].fillna(0) > 0]

st.subheader("Overview of filtered markets")

n_markets = len(filtered_df)
total_liq = filtered_df["liquidity_num"].sum(skipna=True)
total_vol24 = filtered_df["volume_24h"].sum(skipna=True)

col1, col2, col3 = st.columns(3)
col1.metric("Number of markets", f"{n_markets:,}")
col2.metric("Total liquidity_num", f"{total_liq:,.0f}")
col3.metric("Total 24h volume", f"{total_vol24:,.0f}")

st.markdown("### Distributions")

col_a, col_b = st.columns(2)

with col_a:
    if filtered_df["liquidity_num"].notna().any():
        with st.expander("📊 **Liquidity_num** - What it means", expanded=False):
            st.markdown("""
            **Liquidity_num** = how much money is sitting on the orderbook right now.
            
            **It tells you:**
            - How easy it is to enter/exit a position
            - How much slippage you'll take
            - How "robust" the market is
            
            **Guidelines:**
            - **< $200** → too thin
            - **$200–$2,000** → sweet spot (model edge + tradable)
            - **> $10k** → very efficient markets, fewer opportunities
            
            High liquidity → good execution, hard to find mispricing  
            Low liquidity → big mispricings possible, but harder to trade size
            """)
        st.write("**Liquidity distribution**")
        # Filter to show only 5th to 95th percentiles
        liq_col = filtered_df["liquidity_num"].fillna(0)
        if liq_col.notna().any() and liq_col.max() > 0:
            # Calculate 5th and 95th percentiles
            p5 = liq_col.quantile(0.05)
            p95 = liq_col.quantile(0.95)
            liq_data = filtered_df[
                (filtered_df["liquidity_num"] >= p5) & 
                (filtered_df["liquidity_num"] <= p95)
            ].copy()
            chart = (
                alt.Chart(liq_data)
                .mark_bar()
                .encode(
                    alt.X("liquidity_num:Q", bin=alt.Bin(maxbins=40)),
                    alt.Y("count()", title="Count of markets"),
                )
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)
            excluded_low = len(filtered_df[filtered_df["liquidity_num"] < p5])
            excluded_high = len(filtered_df[filtered_df["liquidity_num"] > p95])
            if excluded_low > 0 or excluded_high > 0:
                st.caption(f"Note: Showing 5th–95th percentile (${p5:,.0f}–${p95:,.0f}). {excluded_low + excluded_high} outliers excluded.")
        else:
            st.info("No liquidity_num data available.")

with col_b:
    if filtered_df["volume_24h"].notna().any():
        with st.expander("📊 **Volume_24h** - What it means", expanded=False):
            st.markdown("""
            **Volume_24h** = how much was traded in the last 24 hours.
            
            **It tells you:**
            - How active the market is
            - Whether prices update quickly
            - Whether traders are paying attention
            
            **Guidelines:**
            - **$50–$500** → sweet spot for model opportunities
            - High volume → efficient, competitive
            - Low volume → stale prices, bigger edges
            - Zero volume → dead market, avoid
            
            **Best markets for superforecaster model:**  
            Liquidity: $200–$2,000 | Volume: $50–$500
            
            These markets aren't dominated by pros, have enough activity to enter/exit, and are slow enough that your model can catch mispricings.
            """)
        st.write("**24h Volume distribution**")
        # Filter to show only 5th to 95th percentiles
        vol_col = filtered_df["volume_24h"].fillna(0)
        if vol_col.notna().any() and vol_col.max() > 0:
            # Calculate 5th and 95th percentiles
            p5 = vol_col.quantile(0.05)
            p95 = vol_col.quantile(0.95)
            vol_data = filtered_df[
                (filtered_df["volume_24h"] >= p5) & 
                (filtered_df["volume_24h"] <= p95)
            ].copy()
            chart = (
                alt.Chart(vol_data)
                .mark_bar()
                .encode(
                    alt.X("volume_24h:Q", bin=alt.Bin(maxbins=40)),
                    alt.Y("count()", title="Count of markets"),
                )
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)
            excluded_low = len(filtered_df[filtered_df["volume_24h"] < p5])
            excluded_high = len(filtered_df[filtered_df["volume_24h"] > p95])
            if excluded_low > 0 or excluded_high > 0:
                st.caption(f"Note: Showing 5th–95th percentile (${p5:,.0f}–${p95:,.0f}). {excluded_low + excluded_high} outliers excluded.")
        else:
            st.info("No volume_24h data available.")

st.markdown("### Spread distribution")
if filtered_df["spread"].notna().any():
    chart = (
        alt.Chart(filtered_df)
        .mark_bar()
        .encode(
            alt.X("spread:Q", bin=alt.Bin(maxbins=40)),
            alt.Y("count()", title="Count of markets"),
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No spread data available.")

st.markdown("### Markets by domain")
if "domain" in filtered_df.columns and filtered_df["domain"].notna().any():
    domain_counts = (
        filtered_df.groupby("domain")["market_id"]
        .count()
        .reset_index(name="num_markets")
    )
    chart = (
        alt.Chart(domain_counts)
        .mark_bar()
        .encode(
            x=alt.X("num_markets:Q", title="Number of markets"),
            y=alt.Y("domain:N", sort="-x", title="Domain"),
        )
        .properties(height=400)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No domain data available.")

st.markdown("### Sample markets")
cols = [
    "event_title",
    "market_question",
    "domain",
    "liquidity_num",
    "volume_24h",
    "spread",
    "time_to_resolution_days",
    "quality_score",
]
cols = [c for c in cols if c in filtered_df.columns]
st.dataframe(filtered_df[cols].head(20), use_container_width=True)
