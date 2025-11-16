# pages/2_Domain_Explorer.py

import altair as alt
import pandas as pd
import streamlit as st

from data_loader import load_markets
from filters import apply_global_filters
from model_api import attach_superforecaster_estimates


def main():
    st.title("Domain / Tag Explorer")

    df = load_markets()
    df = attach_superforecaster_estimates(df)
    filtered_df = apply_global_filters(df)

    if filtered_df.empty:
        st.warning("No markets match the current filters.")
        return

    st.markdown("### Domain-level stats")

    if "domain" not in filtered_df.columns:
        st.info("No domain column found.")
        return

    domain_stats = (
        filtered_df.groupby("domain")
        .agg(
            n_markets=("market_id", "count"),
            med_liq=("liquidity_num", "median"),
            med_vol24=("volume_24h", "median"),
            med_spread=("spread", "median"),
        )
        .reset_index()
        .sort_values("med_liq", ascending=False)
    )

    st.dataframe(domain_stats, use_container_width=True)

    st.markdown("### Domains by median liquidity")
    chart = (
        alt.Chart(domain_stats)
        .mark_bar()
        .encode(
            x=alt.X("med_liq:Q", title="Median liquidity_num"),
            y=alt.Y("domain:N", sort="-x"),
        )
        .properties(height=400)
    )
    st.altair_chart(chart, use_container_width=True)

    st.markdown("### Explore a single domain")

    domains = domain_stats["domain"].tolist()
    selected_domain = st.selectbox("Select domain", domains)

    sub = filtered_df[filtered_df["domain"] == selected_domain]

    st.write(f"Markets in **{selected_domain}**: {len(sub):,}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Median liquidity_num", f"{sub['liquidity_num'].median():,.0f}")
    col2.metric("Median 24h volume", f"{sub['volume_24h'].median():,.0f}")
    col3.metric("Median spread", f"{sub['spread'].median():.3f}")

    st.markdown("#### Distributions in this domain")

    ca, cb = st.columns(2)
    with ca:
        st.write("Liquidity distribution")
        chart = (
            alt.Chart(sub)
            .mark_bar()
            .encode(
                alt.X("liquidity_num:Q", bin=alt.Bin(maxbins=40)),
                alt.Y("count()", title="Count of markets"),
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)

    with cb:
        st.write("Spread distribution")
        chart = (
            alt.Chart(sub)
            .mark_bar()
            .encode(
                alt.X("spread:Q", bin=alt.Bin(maxbins=40)),
                alt.Y("count()", title="Count of markets"),
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)

    st.markdown("#### Sample markets in this domain")
    cols = [
        "event_title",
        "market_question",
        "liquidity_num",
        "volume_24h",
        "spread",
        "time_to_resolution_days",
    ]
    cols = [c for c in cols if c in sub.columns]
    st.dataframe(sub[cols].head(50), use_container_width=True)


if __name__ == "__main__":
    main()

