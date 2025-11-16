# pages/3_Trading_Screener.py

import re
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

from data_loader import load_markets
from filters import apply_global_filters
from model_api import attach_superforecaster_estimates


def compute_alpha_score(df: pd.DataFrame) -> pd.DataFrame:
    import numpy as np  # local import to mirror provided pattern

    def band_liq(x):
        if x is None or np.isnan(x):
            return 0.0
        if x <= 100:
            return 0.0
        if 100 < x < 200:
            return (x - 100) / 100.0
        if 200 <= x <= 5000:
            return 1.0
        if 5000 < x < 25000:
            return 1 - (x - 5000) / 20000.0
        return 0.0

    def band_vol(x):
        if x is None or np.isnan(x):
            return 0.0
        if x <= 10:
            return 0.0
        if 10 < x < 50:
            return (x - 10) / 40.0
        if 50 <= x <= 5000:
            return 1.0
        if 5000 < x < 50000:
            return 1 - (x - 5000) / 45000.0
        return 0.0

    def band_spread(x):
        if x is None or np.isnan(x) or x <= 0:
            return 0.0
        if x < 0.005:
            return x / 0.005
        if 0.005 <= x <= 0.05:
            return 1.0
        if 0.05 < x < 0.15:
            return 1 - (x - 0.05) / 0.10
        return 0.0

    def band_time(x):
        if x is None or np.isnan(x) or x < 0:
            return 0.0
        if 0 <= x < 7:
            return x / 7.0
        if 7 <= x <= 60:
            return 1.0
        if 60 < x < 120:
            return 1 - (x - 60) / 60.0
        return 0.0

    def dom_mult(row):
        d = str(row.get("domain", "Other"))
        title = str(row.get("event_title", ""))

        if d in ["Elections", "Global Elections", "Politics"]:
            base = 1.0
        elif d in ["Tech", "Finance", "Crypto"]:
            base = 0.9
        elif d in ["Culture"]:
            base = 0.7
        elif d in ["Sports"]:
            base = 0.4
        else:
            base = 0.8

        if "Up or Down" in title:
            base *= 0.5

        return base

    liq_band = df.get("liquidity_num", pd.Series(0, index=df.index)).apply(band_liq)
    vol_band = df.get("volume_24h", pd.Series(0, index=df.index)).apply(band_vol)
    spr_band = df.get("spread", pd.Series(0, index=df.index)).apply(band_spread)
    time_band = df.get("time_to_resolution_days", pd.Series(0, index=df.index)).apply(band_time)
    domain_mult = df.apply(dom_mult, axis=1)

    alpha_raw = (
        0.30 * liq_band +
        0.25 * vol_band +
        0.20 * spr_band +
        0.25 * time_band
    )

    quality = df.get("quality_score", 1.0)
    df["alpha_score"] = alpha_raw * domain_mult * quality

    return df


