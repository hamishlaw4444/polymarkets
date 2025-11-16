# config.py
# Paths and simple configuration

import os

# Path to the CSV file (relative to this file)
CSV_PATH = os.path.join(os.path.dirname(__file__), "polymarket_active_markets_enriched.csv")

# Default filter values
DEFAULT_MIN_LIQUIDITY = 0
DEFAULT_ONLY_TRADEABLE = True

