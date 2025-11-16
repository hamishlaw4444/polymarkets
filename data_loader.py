# data_loader.py
# Load CSV and add core features

import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config import CSV_PATH
from features import add_features


@st.cache_data(show_spinner=True)
def load_markets(force_refresh: bool = None) -> pd.DataFrame:
    """
    Load markets from CSV. If CSV doesn't exist or force_refresh is True,
    fetch fresh data using get_markets.py.
    
    Args:
        force_refresh: If True, fetch fresh data even if CSV exists. If None, checks session state.
        
    Returns:
        DataFrame with markets data and derived features
    """
    # Check session state for force refresh
    if force_refresh is None:
        force_refresh = st.session_state.get('force_refresh', False)
        if force_refresh:
            # Clear the flag after using it
            st.session_state['force_refresh'] = False
    
    csv_path = CSV_PATH
    
    # Check if we need to fetch data
    if force_refresh or not os.path.exists(csv_path):
        if force_refresh:
            st.info("🔄 Fetching fresh data from Polymarket API...")
        else:
            st.info("📥 CSV not found. Fetching data from Polymarket API...")
        
        # Run get_markets.py to fetch data
        try:
            # Get the directory where data_loader.py is located (same as get_markets.py)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, "get_markets.py")
            
            if not os.path.exists(script_path):
                st.error(f"❌ get_markets.py not found at {script_path}")
                if os.path.exists(csv_path):
                    st.warning(f"Using existing CSV file: {csv_path}")
                else:
                    st.error("No data available. Please ensure get_markets.py is in the same directory.")
                    return pd.DataFrame()
            
            # Run get_markets.py from the script directory, passing the CSV path as argument
            result = subprocess.run(
                [sys.executable, script_path, csv_path],
                cwd=script_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                st.error(f"❌ Error fetching data: {result.stderr}")
                if result.stdout:
                    st.text("Output: " + result.stdout)
                if os.path.exists(csv_path):
                    st.warning(f"Using existing CSV file: {csv_path}")
                else:
                    st.error("No data available. Please check get_markets.py for errors.")
                    return pd.DataFrame()
            
            # Clean up backup if it exists
            backup_path = csv_path + ".backup"
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except:
                    pass
            
            st.success("✅ Data fetched successfully!")
            
        except subprocess.TimeoutExpired:
            st.error("⏱️ Data fetch timed out. Please try again or run get_markets.py manually.")
            # Restore backup if it exists
            backup_path = csv_path + ".backup"
            if os.path.exists(backup_path):
                import shutil
                shutil.move(backup_path, csv_path)
            if os.path.exists(csv_path):
                st.warning(f"Using existing CSV file: {csv_path}")
            else:
                return pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Error running get_markets.py: {str(e)}")
            # Restore backup if it exists
            backup_path = csv_path + ".backup"
            if os.path.exists(backup_path):
                import shutil
                shutil.move(backup_path, csv_path)
            if os.path.exists(csv_path):
                st.warning(f"Using existing CSV file: {csv_path}")
            else:
                return pd.DataFrame()
    
    # Load CSV
    if not os.path.exists(csv_path):
        st.error(f"CSV file not found at: {csv_path}")
        st.info("💡 Click 'Refresh Data' button to fetch data from the API.")
        return pd.DataFrame()
    
    df = pd.read_csv(csv_path)
    
    # Ensure numeric columns
    numeric_cols = [
        "liquidity_num", "liquidity_amm", "liquidity_clob",
        "event_liquidity", "event_volume", "event_openInterest",
        "volume_num", "volume_24h", "volume_1w", "volume_1m", "volume_1y",
        "lastTradePrice", "bestBid", "bestAsk",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Parse dates where available
    date_cols = [
        "event_startDate", "event_endDate",
        "market_startDate", "market_endDate",
        "market_startDateIso", "market_endDateIso",
        "umaEndDateIso",
        "createdAt", "updatedAt", "closedTime",
    ]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    
    # Add derived features
    df = add_features(df)
    
    return df


def download_csv_button():
    """
    Display a download button for the CSV file in the sidebar.
    """
    csv_path = CSV_PATH
    
    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            st.sidebar.download_button(
                label="📥 Download CSV",
                data=f.read(),
                file_name="polymarket_active_markets_enriched.csv",
                mime="text/csv",
                help="Download the current market data as CSV"
            )
    else:
        st.sidebar.info("No CSV file available to download.")


def refresh_data_button():
    """
    Display a button to refresh data from the API.
    """
    if st.sidebar.button("🔄 Refresh Data", help="Fetch fresh data from Polymarket API"):
        # Clear cache
        load_markets.clear()
        # Temporarily rename CSV to force refresh
        csv_path = CSV_PATH
        if os.path.exists(csv_path):
            backup_path = csv_path + ".backup"
            try:
                import shutil
                shutil.move(csv_path, backup_path)
                st.session_state['force_refresh'] = True
            except Exception as e:
                st.error(f"Error preparing refresh: {e}")
        else:
            st.session_state['force_refresh'] = True
        st.rerun()

