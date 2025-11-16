import requests
import csv
import json
import sys
import os
from typing import List, Dict, Any

BASE_URL = "https://gamma-api.polymarket.com"
EVENTS_ENDPOINT = f"{BASE_URL}/events"

OUTPUT_CSV = "polymarket_active_markets_enriched.csv"

# Tweak these if needed
PAGE_LIMIT = 100          # how many events per page
MIN_LIQUIDITY = 0         # numeric min market liquidity filter (on liquidityNum/liquidity)
ONLY_TRADEABLE = True     # if True, require enableOrderBook + acceptingOrders


def fetch_events_page(limit: int = PAGE_LIMIT, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch a single page of events from the Gamma /events endpoint.
    We request only open (active) events with closed=false.
    """
    params = {
        "order": "id",
        "ascending": "false",
        "closed": "false",
        "limit": limit,
        "offset": offset,
    }

    resp = requests.get(EVENTS_ENDPOINT, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    # API may return a list or a dict with 'events'
    if isinstance(data, dict) and "events" in data:
        return data["events"]
    elif isinstance(data, list):
        return data
    else:
        print("Unexpected /events response shape, got:", type(data))
        return []


def _flatten_event_tags(event: Dict[str, Any]) -> Dict[str, str]:
    """Return pipe-separated tag labels/slugs for the event."""
    tags = event.get("tags", []) or []
    labels = [t.get("label", "").strip() for t in tags if t.get("label")]
    slugs = [t.get("slug", "").strip() for t in tags if t.get("slug")]
    return {
        "event_tags_labels": "|".join(labels) if labels else "",
        "event_tags_slugs": "|".join(slugs) if slugs else "",
    }


def _flatten_market_tags(market: Dict[str, Any]) -> Dict[str, str]:
    """Return pipe-separated tag/category labels/slugs for the market."""
    tags = market.get("tags", []) or []
    tag_labels = [t.get("label", "").strip() for t in tags if t.get("label")]
    tag_slugs = [t.get("slug", "").strip() for t in tags if t.get("slug")]

    cats = market.get("categories", []) or []
    cat_labels = [c.get("label", "").strip() for c in cats if c.get("label")]
    cat_slugs = [c.get("slug", "").strip() for c in cats if c.get("slug")]

    return {
        "market_tags_labels": "|".join(tag_labels) if tag_labels else "",
        "market_tags_slugs": "|".join(tag_slugs) if tag_slugs else "",
        "market_categories_labels": "|".join(cat_labels) if cat_labels else "",
        "market_categories_slugs": "|".join(cat_slugs) if cat_slugs else "",
    }


def _safe_float(val, default: float = 0.0) -> float:
    """Convert val to float if possible, otherwise default."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val))
    except (TypeError, ValueError):
        return default


def extract_active_markets_from_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    For a given event object, extract all relevant active markets.

    Returns a list of dict rows to write to CSV, one per market.
    """
    markets = event.get("markets", []) or []
    rows: List[Dict[str, Any]] = []

    # Event-level fields we care about
    event_id = event.get("id")
    event_slug = event.get("slug")
    event_title = event.get("title")
    event_subtitle = event.get("subtitle")
    event_description = event.get("description")
    event_category = event.get("category")
    event_subcategory = event.get("subcategory")
    event_active = event.get("active", True)
    event_closed = event.get("closed", False)
    event_liquidity = _safe_float(event.get("liquidity", 0))
    event_volume = _safe_float(event.get("volume", 0))
    event_open_interest = _safe_float(event.get("openInterest", 0))
    event_start_date = event.get("startDate")
    event_end_date = event.get("endDate")
    event_tags_flat = _flatten_event_tags(event)

    for m in markets:
        # Market-level closed flag (matching fetch_markets.py behavior)
        market_closed = m.get("closed", event_closed)
        if market_closed:
            continue

        # Optional: filter by active status (default: include all non-closed)
        market_active = m.get("active", True)
        if not market_active:
            continue

        # Optional: filter by tradeability (only if ONLY_TRADEABLE is True)
        if ONLY_TRADEABLE:
            enable_order_book = m.get("enableOrderBook", True)
            accepting_orders = m.get("acceptingOrders", True)
            if not enable_order_book or not accepting_orders:
                continue

        # Liquidity (prefer *_Num fields)
        liquidity_num = _safe_float(m.get("liquidityNum", m.get("liquidity", 0)))
        liquidity_amm = _safe_float(m.get("liquidityAmm", 0))
        liquidity_clob = _safe_float(m.get("liquidityClob", 0))

        if liquidity_num < MIN_LIQUIDITY:
            continue

        # Volume (prefer *_Num)
        volume_num = _safe_float(m.get("volumeNum", m.get("volume", 0)))
        volume_24h = _safe_float(m.get("volume24hr", 0))
        volume_1w = _safe_float(m.get("volume1wk", 0))
        volume_1m = _safe_float(m.get("volume1mo", 0))
        volume_1y = _safe_float(m.get("volume1yr", 0))

        # Prices
        last_trade_price = _safe_float(m.get("lastTradePrice", 0))
        best_bid = _safe_float(m.get("bestBid", 0))
        best_ask = _safe_float(m.get("bestAsk", 0))

        # Basic market info
        row: Dict[str, Any] = {
            # Event context
            "event_id": event_id,
            "event_slug": event_slug,
            "event_title": event_title,
            "event_subtitle": event_subtitle,
            "event_description": event_description,
            "event_category": event_category,
            "event_subcategory": event_subcategory,
            "event_active": event_active,
            "event_closed": event_closed,
            "event_startDate": event_start_date,
            "event_endDate": event_end_date,
            "event_liquidity": event_liquidity,
            "event_volume": event_volume,
            "event_openInterest": event_open_interest,
            **event_tags_flat,

            # Market identifiers
            "market_id": m.get("id"),
            "market_slug": m.get("slug"),
            "market_question": m.get("question"),
            "market_description": m.get("description"),
            "market_resolutionSource": m.get("resolutionSource"),
            "market_category": m.get("category"),
            "market_type": m.get("marketType"),
            "format_type": m.get("formatType"),
            "outcome_type": m.get("outcomeType"),
            "denomination_token": m.get("denominationToken"),

            # Dates
            "market_startDate": m.get("startDate"),
            "market_endDate": m.get("endDate"),
            "market_startDateIso": m.get("startDateIso"),
            "market_endDateIso": m.get("endDateIso"),
            "umaEndDateIso": m.get("umaEndDateIso"),

            # Status / flags
            "market_active": market_active,
            "market_closed": market_closed,
            "enable_order_book": enable_order_book,
            "accepting_orders": accepting_orders,
            "notifications_enabled": m.get("notificationsEnabled"),
            "ready": m.get("ready"),
            "funded": m.get("funded"),

            # Liquidity & volume
            "liquidity_num": liquidity_num,
            "liquidity_amm": liquidity_amm,
            "liquidity_clob": liquidity_clob,
            "volume_num": volume_num,
            "volume_24h": volume_24h,
            "volume_1w": volume_1w,
            "volume_1m": volume_1m,
            "volume_1y": volume_1y,

            # Prices
            "lastTradePrice": last_trade_price,
            "bestBid": best_bid,
            "bestAsk": best_ask,

            # Outcomes & tokens
            "outcomes_raw": m.get("outcomes"),
            "shortOutcomes_raw": m.get("shortOutcomes"),
            "clobTokenIds": m.get("clobTokenIds"),

            # Meta
            "createdAt": m.get("createdAt"),
            "updatedAt": m.get("updatedAt"),
            "closedTime": m.get("closedTime"),
        }

        # Add flattened market tags/categories
        row.update(_flatten_market_tags(m))

        rows.append(row)

    return rows


def fetch_all_active_markets() -> List[Dict[str, Any]]:
    """
    Paginate through all active events and collect all active markets.
    """
    all_rows: List[Dict[str, Any]] = []
    offset = 0

    while True:
        print(f"Fetching events page with offset={offset}...")
        events = fetch_events_page(limit=PAGE_LIMIT, offset=offset)

        if not events:
            print("No more events returned; stopping pagination.")
            break

        print(f"  -> Got {len(events)} events")

        for event in events:
            rows = extract_active_markets_from_event(event)
            all_rows.extend(rows)

        # If fewer than PAGE_LIMIT events returned, we're done
        if len(events) < PAGE_LIMIT:
            break

        offset += PAGE_LIMIT

    return all_rows


def _clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean a row by converting None values to empty strings and ensuring
    all values are CSV-safe (no None, no complex objects).
    """
    cleaned = {}
    for key, value in row.items():
        if value is None:
            cleaned[key] = ""
        elif isinstance(value, (list, dict)):
            # Convert complex objects to JSON strings
            try:
                cleaned[key] = json.dumps(value)
            except (TypeError, ValueError):
                cleaned[key] = str(value)
        else:
            cleaned[key] = value
    return cleaned


def write_csv(rows: List[Dict[str, Any]], filename: str = OUTPUT_CSV) -> None:
    """
    Write all market rows to a CSV. Only includes fields that have actual data
    (at least one non-empty value across all rows).
    """
    if not rows:
        print("No rows to write; CSV will not be created.")
        return

    # First pass: clean all rows
    cleaned_rows = [_clean_row(row) for row in rows]
    
    # Second pass: identify fields that have at least one non-empty value
    all_fieldnames = {k for row in cleaned_rows for k in row.keys()}
    fields_with_data = set()
    
    for fieldname in all_fieldnames:
        # Check if any row has a non-empty value for this field
        for row in cleaned_rows:
            value = row.get(fieldname, "")
            # Consider a field as having data if it's not None, not empty string, and not just whitespace
            if value is not None and str(value).strip() != "":
                fields_with_data.add(fieldname)
                break  # Found at least one non-empty value, no need to check more rows
    
    # Sort fieldnames for consistent column order
    fieldnames = sorted(fields_with_data)
    
    if not fieldnames:
        print("No fields with data found; CSV will not be created.")
        return
    
    print(f"Including {len(fieldnames)} fields with data (out of {len(all_fieldnames)} total fields)")

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cleaned_row in cleaned_rows:
            # Only include fields that have data
            filtered_row = {k: cleaned_row.get(k, "") for k in fieldnames}
            writer.writerow(filtered_row)

    print(f"Wrote {len(rows)} rows to {filename}")


if __name__ == "__main__":
    # Allow output path to be specified as command line argument
    output_path = OUTPUT_CSV
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    else:
        # Default to current directory
        output_path = os.path.join(os.getcwd(), OUTPUT_CSV)
    
    print("Fetching all active Polymarket markets from Gamma API...")
    active_markets = fetch_all_active_markets()
    print(f"Total active markets found: {len(active_markets)}")

    write_csv(active_markets, output_path)
