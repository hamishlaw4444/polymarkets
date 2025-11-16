# filters.py
# Global filters (sidebar)

import numpy as np
import pandas as pd
import streamlit as st


def apply_global_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply sidebar filters:
    - Tradeable only
    - Liquidity, volume, spread, time to resolution
    - Domain / tags
    - Text search
    - Binary-like toggle
    """
    st.sidebar.header("Global Filters")

    # Tradeable toggle
    tradeable = st.sidebar.checkbox("Only tradeable markets", value=True)
    if tradeable:
        df = df[
            (df.get("market_active", True)) &
            (~df.get("market_closed", False)) &
            (df.get("enable_order_book", True)) &
            (df.get("accepting_orders", True))
        ]

    if df.empty:
        return df

    # Liquidity filter
    liq_col = df["liquidity_num"].fillna(0)
    liq_min, liq_max = float(liq_col.min()), float(liq_col.max() or 1_000)
    default_min_liq = max(liq_min, 0.0)
    default_max_liq = liq_max

    min_liq, max_liq = st.sidebar.slider(
        "Liquidity (liquidity_num)",
        min_value=0.0,
        max_value=float(default_max_liq),
        value=(default_min_liq, default_max_liq),
        step=float(default_max_liq / 100.0 if default_max_liq > 0 else 1.0),
    )
    df = df[
        (df["liquidity_num"].fillna(0) >= min_liq) &
        (df["liquidity_num"].fillna(0) <= max_liq)
    ]

    # Volume 24h filter
    vol24_col = df["volume_24h"].fillna(0)
    vol_min, vol_max = float(vol24_col.min()), float(vol24_col.max() or 1_000)
    min_vol, max_vol = st.sidebar.slider(
        "24h Volume (volume_24h)",
        min_value=0.0,
        max_value=float(vol_max),
        value=(0.0, float(vol_max)),
        step=float(vol_max / 100.0 if vol_max > 0 else 1.0),
    )
    df = df[
        (df["volume_24h"].fillna(0) >= min_vol) &
        (df["volume_24h"].fillna(0) <= max_vol)
    ]

    # Spread filter
    spread_col = df["spread"].replace([np.inf, -np.inf], np.nan)
    if spread_col.notna().any():
        spread_min_val, spread_max_val = float(spread_col.min()), float(spread_col.max())
        spread_min_val = max(0.0, spread_min_val)
        spread_max_val = max(0.01, spread_max_val)
    else:
        spread_min_val, spread_max_val = 0.0, 0.3

    spread_min, spread_max = st.sidebar.slider(
        "Spread (bestAsk - bestBid)",
        min_value=0.0,
        max_value=float(spread_max_val),
        value=(0.0, min(0.10, spread_max_val)),
        step=0.005,
    )
    df = df[
        (df["spread"].fillna(1.0) >= spread_min) &
        (df["spread"].fillna(1.0) <= spread_max)
    ]

    # Time to resolution
    ttr_col = df["time_to_resolution_days"]
    if ttr_col.notna().any():
        ttr_min_val, ttr_max_val = float(ttr_col.min()), float(ttr_col.max())
    else:
        ttr_min_val, ttr_max_val = -30.0, 365.0

    ttr_min_val = max(-30.0, ttr_min_val)
    ttr_max_val = min(365.0, ttr_max_val if ttr_max_val > 0 else 365.0)

    default_ttr_min, default_ttr_max = 0.0, 90.0
    default_ttr_min = max(default_ttr_min, ttr_min_val)
    default_ttr_max = min(default_ttr_max, ttr_max_val)

    ttr_min, ttr_max = st.sidebar.slider(
        "Time to resolution (days)",
        min_value=float(ttr_min_val),
        max_value=float(max(ttr_max_val, ttr_min_val + 1.0)),
        value=(float(default_ttr_min), float(default_ttr_max)),
        step=1.0,
    )
    df = df[
        (df["time_to_resolution_days"].fillna(1e9) >= ttr_min) &
        (df["time_to_resolution_days"].fillna(1e9) <= ttr_max)
    ]

    # Domain filter (based on domain column)
    if "domain" in df.columns:
        domains = sorted(df["domain"].dropna().unique())
        selected_domains = st.sidebar.multiselect(
            "Domain",
            options=domains,
            default=domains,
        )
        if selected_domains:
            df = df[df["domain"].isin(selected_domains)]

    # Text search
    search = st.sidebar.text_input("Search text (question / event title)")
    if search:
        s = search.lower()
        df = df[
            df["market_question"].fillna("").str.lower().str.contains(s) |
            df["event_title"].fillna("").str.lower().str.contains(s)
        ]

    # Binary-like only
    if "is_binary_like" in df.columns:
        binary_only = st.sidebar.checkbox("Only binary-like markets", value=False)
        if binary_only:
            df = df[df["is_binary_like"]]

    # Optional: exclude obvious 'Up or Down' intraday stuff
    exclude_updown = st.sidebar.checkbox("Exclude 'Up or Down' / very short crypto price markets", value=True)
    if exclude_updown:
        df = df[~df["event_title"].fillna("").str.contains("Up or Down", case=False)]

    return df

