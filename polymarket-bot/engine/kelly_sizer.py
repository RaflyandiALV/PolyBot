"""
Kelly Criterion Bet Sizer for the Polymarket Trading Bot.

Implements Half-Kelly with confidence-based uncertainty adjustment.
Hard limits: max 15% bankroll, min $5 bet, 10% max if bankroll < $50.
"""

from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_bet_size(
    ai_probability: float,
    market_price: float,
    bankroll: float,
    confidence: str,
    kelly_fraction: float = 0.5,
    news_count: int = 0,
) -> dict:
    """
    Hitung ukuran bet optimal menggunakan Half-Kelly Criterion.

    Uncertainty multiplier berdasarkan confidence:
    - HIGH:   1.0  (pakai full Half-Kelly)
    - MEDIUM: 0.5  (pakai Quarter-Kelly) - dikurangi 50% lagi jika news_count < 2
    - LOW:    0.0  (SKIP, jangan bet)

    Hard limits yang tidak boleh dilanggar:
    - Maximum 15% bankroll per trade
    - Minimum bet: $5 (di bawah ini tidak worth the fee)
    - Kalau bankroll < $50: maximum 10% per trade

    Args:
        ai_probability: AI's estimated probability (0.0-1.0).
        market_price:   Current market price (0.0-1.0).
        bankroll:       Current total bankroll in USDC.
        confidence:     "LOW", "MEDIUM", or "HIGH" from AI.
        kelly_fraction: Kelly fraction to use (default 0.5 = Half-Kelly).
        news_count:     Number of relevant news articles found for this market.

    Returns:
        Dict with bet_size, kelly_full_pct, kelly_applied_pct, bankroll_pct, reason.
    """
    # Kalau confidence LOW, langsung return 0
    if confidence == "LOW":
        logger.info("Bet size = $0 (confidence LOW, skipping)")
        return {"bet_size": 0, "reason": "Confidence too low, skipping"}

    # Guard: bankroll must be positive
    if bankroll <= 0:
        return {"bet_size": 0, "reason": "No bankroll remaining"}

    # Guard: valid market price
    if market_price <= 0 or market_price >= 1:
        return {"bet_size": 0, "reason": "Invalid market price"}

    # Kelly formula: f* = (p*b - q) / b
    # b = net payout ratio = (1/market_price) - 1
    p = ai_probability
    q = 1 - ai_probability
    b = (1 / market_price) - 1

    if b <= 0:
        return {"bet_size": 0, "reason": "Invalid odds"}

    kelly_full = (p * b - q) / b

    # Kalau Kelly negatif, jangan bet
    if kelly_full <= 0:
        logger.info(f"Bet size = $0 (negative Kelly: {kelly_full:.4f})")
        return {"bet_size": 0, "reason": "Negative Kelly, no edge"}

    # Apply fraction
    kelly_adjusted = kelly_full * kelly_fraction

    # Apply uncertainty multiplier
    uncertainty_multiplier = {"HIGH": 1.0, "MEDIUM": 0.5}.get(confidence, 0)
    
    # PENALTY: Trades with MEDIUM confidence and VERY LOW news count (e.g., < 2)
    if confidence == "MEDIUM" and news_count < 2:
        logger.info(f"Penalizing Kelly for MEDIUM confidence but low news count ({news_count})")
        uncertainty_multiplier *= 0.5  # Reduce by half again (so 0.25 total multiplier)

    kelly_adjusted *= uncertainty_multiplier

    # Calculate raw bet size
    raw_bet = bankroll * kelly_adjusted

    # Apply hard limits
    max_bet = bankroll * (0.10 if bankroll < 50 else 0.15)
    min_bet = 5.0

    final_bet = max(min_bet, min(raw_bet, max_bet))

    # Final check: jangan bet kalau melebihi bankroll
    final_bet = min(final_bet, bankroll * 0.95)

    # If final bet is below minimum and raw was also below, skip
    if raw_bet < min_bet and bankroll >= min_bet * 2:
        logger.info(f"Bet size = $0 (Kelly too small: ${raw_bet:.2f} < min ${min_bet})")
        return {"bet_size": 0, "reason": f"Kelly size ${raw_bet:.2f} below minimum ${min_bet}"}

    result = {
        "bet_size": round(final_bet, 2),
        "kelly_full_pct": round(kelly_full * 100, 2),
        "kelly_applied_pct": round(kelly_adjusted * 100, 2),
        "bankroll_pct": round(final_bet / bankroll * 100, 2),
        "reason": f"Half-Kelly × {uncertainty_multiplier} uncertainty multiplier",
    }

    logger.info(
        f"Bet size: ${result['bet_size']:.2f} "
        f"({result['bankroll_pct']:.1f}% bankroll) | "
        f"Kelly full: {result['kelly_full_pct']:.1f}% | "
        f"Confidence: {confidence}"
    )

    return result
