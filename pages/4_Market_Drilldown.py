# pages/4_Market_Drilldown.py

import pandas as pd
import streamlit as st

from data_loader import load_markets
from filters import apply_global_filters
from model_api import attach_superforecaster_estimates


def main():
    st.title("Single Market Drilldown")

    df = load_markets()
    df = attach_superforecaster_estimates(df)
    filtered_df = apply_global_filters(df)

    if filtered_df.empty:
        st.warning("No markets available for drilldown with current filters.")
        return

    # Build label for selection
    def label_row(row):
        title = row.get("event_title") or ""
        q = row.get("market_question") or ""
        return f"{title[:60]} – {q[:80]}"

    options = filtered_df["market_id"].astype(str).tolist()
    labels = filtered_df.apply(label_row, axis=1).tolist()
    market_id_to_label = dict(zip(options, labels))

    selected_market_id = st.selectbox(
        "Select a market",
        options=options,
        format_func=lambda x: market_id_to_label.get(str(x), str(x)),
    )

    market = filtered_df[filtered_df["market_id"].astype(str) == str(selected_market_id)].iloc[0]

    st.markdown("### Event context")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Event title**:", market.get("event_title"))
        st.write("**Subtitle**:", market.get("event_subtitle"))
        st.write("**Category**:", market.get("event_category"))
        st.write("**Subcategory**:", market.get("event_subcategory"))
        st.write("**Event tags**:", market.get("event_tags_labels"))
        st.write("**Event start**:", market.get("event_startDate"))
        st.write("**Event end**:", market.get("event_endDate"))
    with col2:
        st.write("**Event ID**:", market.get("event_id"))
        st.write("**Event slug**:", market.get("event_slug"))
        st.write("**Event liquidity**:", market.get("event_liquidity"))
        st.write("**Event volume**:", market.get("event_volume"))
        st.write("**Open interest**:", market.get("event_openInterest"))

    st.markdown("---")
    st.markdown("### Market details")
    col3, col4 = st.columns(2)
    with col3:
        st.write("**Market question**:", market.get("market_question"))
        st.write("**Description**:", market.get("market_description"))
        st.write("**Resolution source**:", market.get("market_resolutionSource"))
        st.write("**Market category**:", market.get("market_category"))
        st.write("**Outcome type**:", market.get("outcome_type"))
        st.write("**Market type**:", market.get("market_type"))
        st.write("**Format type**:", market.get("format_type"))
    with col4:
        st.write("**Market ID**:", market.get("market_id"))
        st.write("**Market slug**:", market.get("market_slug"))
        st.write("**Denomination token**:", market.get("denomination_token"))
        st.write("**Start date**:", market.get("market_startDate"))
        st.write("**End date**:", market.get("market_endDate"))
        st.write("**End date (ISO)**:", market.get("market_endDateIso"))
        st.write("**Time to resolution (days)**:", market.get("time_to_resolution_days"))

    st.markdown("---")
    st.markdown("### Trading info")
    col5, col6, col7 = st.columns(3)
    with col5:
        st.write("**Liquidity_num**:", market.get("liquidity_num"))
        st.write("**Liquidity_amm**:", market.get("liquidity_amm"))
        st.write("**Liquidity_clob**:", market.get("liquidity_clob"))
    with col6:
        st.write("**24h Volume**:", market.get("volume_24h"))
        st.write("**1w Volume**:", market.get("volume_1w"))
        st.write("**Total Volume (num)**:", market.get("volume_num"))
    with col7:
        st.write("**Best bid**:", market.get("bestBid"))
        st.write("**Best ask**:", market.get("bestAsk"))
        st.write("**Spread**:", market.get("spread"))
        st.write("**Mid price**:", market.get("mid_price"))
        st.write("**Quality score**:", market.get("quality_score"))

    st.markdown("---")
    st.markdown("### Model estimates")
    col8, col9 = st.columns(2)
    with col8:
        st.write("**Model probability (p_true)**:", market.get("p_true"))
        st.write("**Implied probability**:", market.get("implied_prob"))
    with col9:
        st.write("**Edge**:", market.get("edge"))

    st.markdown("---")
    st.markdown("### Outcomes & Tokens")
    st.write("**Outcomes (raw)**:", market.get("outcomes_raw"))
    st.write("**Short outcomes (raw)**:", market.get("shortOutcomes_raw"))
    st.write("**CLOB token IDs**:", market.get("clobTokenIds"))

    # Construct URL
    event_slug = market.get("event_slug")
    market_slug = market.get("market_slug")
    url = None
    if pd.notna(event_slug):
        url = f"https://polymarket.com/event/{event_slug}"
    elif pd.notna(market_slug):
        url = f"https://polymarket.com/market/{market_slug}"

    if url:
        st.markdown(f"**Polymarket URL:** [{url}]({url})")

    st.markdown("---")
    st.caption("This view is designed to be friendly for later wiring up a superforecaster model and a trading bot.")


if __name__ == "__main__":
    main()