def main():
    st.title("Trading Screener")

    df = load_markets()
    df = attach_superforecaster_estimates(df)
    filtered_df = apply_global_filters(df)

    if filtered_df.empty:
        st.warning("No markets match the current filters.")
        return

    # ---- Trading Screener specific filters ----
    screener_df = filtered_df.copy()

    # ---- Toggable Filters ----
    st.markdown("### Screener Filters")
    
    # Filter 0: Exclude Sports and Crypto
    exclude_sports_crypto = st.checkbox(
        "Exclude Sports and Crypto",
        value=True,
        help="Exclude markets in the Sports and Crypto domains by default"
    )
    if exclude_sports_crypto:
        domain_col = screener_df.get("domain", pd.Series("", index=screener_df.index)).fillna("")
        screener_df = screener_df[
            ~domain_col.str.contains(r"\bSports\b", case=False, regex=True) &
            ~domain_col.str.contains(r"\bCrypto\b", case=False, regex=True)
        ]
    
    # Filter 1: Market must be active
    filter_active = st.checkbox(
        "Market must be active",
        value=True,
        help="Market must be active, not closed, accepting orders, and have order book enabled"
    )
    if filter_active:
        for col, default in [
            ("market_active", True),
            ("market_closed", False),
            ("enable_order_book", True),
            ("accepting_orders", True),
        ]:
            if col not in screener_df.columns:
                screener_df[col] = default
        screener_df = screener_df[
            (screener_df["market_active"] == True)
            & (screener_df["market_closed"] == False)
            & (screener_df["enable_order_book"] == True)
            & (screener_df["accepting_orders"] == True)
        ]

    # Filter 2: Liquidity band
    filter_liq = st.checkbox(
        "Liquidity: 200–5,000",
        value=True,
        help="<200 → dead | 5,000 → too efficient, dominated by bots, little edge"
    )
    if filter_liq:
        liq_series = screener_df.get("liquidity_num", 0).fillna(0)
        screener_df = screener_df[
            (liq_series >= 200) & (liq_series <= 5000)
        ]

    # Filter 3: Spread
    filter_spread = st.checkbox(
        "Spread ≤ 0.12",
        value=True,
        help="Allow some spread — that's where inefficiency lives."
    )
    if filter_spread:
        spr_series = screener_df.get("spread", 1.0).fillna(1.0).clip(lower=0)
        screener_df = screener_df[spr_series <= 0.12]

    # Filter 4: Volume
    filter_vol = st.checkbox(
        "24h Volume ≥ 20",
        value=True,
        help="0–20 volume = market not updating | 20 = at least some attention"
    )
    if filter_vol:
        vol_series = screener_df.get("volume_24h", 0).fillna(0)
        screener_df = screener_df[vol_series >= 20]

    # Filter 5: Time to resolution
    filter_time = st.checkbox(
        "Time to resolution: 2–120 days",
        value=True,
        help="<2 days = price efficient | 3–45 days = peak alpha zone | 45–120 = still ok, but edge decays | >120 = too much uncertainty drift"
    )
    if filter_time:
        ttr = screener_df.get("time_to_resolution_days", pd.Series(np.nan, index=screener_df.index))
        screener_df = screener_df[(ttr >= 2) & (ttr <= 120)]

    if screener_df.empty:
        st.warning("No markets match the screener's filters.")
        return

    # Show count of markets after screener filters
    st.metric("Markets in screener", f"{len(screener_df):,}")

    # ---- Ranking: Screener Score (emphasizes liquidity, volume, tight spreads, 3–90 day band) ----
    liq = screener_df.get("liquidity_num", pd.Series(0, index=screener_df.index)).fillna(0)
    vol = screener_df.get("volume_24h", pd.Series(0, index=screener_df.index)).fillna(0)
    spr = screener_df.get("spread", pd.Series(1.0, index=screener_df.index)).fillna(1.0).clip(lower=0)
    ttr = screener_df.get("time_to_resolution_days", pd.Series(90.0, index=screener_df.index)).fillna(90.0)

    # Liquidity: log-normalized
    max_liq = float(liq.max()) if float(liq.max()) > 0 else 1.0
    liq_score = np.log1p(liq) / np.log1p(max_liq)

    # Volume: cap at 1000 (can tune later)
    vol_score = np.minimum(vol / 1000.0, 1.0)

    # Spread: 0.05 upper bound (tighter is better)
    spread_score = 1.0 - np.minimum(spr / 0.05, 1.0)

    # Time score: ideal band centered ~45 days within 3–90 (triangular shape)
    ttr_clamped = ttr.clip(lower=3.0, upper=90.0)
    time_score = 1.0 - np.minimum(np.abs(ttr_clamped - 45.0) / 45.0, 1.0)

    screener_score = (
        0.35 * liq_score +
        0.30 * vol_score +
        0.20 * spread_score +
        0.15 * time_score
    ).fillna(0.0)

    screener_df["screener_score"] = screener_score

    # Compute alpha score (banded logic)
    screener_df = compute_alpha_score(screener_df)

    # ---- Domain-level charts ----
    st.markdown("### Domains overview")
    if "domain" in screener_df.columns and screener_df["domain"].notna().any():
        # Count and median quality score by domain
        domain_stats = (
            screener_df.groupby("domain")
            .agg(
                num_markets=("domain", "size"),
                med_quality=("quality_score", "median"),
            )
            .reset_index()
        )

        ca, cb = st.columns(2)
        with ca:
            chart_count = (
                alt.Chart(domain_stats)
                .mark_bar()
                .encode(
                    x=alt.X("num_markets:Q", title="Number of markets"),
                    y=alt.Y("domain:N", sort="-x", title="Domain"),
                    tooltip=["domain:N", "num_markets:Q"],
                )
                .properties(height=400)
            )
            st.altair_chart(chart_count, use_container_width=True)
        with cb:
            chart_quality = (
                alt.Chart(domain_stats)
                .mark_bar()
                .encode(
                    x=alt.X("med_quality:Q", title="Median quality score", scale=alt.Scale(domain=[0, 1])),
                    y=alt.Y("domain:N", sort="-x", title="Domain"),
                    tooltip=["domain:N", alt.Tooltip("med_quality:Q", format=".3f")],
                )
                .properties(height=400)
            )
            st.altair_chart(chart_quality, use_container_width=True)
    else:
        st.info("No domain data available for charts.")

    with st.expander("📊 **Quality Score** - How it's computed", expanded=False):
        st.markdown("""
        The quality score (0-1) indicates how tradeable a market is, combining 4 factors:
        
        **Formula:**
        ```
        QualityScore = 0.35 × LiquidityScore + 0.30 × VolumeScore + 
                       0.20 × SpreadScore + 0.15 × TimeScore
        ```
        
        **Components:**
        
        1. **LiquidityScore (35% weight)**
           - Uses log normalization: `log1p(liquidity_num) / log1p(max_liquidity)`
           - Higher liquidity → higher score
        
        2. **VolumeScore (30% weight)**
           - Capped at $1000: `min(volume_24h / 1000, 1)`
           - Higher volume → higher score
        
        3. **SpreadScore (20% weight)**
           - Tighter spreads = better: `1 - min(spread / 0.10, 1)`
           - Spreads ≥ 0.10 get score of 0
           - Spreads near 0 get score of 1
        
        4. **TimeScore (15% weight)**
           - Shorter time to resolution = better: `1 - min(days / 100, 1)`
           - Markets resolving in < 100 days score higher
           - Markets > 100 days get lower scores
        
        **Interpretation:**
        - **High score (0.7-1.0)**: Excellent markets - high liquidity, good volume, tight spreads
        - **Medium score (0.4-0.7)**: Decent markets - tradeable but may have some limitations
        - **Low score (0.0-0.4)**: Poor markets - illiquid, low volume, or wide spreads
        """)

    with st.expander("📊 **Screener Score** - How it's computed", expanded=False):
        st.markdown("""
        The screener score is a ranking score used **within this filtered universe**:
        
        - Emphasises:
          - Higher liquidity (log-normalized)
          - Higher 24h volume (capped at a ceiling)
          - Tighter spreads (0.05 and below are best)
          - Time to resolution near a sweet-spot window (around 45 days)
        - It combines these components with weights similar to quality_score, but tuned for the screener's time/spread band.
        - This is the **default sort order** in the Trading Screener.
        """)

    with st.expander("📊 **Alpha Score** - How it's computed", expanded=False):
        st.markdown("""
        The alpha score is a more opinionated measure that looks for **“alpha pockets”**:
        
        - Uses **banded functions** for:
          - Liquidity_num: prefers a mid-range band (too low or too high scores worse)
          - Volume_24h: prefers mid-range activity, not dead but not hyper-efficient
          - Spread: rewards reasonable, not ultra-tight spreads; penalizes very wide markets
          - Time_to_resolution_days: prefers an intermediate horizon (roughly 1–2 months)
        - Multiplies by a **domain multiplier**:
          - Elections/Politics get the highest base,
          - Tech/Finance/Crypto slightly lower,
          - Culture/Sports/Other are down-weighted,
          - Markets with "Up or Down" in the title are further penalized.
        - Finally, it scales by `quality_score`, so very low-quality markets can't rank as high-alpha.
        """)

    sort_options = {
        "Screener score (desc)": ("screener_score", True),
        "Quality score (desc)": ("quality_score", True),
        "Liquidity (liquidity_num, desc)": ("liquidity_num", True),
        "24h Volume (volume_24h, desc)": ("volume_24h", True),
        "Spread (asc)": ("spread", False),
        "Time to resolution (days, asc)": ("time_to_resolution_days", False),
    }

    sort_label = st.selectbox("Sort by", list(sort_options.keys()))
    sort_col, descending = sort_options[sort_label]

    screener_df = screener_df.sort_values(sort_col, ascending=not descending)

    # Construct Polymarket URL (heuristic)
    if "event_slug" in screener_df.columns:
        screener_df["polymarket_url"] = (
            "https://polymarket.com/event/" + screener_df["event_slug"].astype(str)
        )

    cols_to_show = [
        "event_title",
        "market_question",
        "domain",
        "liquidity_num",
        "volume_24h",
        "spread",
        "mid_price",
        "time_to_resolution_days",
        "quality_score",
        "alpha_score",
        "screener_score",
        "p_true",
        "implied_prob",
        "edge",
        "polymarket_url",
    ]
    cols_to_show = [c for c in cols_to_show if c in screener_df.columns]

    st.dataframe(screener_df[cols_to_show], use_container_width=True)


if __name__ == "__main__":
    main()

