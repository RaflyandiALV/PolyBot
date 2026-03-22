"""
RSS Feed Collector for the Polymarket Trading Bot.

Collects news from 9 free RSS feeds, standardizes format,
deduplicates by URL hash, and filters articles older than 24 hours.
"""

import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import feedparser

from utils.logger import get_logger

logger = get_logger(__name__)

# Project root and data directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_RAW_NEWS_FILE = _PROJECT_ROOT / "data" / "news" / "raw_news.json"

# Hardcoded RSS feeds (free, no API key required)
RSS_FEEDS = {
    "Reuters Top News":      "https://feeds.reuters.com/reuters/topNews",
    "Reuters Business":      "https://feeds.reuters.com/reuters/businessNews",
    "BBC World":             "http://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Business":          "http://feeds.bbci.co.uk/news/business/rss.xml",
    "CNBC Top News":         "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CoinDesk":              "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph":         "https://cointelegraph.com/rss",
    "Politico":              "https://rss.politico.com/politics-news.xml",
    "Al Jazeera":            "https://www.aljazeera.com/xml/rss/all.xml",
}


def _hash_url(url: str) -> str:
    """Generate SHA256 hash of URL for deduplication."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _parse_published_date(entry) -> Optional[str]:
    """
    Extract published date from feedparser entry.
    Returns ISO 8601 UTC string, or None if unparseable.
    """
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

    # Fallback: use current time
    return datetime.now(timezone.utc).isoformat()


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


def _filter_old_articles(articles: List[Dict], max_age_hours: int = 24) -> List[Dict]:
    """Remove articles older than max_age_hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    cutoff_iso = cutoff.isoformat()

    filtered = []
    for article in articles:
        pub_date = article.get("published_at", "")
        if pub_date >= cutoff_iso:
            filtered.append(article)

    removed = len(articles) - len(filtered)
    if removed > 0:
        logger.info(f"Removed {removed} articles older than {max_age_hours}h")

    return filtered


def collect_rss() -> List[Dict]:
    """
    Collect news from all RSS feeds.

    Returns:
        List of standardized article dictionaries (deduplicated, fresh only).
    """
    logger.info("Starting RSS collection...")

    # Load existing articles for dedup
    existing = _load_existing_news()
    existing_ids = {a["id"] for a in existing}

    new_articles = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for feed_name, feed_url in RSS_FEEDS.items():
        try:
            logger.debug(f"Fetching {feed_name}...")
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"Feed error for {feed_name}: {feed.bozo_exception}")
                continue

            count = 0
            for entry in feed.entries:
                url = getattr(entry, "link", "")
                if not url:
                    continue

                article_id = _hash_url(url)

                # Deduplication
                if article_id in existing_ids:
                    continue

                article = {
                    "id": article_id,
                    "source": "rss",
                    "feed_name": feed_name,
                    "title": getattr(entry, "title", "No title"),
                    "description": getattr(entry, "summary", getattr(entry, "description", "")),
                    "url": url,
                    "published_at": _parse_published_date(entry),
                    "collected_at": now_iso,
                    "analyzed": False,
                }

                new_articles.append(article)
                existing_ids.add(article_id)
                count += 1

            logger.info(f"  {feed_name}: {count} new articles")

        except Exception as e:
            logger.warning(f"Failed to fetch {feed_name}: {e}")
            continue

    # Merge with existing, then filter old
    all_articles = existing + new_articles
    all_articles = _filter_old_articles(all_articles)

    # Save to disk
    _save_news(all_articles)

    logger.info(f"RSS collection complete. Total articles: {len(all_articles)} "
                f"(+{len(new_articles)} new)")
    return all_articles


def get_recent_news(hours: int = 6) -> List[Dict]:
    """
    Get news articles from the last N hours.

    Args:
        hours: Number of hours to look back.

    Returns:
        List of article dicts from the last N hours.
    """
    articles = _load_existing_news()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    recent = [a for a in articles if a.get("published_at", "") >= cutoff_iso]
    logger.debug(f"Found {len(recent)} articles from last {hours}h")
    return recent
