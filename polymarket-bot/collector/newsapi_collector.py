"""
NewsAPI Collector for the Polymarket Trading Bot.

Uses NewsAPI free tier (100 req/day).
Implements rate limiting with daily usage tracking.
Falls back to RSS-only when quota is exhausted.
"""

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv

from utils.logger import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Project root and data paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_RAW_NEWS_FILE = _PROJECT_ROOT / "data" / "news" / "raw_news.json"
_USAGE_FILE = _PROJECT_ROOT / "data" / "newsapi_usage.json"

# NewsAPI config
_NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"
_MAX_DAILY_REQUESTS = 80  # Leave 20 buffer from the 100 limit

# Hardcoded topics
TOPICS = [
    "Federal Reserve interest rates",
    "US election 2026",
    "Bitcoin price prediction",
    "Ukraine Russia ceasefire",
    "US economy GDP",
    "crypto regulation SEC",
    "artificial intelligence regulation",
    "oil price OPEC",
]


def _hash_url(url: str) -> str:
    """Generate SHA256 hash of URL for deduplication."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _load_usage() -> Dict:
    """Load daily usage counter."""
    if _USAGE_FILE.exists():
        try:
            with open(_USAGE_FILE, "r", encoding="utf-8") as f:
                usage = json.load(f)
            # Reset if date changed (midnight UTC)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if usage.get("date") != today:
                return {"date": today, "requests": 0}
            return usage
        except (json.JSONDecodeError, IOError):
            pass

    return {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "requests": 0}


def _save_usage(usage: Dict) -> None:
    """Save daily usage counter to disk."""
    _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, indent=2)


def _load_existing_news() -> List[Dict]:
    """Load existing news articles from disk."""
    if _RAW_NEWS_FILE.exists():
        try:
            with open(_RAW_NEWS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading existing news: {e}")
    return []


def _save_news(articles: List[Dict]) -> None:
    """Save news articles to disk."""
    _RAW_NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_RAW_NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def collect_newsapi() -> List[Dict]:
    """
    Collect news from NewsAPI for all configured topics.

    Respects rate limits (max 80 requests/day).
    Falls back gracefully if no API key or quota exhausted.

    Returns:
        List of new article dicts collected in this run.
    """
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key or api_key == "your_newsapi_key_here":
        logger.info("NewsAPI key not configured — skipping NewsAPI collection")
        return []

    usage = _load_usage()

    if usage["requests"] >= _MAX_DAILY_REQUESTS:
        logger.warning(
            f"NewsAPI daily quota exhausted ({usage['requests']}/{_MAX_DAILY_REQUESTS}). "
            "Falling back to RSS only."
        )
        return []

    logger.info(f"Starting NewsAPI collection (used {usage['requests']}/{_MAX_DAILY_REQUESTS} today)...")

    # Load existing for dedup
    existing = _load_existing_news()
    existing_ids = {a["id"] for a in existing}

    new_articles = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # Calculate date range: last 24 hours
    from_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")

    for topic in TOPICS:
        # Check quota before each request
        if usage["requests"] >= _MAX_DAILY_REQUESTS:
            logger.warning("NewsAPI quota reached mid-collection, stopping.")
            break

        try:
            response = requests.get(
                _NEWSAPI_BASE_URL,
                params={
                    "q": topic,
                    "from": from_date,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 10,
                    "apiKey": api_key,
                },
                timeout=15,
            )
            usage["requests"] += 1
            _save_usage(usage)

            if response.status_code != 200:
                logger.warning(f"NewsAPI error for topic '{topic}': {response.status_code}")
                continue

            data = response.json()
            articles_data = data.get("articles", [])
            count = 0

            for item in articles_data:
                url = item.get("url", "")
                if not url:
                    continue

                article_id = _hash_url(url)
                if article_id in existing_ids:
                    continue

                article = {
                    "id": article_id,
                    "source": "newsapi",
                    "feed_name": "NewsAPI",
                    "topic": topic,
                    "title": item.get("title", "No title"),
                    "description": item.get("description", ""),
                    "url": url,
                    "published_at": item.get("publishedAt", now_iso),
                    "collected_at": now_iso,
                    "analyzed": False,
                }

                new_articles.append(article)
                existing_ids.add(article_id)
                count += 1

            logger.info(f"  Topic '{topic}': {count} new articles")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error for topic '{topic}': {e}")
            continue
        except Exception as e:
            logger.warning(f"Unexpected error for topic '{topic}': {e}")
            continue

    # Merge with existing and save
    if new_articles:
        all_articles = existing + new_articles
        _save_news(all_articles)

    logger.info(f"NewsAPI collection complete. {len(new_articles)} new articles. "
                f"Usage: {usage['requests']}/{_MAX_DAILY_REQUESTS}")
    return new_articles
