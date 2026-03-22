"""
Polymarket Market Collector for the Trading Bot.

Fetches active markets from the Polymarket CLOB API.
Filters by volume, end date, and active status.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import requests

from utils.logger import get_logger

logger = get_logger(__name__)

# Project root and data path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MARKETS_FILE = _PROJECT_ROOT / "data" / "markets" / "active_markets.json"

# Polymarket CLOB API
_CLOB_BASE_URL = "https://clob.polymarket.com"

# Filters
_MIN_VOLUME = 10_000
_MAX_DAYS_TO_RESOLUTION = 7


def _load_existing_markets() -> List[Dict]:
    """Load existing markets from disk."""
    if _MARKETS_FILE.exists():
        try:
            with open(_MARKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading markets: {e}")
    return []


def _save_markets(markets: List[Dict]) -> None:
    """Save markets to disk."""
    _MARKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_MARKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(markets, f, indent=2, ensure_ascii=False)


def _parse_float(value, default: float = 0.0) -> float:
    """Safely parse a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def collect_markets() -> List[Dict]:
    """
    Fetch and filter active markets from Polymarket CLOB API.

    Filters:
        - volume >= 10,000 USDC
        - end_date within 7 days
        - active == True

    Returns:
        List of market dicts meeting all criteria.
    """
    logger.info("Fetching markets from Polymarket CLOB API...")

    now = datetime.now(timezone.utc)
    max_end_date = now + timedelta(days=_MAX_DAYS_TO_RESOLUTION)
    now_iso = now.isoformat()

    filtered_markets = []

    try:
        # Paginate through markets
        next_cursor = None
        page = 0

        while True:
            params = {"limit": 100}
            if next_cursor:
                params["next_cursor"] = next_cursor

            response = requests.get(
                f"{_CLOB_BASE_URL}/markets",
                params=params,
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Polymarket API error: {response.status_code}")
                break

            data = response.json()

            # Handle both list and dict response formats
            if isinstance(data, list):
                markets_data = data
                next_cursor = None
            elif isinstance(data, dict):
                markets_data = data.get("data", data.get("markets", []))
                next_cursor = data.get("next_cursor")
            else:
                logger.warning(f"Unexpected response format: {type(data)}")
                break

            for market in markets_data:
                try:
                    # Check active status
                    if not market.get("active", False):
                        continue

                    # Parse end date
                    end_date_str = market.get("end_date_iso", market.get("end_date", ""))
                    if not end_date_str:
                        continue

                    try:
                        # Handle various date formats
                        if "T" in str(end_date_str):
                            end_date = datetime.fromisoformat(
                                str(end_date_str).replace("Z", "+00:00")
                            )
                        else:
                            end_date = datetime.strptime(
                                str(end_date_str), "%Y-%m-%d"
                            ).replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        continue

                    # Filter: must resolve within 7 days
                    if end_date > max_end_date:
                        continue

                    # Filter: must not have already ended
                    if end_date < now:
                        continue

                    # Parse volume
                    volume = _parse_float(market.get("volume", 0))
                    if volume < _MIN_VOLUME:
                        continue

                    # Parse tokens/prices
                    tokens = market.get("tokens", [])
                    best_ask_yes = 0.5
                    best_bid_yes = 0.5
                    best_ask_no = 0.5

                    if tokens and len(tokens) >= 1:
                        yes_token = tokens[0] if tokens[0].get("outcome", "").upper() == "YES" else (
                            tokens[1] if len(tokens) > 1 else tokens[0]
                        )
                        no_token = tokens[1] if len(tokens) > 1 and tokens[1].get("outcome", "").upper() == "NO" else (
                            tokens[0] if tokens[0].get("outcome", "").upper() == "NO" else None
                        )

                        best_ask_yes = _parse_float(yes_token.get("price", 0.5))
                        best_bid_yes = _parse_float(yes_token.get("price", 0.5))
                        if no_token:
                            best_ask_no = _parse_float(no_token.get("price", 0.5))

                    filtered_market = {
                        "condition_id": market.get("condition_id", ""),
                        "question": market.get("question", ""),
                        "category": market.get("category", "unknown"),
                        "end_date": end_date.isoformat(),
                        "volume": volume,
                        "best_ask_yes": best_ask_yes,
                        "best_bid_yes": best_bid_yes,
                        "best_ask_no": best_ask_no,
                        "liquidity": _parse_float(market.get("liquidity", 0)),
                        "last_updated": now_iso,
                    }

                    filtered_markets.append(filtered_market)

                except Exception as e:
                    logger.debug(f"Error parsing market: {e}")
                    continue

            page += 1
            logger.debug(f"Processed page {page}, {len(filtered_markets)} markets so far")

            # Stop pagination
            if not next_cursor or not markets_data:
                break

            # Safety limit: don't fetch more than 10 pages
            if page >= 10:
                logger.info("Reached page limit, stopping pagination")
                break

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching markets: {e}")
        # Return cached markets if available
        cached = _load_existing_markets()
        if cached:
            logger.info(f"Using {len(cached)} cached markets")
            return cached
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching markets: {e}")
        return _load_existing_markets()

    # Save to disk
    _save_markets(filtered_markets)

    logger.info(f"Market collection complete. {len(filtered_markets)} markets "
                f"meeting criteria (vol >= ${_MIN_VOLUME:,}, resolves within {_MAX_DAYS_TO_RESOLUTION} days)")
    return filtered_markets


def get_active_markets() -> List[Dict]:
    """
    Get the current list of active markets (from disk cache).

    Returns:
        List of filtered market dicts.
    """
    return _load_existing_markets()
