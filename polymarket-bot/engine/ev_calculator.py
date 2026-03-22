"""
Expected Value Calculator for the Polymarket Trading Bot.

Calculates EV with Polymarket's 2% profit fee.
Supports both YES and NO sides.
"""

from utils.logger import get_logger

logger = get_logger(__name__)

POLYMARKET_FEE = 0.02  # 2% dari profit


def calculate_ev(
    ai_probability: float,
    market_price: float,
    stake: float,
    side: str,
) -> dict:
    """
    Hitung Expected Value dengan fee.

    Untuk BUY YES di harga 0.40:
    - Kalau menang: dapat $1.00 per share, profit = (1/0.40 - 1) × stake
    - Kalau kalah: kehilangan stake
    - Fee: 2% dari profit saja (bukan dari total)

    Args:
        ai_probability: AI's estimated probability (0.0-1.0).
        market_price:   Current market price (0.0-1.0).
        stake:          Amount in USDC to bet.
        side:           "YES" or "NO".

    Returns:
        Dict with ev_raw, ev_net, edge, edge_pct, profitable, fee_cost.
    """
    # Kalau side = "NO", flip probabilitas
    if side == "NO":
        ai_probability = 1 - ai_probability
        market_price = 1 - market_price

    # Guard against division by zero or invalid prices
    if market_price <= 0 or market_price >= 1:
        logger.warning(f"Invalid market_price: {market_price}")
        return {
            "ev_raw": 0.0,
            "ev_net": 0.0,
            "edge": 0.0,
            "edge_pct": 0.0,
            "profitable": False,
            "fee_cost": 0.0,
        }

    # Potential profit per unit stake
    potential_profit = stake * (1 / market_price - 1)

    # EV tanpa fee
    ev_raw = (ai_probability * potential_profit) + \
             ((1 - ai_probability) * (-stake))

    # Fee hanya dari profit (bukan dari loss)
    fee = potential_profit * POLYMARKET_FEE

    # EV bersih
    ev_net = ev_raw - (ai_probability * fee)

    # Edge = selisih probabilitas
    edge = ai_probability - market_price

    result = {
        "ev_raw": round(ev_raw, 4),
        "ev_net": round(ev_net, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge * 100, 2),
        "profitable": ev_net > 0,
        "fee_cost": round(ai_probability * fee, 4),
    }

    logger.debug(
        f"EV calc: side={side}, prob={ai_probability:.2f}, "
        f"price={market_price:.2f}, edge={result['edge_pct']}%, "
        f"ev_net=${result['ev_net']:.4f}"
    )

    return result
