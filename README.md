# Polymarket Dashboard

A multi-page Streamlit dashboard for exploring and analyzing Polymarket prediction markets.

## Structure

```
polymarket_dashboard/
├── app.py                         # Main Streamlit entry (overview)
├── config.py                      # Paths and simple config
├── data_loader.py                 # Load CSV and add core features
├── features.py                    # Derived fields & domain logic
├── filters.py                     # Global filters (sidebar)
├── model_api.py                   # Stub for superforecaster integration
├── polymarket_active_markets_enriched.csv  # Generated CSV (auto-created)
└── pages/
    ├── 2_Domain_Explorer.py       # Domain/tag exploration
    ├── 3_Trading_Screener.py      # Trading opportunity screener
    └── 4_Market_Drilldown.py      # Single market detailed view
```

## Features

- **Data Fetching**: Automatically fetches data from Polymarket API using `get_markets.py` (cached)
- **CSV Download**: Download the current market data as CSV
- **Multi-page Navigation**: 
  - Overview: High-level statistics and distributions
  - Domain Explorer: Explore markets by domain/tag
  - Trading Screener: Find trading opportunities
  - Market Drilldown: Detailed view of individual markets
- **Global Filters**: Sidebar filters apply across all pages
- **Model Integration Ready**: Placeholder for superforecaster model integration

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the dashboard:
   ```bash
   streamlit run app.py
   ```

3. The dashboard will automatically fetch data if the CSV doesn't exist, or you can click "Refresh Data" to fetch fresh data.

## Data Flow

1. `data_loader.py` loads data from CSV (or fetches it using `get_markets.py`)
2. `features.py` adds derived columns (spread, mid_price, quality_score, etc.)
3. `filters.py` applies global filters from the sidebar
4. `model_api.py` (placeholder) would add model predictions
5. Pages display the filtered and enriched data

## Notes

- The CSV file is cached and stored in the `polymarket_dashboard` directory
- Data fetching uses `get_markets.py` from the parent directory
- All pages share the same global filters in the sidebar

