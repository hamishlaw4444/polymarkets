# features.py
# Derived fields & domain logic

from datetime import datetime, timezone

import numpy as np
import pandas as pd


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns: spread, mid_price, time_to_resolution, domain flags,
    binary-like flag, quality_score, and placeholders for model output.
    """

    # Spread & mid price
    if "bestBid" in df.columns and "bestAsk" in df.columns:
        df["spread"] = (df["bestAsk"] - df["bestBid"]).astype(float)
        df["mid_price"] = (df["bestBid"] + df["bestAsk"]) / 2.0
    else:
        df["spread"] = np.nan
        df["mid_price"] = np.nan

    # Time to resolution (days)
    now = pd.Timestamp.utcnow().tz_localize("UTC") if not isinstance(
        pd.Timestamp.utcnow().tzinfo, timezone
    ) else pd.Timestamp.utcnow()

    end = None
    if "market_endDateIso" in df.columns:
        end = df["market_endDateIso"]
    elif "market_endDate" in df.columns:
        end = df["market_endDate"]
    else:
        end = df.get("event_endDate")

    if end is not None:
        df["time_to_resolution_days"] = (end - now).dt.total_seconds() / (60 * 60 * 24)
    else:
        df["time_to_resolution_days"] = np.nan

    # Binary-like detection (very rough)
    if "outcomes_raw" in df.columns:
        df["is_binary_like"] = df["outcomes_raw"].apply(_looks_binary)
    else:
        df["is_binary_like"] = False

    # Domain / tag flags
    df = add_domain_flags(df)

    # Placeholders for model probabilities & edge
    df["p_true"] = np.nan
    df["implied_prob"] = df["mid_price"]
    df["edge"] = np.nan

    # Quality score
    df["quality_score"] = compute_quality_score(df)

    return df


def _looks_binary(outcomes_raw) -> bool:
    """Very rough heuristic to check if outcomes_raw looks like 2 outcomes."""
    if pd.isna(outcomes_raw):
        return False

    text = str(outcomes_raw).strip()
    candidates = []

    if text.startswith("[") and text.endswith("]"):
        # Likely a JSON-like list
        inner = text[1:-1]
        candidates = [x.strip().strip('"').strip("'") for x in inner.split(",")]
    else:
        if "," in text:
            candidates = [x.strip() for x in text.split(",")]
        elif "|" in text:
            candidates = [x.strip() for x in text.split("|")]
        else:
            candidates = [text]

    # Count non-empty tokens
    tokens = [c for c in candidates if c]
    return len(tokens) == 2


def add_domain_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add columns like is_elections, is_crypto, is_sports based on event_tags_labels.
    """

    tags_col = df.get("event_tags_labels")
    if tags_col is None:
        # Nothing to do
        df["is_elections"] = False
        df["is_global_elections"] = False
        df["is_politics"] = False
        df["is_crypto"] = False
        df["is_crypto_prices"] = False
        df["is_tech"] = False
        df["is_finance"] = False
        df["is_sports"] = False
        df["is_culture"] = False
        return df

    s = tags_col.fillna("").astype(str)

    def has_tag(name: str) -> pd.Series:
        # rough word boundary match
        return s.str.contains(rf"\b{name}\b", regex=True)

    df["is_elections"] = has_tag("Elections")
    df["is_global_elections"] = has_tag("Global Elections")
    df["is_politics"] = has_tag("Politics")
    df["is_crypto"] = has_tag("Crypto")
    df["is_crypto_prices"] = has_tag("Crypto Prices")
    df["is_tech"] = has_tag("Tech")
    df["is_finance"] = has_tag("Finance")
    df["is_sports"] = has_tag("Sports")
    df["is_culture"] = has_tag("Culture")

    # Convenience "domain" string (not exhaustive, but handy)
    domain = []
    for idx, row in df.iterrows():
        if row.get("is_sports"):
            domain.append("Sports")
        elif row.get("is_global_elections") or row.get("is_elections"):
            domain.append("Elections")
        elif row.get("is_politics"):
            domain.append("Politics")
        elif row.get("is_crypto_prices"):
            domain.append("Crypto Prices")
        elif row.get("is_crypto"):
            domain.append("Crypto")
        elif row.get("is_tech"):
            domain.append("Tech")
        elif row.get("is_finance"):
            domain.append("Finance")
        elif row.get("is_culture"):
            domain.append("Culture")
        else:
            domain.append("Other")

    df["domain"] = domain

    return df


def compute_quality_score(df: pd.DataFrame) -> pd.Series:
    """
    Quality score (0-1) indicating how tradeable a market is.
    Combines liquidity, volume, spread, and time to resolution.
    
    Formula:
    QualityScore = 0.35 * LiquidityScore + 0.30 * VolumeScore + 
                   0.20 * SpreadScore + 0.15 * TimeScore
    """

    # Get base values, filling missing with defaults
    liq = df.get("liquidity_num", pd.Series(0, index=df.index)).fillna(0)
    vol_24h = df.get("volume_24h", pd.Series(0, index=df.index)).fillna(0)
    spread = df.get("spread", pd.Series(np.nan, index=df.index))
    ttr = df.get("time_to_resolution_days", pd.Series(np.nan, index=df.index))

    # 1. LiquidityScore: log normalization
    max_liq = liq.max()
    if max_liq > 0:
        liq_score = np.log1p(liq) / np.log1p(max_liq)
    else:
        liq_score = pd.Series(0.0, index=df.index)

    # 2. VolumeScore: capped at 1000
    vol_score = np.minimum(vol_24h / 1000.0, 1.0)

    # 3. SpreadScore: tighter spreads = higher score
    # Any spread >= 0.10 gets a score of 0
    spread_safe = spread.fillna(1.0)  # Missing spread treated as very wide
    spread_safe = np.maximum(spread_safe, 0.0)  # Ensure non-negative
    spread_score = 1.0 - np.minimum(spread_safe / 0.10, 1.0)

    # 4. TimeScore: shorter time to resolution = better, capped at 100 days
    ttr_safe = ttr.fillna(100.0)  # Missing time treated as max
    ttr_safe = np.maximum(ttr_safe, 0.0)  # Ensure non-negative
    time_score = 1.0 - np.minimum(ttr_safe / 100.0, 1.0)

    # Final weighted score
    score = (
        0.35 * liq_score +
        0.30 * vol_score +
        0.20 * spread_score +
        0.15 * time_score
    )

    return score.fillna(0.0)

