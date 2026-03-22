"""
Decision Engine — Main orchestrator for the Polymarket Trading Bot.

Combines all engines: base rate → news matching → AI analysis →
EV calculation → Kelly sizing → pre-execution checklist → BUY/SKIP.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from engine import base_rate
from engine import ai_analyzer
from engine import ev_calculator
from engine import kelly_sizer
from risk.checklist import pre_execution_checklist
from risk.survival_engine import SurvivalEngine
from collector.rss_collector import get_recent_news
from utils.logger import get_logger

logger = get_logger(__name__)


def _find_relevant_news(market_question: str, news_articles: List[Dict]) -> List[Dict]:
    """
    Find news articles relevant to a market question using keyword matching.

    Args:
        market_question: The market question string.
        news_articles:   List of news article dicts.

    Returns:
        List of relevant articles (max 10).
    """
    if not news_articles:
        return []

    # Extract keywords from market question (words > 3 chars, excluding common words)
    stop_words = {
        "will", "the", "this", "that", "what", "when", "where", "which",
        "have", "been", "with", "from", "they", "their", "about", "would",
        "could", "should", "does", "more", "than", "into", "over", "under",
        "before", "after", "during",
    }

    question_words = set()
    for word in market_question.lower().split():
        # Remove punctuation
        cleaned = "".join(c for c in word if c.isalnum())
        if len(cleaned) > 3 and cleaned not in stop_words:
            question_words.add(cleaned)

    if not question_words:
        return []

    # Score articles by keyword overlap
    scored = []
    for article in news_articles:
        title = article.get("title", "").lower()
        description = article.get("description", "").lower()
        text = f"{title} {description}"

        score = sum(1 for word in question_words if word in text)
        if score > 0:
            scored.append((score, article))

    # Sort by relevance score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    return [article for _, article in scored[:10]]


def _calculate_hours_to_resolution(end_date_str: str) -> float:
    """Calculate hours until market resolution."""
    try:
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = end_date - now
        return max(0, delta.total_seconds() / 3600)
    except (ValueError, TypeError):
        return 168.0  # Default 7 days


def evaluate_market(
    market: Dict,
    survival: SurvivalEngine,
    news_articles: Optional[List[Dict]] = None,
) -> Dict:
    """
    Run the full decision pipeline on a single market.

    Flow:
        Step 0: Base Rate → classify market, get prior probability
        Step 1: Find relevant news from last 6h
        Step 2: AI Analysis (Claude API / mock) — Bayesian update
        Step 3: EV Calculation with fees
        Step 4: Kelly bet sizing
        Step 5: Pre-execution checklist
        Step 6: Output BUY or SKIP decision

    Args:
        market:        Market dict from market_collector.
        survival:      SurvivalEngine instance.
        news_articles: Optional pre-fetched news articles.

    Returns:
        Decision dict with action, market info, analysis results.
    """
    question = market.get("question", "Unknown")
    market_id = market.get("condition_id", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info(f"\n[EVALUATING] {question[:100]}")

    # ========== STEP 0 — Base Rate ==========
    category = base_rate.classify_market(question)
    prior = base_rate.get_base_rate(category)
    logger.info(f"Step 0 | Category: {category} | Base rate: {prior:.2f}")

    # ========== STEP 1 — Find relevant news ==========
    if news_articles is None:
        news_articles = get_recent_news(hours=6)

    relevant_news = _find_relevant_news(question, news_articles)

    if not relevant_news:
        logger.info(f"Step 1 | No relevant news found → SKIP")
        return _skip_decision(market_id, question, "No relevant news", now_iso)

    logger.info(f"Step 1 | Found {len(relevant_news)} relevant articles")

    # ========== STEP 2 — AI Analysis (Bayesian update) ==========
    market_price = market.get("best_ask_yes", 0.5)
    end_date = market.get("end_date", "")

    ai_result = ai_analyzer.analyze(
        question=question,
        market_price=market_price,
        base_rate=prior,
        category=category,
        end_date=end_date,
        news=relevant_news,
    )

    if ai_result is None:
        logger.info(f"Step 2 | AI analysis failed → SKIP")
        return _skip_decision(market_id, question, "AI analysis failed", now_iso)

    ai_prob = ai_result["probability"]
    confidence = ai_result["confidence"]
    logger.info(f"Step 2 | AI prob: {ai_prob:.2f} | Confidence: {confidence}")

    # ========== STEP 3 — Determine side and EV ==========
    side = "YES" if ai_prob > 0.5 else "NO"
    trade_price = market_price if side == "YES" else market.get("best_ask_no", 1 - market_price)

    ev_data = ev_calculator.calculate_ev(
        ai_probability=ai_prob,
        market_price=market_price,
        stake=100,  # Dummy stake for calculation
        side=side,
    )
    logger.info(f"Step 3 | Side: {side} | Edge: {ev_data['edge_pct']}% | EV: ${ev_data['ev_net']:.4f}")

    # ========== STEP 4 — Kelly Sizing ==========
    sizing = kelly_sizer.calculate_bet_size(
        ai_probability=ai_prob if side == "YES" else (1 - ai_prob),
        market_price=trade_price,
        bankroll=survival.balance,
        confidence=confidence,
        news_count=len(relevant_news),
    )

    bet_size = sizing.get("bet_size", 0)

    if bet_size <= 0:
        reason = sizing.get("reason", "Kelly returned zero bet")
        logger.info(f"Step 4 | Bet size: $0.00 ({reason}) → SKIP")
        return _skip_decision(market_id, question, reason, now_iso)
        
    logger.info(f"Step 4 | Bet size: ${bet_size:.2f}")

    # ========== STEP 5 — Pre-execution Checklist ==========
    hours_to_resolution = _calculate_hours_to_resolution(end_date)

    trade_data = {
        "ev_net": ev_data["ev_net"],
        "edge_pct": ev_data["edge_pct"],
        "confidence": confidence,
        "bet_size": bet_size,
        "base_rate": prior,
        "market_volume": market.get("volume", 0),
        "hours_to_resolution": hours_to_resolution,
    }

    check = pre_execution_checklist(
        trade_data=trade_data,
        bankroll=survival.balance,
        active_positions=len(survival.active_positions),
    )

    if not check["passed"]:
        reason = f"Checklist failed: {', '.join(check['failed_checks'])}"
        logger.info(f"Step 5 | {reason} → SKIP")
        return _skip_decision(market_id, question, reason, now_iso)

    # ========== STEP 6 — BUY signal ==========
    decision = {
        "action": "BUY",
        "market_id": market_id,
        "question": question,
        "side": side,
        "entry_price": trade_price,
        "bet_size": bet_size,
        "ai_probability": ai_prob,
        "market_probability": market_price,
        "edge_pct": ev_data["edge_pct"],
        "ev_net": ev_data["ev_net"],
        "confidence": confidence,
        "reasoning": ai_result.get("reasoning", ""),
        "skip_reason": None,
        "timestamp": now_iso,
    }

    logger.info(
        f"🟢 BUY SIGNAL | {side} '{question[:50]}' | "
        f"Edge: {ev_data['edge_pct']}% | Bet: ${bet_size:.2f} | "
        f"Conf: {confidence}"
    )

    return decision


def _skip_decision(market_id: str, question: str, reason: str, timestamp: str) -> Dict:
    """Create a SKIP decision."""
    return {
        "action": "SKIP",
        "market_id": market_id,
        "question": question,
        "side": None,
        "entry_price": None,
        "bet_size": 0,
        "ai_probability": None,
        "market_probability": None,
        "edge_pct": None,
        "ev_net": None,
        "confidence": None,
        "reasoning": None,
        "skip_reason": reason,
        "timestamp": timestamp,
    }


def run_analysis_cycle(
    markets: List[Dict],
    survival: SurvivalEngine,
) -> List[Dict]:
    """
    Run decision engine on all markets.

    Args:
        markets:  List of market dicts.
        survival: SurvivalEngine instance.

    Returns:
        List of all decisions (BUY and SKIP).
    """
    logger.info(f"\n=== Starting analysis cycle: {len(markets)} markets ===")

    # Pre-fetch news once for all markets
    news_articles = get_recent_news(hours=6)
    logger.info(f"Loaded {len(news_articles)} articles from last 6h")

    decisions = []
    buy_count = 0

    for market in markets:
        decision = evaluate_market(market, survival, news_articles)
        decisions.append(decision)

        if decision["action"] == "BUY":
            buy_count += 1

    logger.info(f"\nCycle complete: {buy_count} BUY / {len(decisions) - buy_count} SKIP")
    return decisions
