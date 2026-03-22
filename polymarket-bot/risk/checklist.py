"""
Pre-Execution Checklist for the Polymarket Trading Bot.

6 mandatory checks before every trade execution.
ALL must pass — if any fails, the trade is SKIPPED.
"""

from utils.logger import get_logger

logger = get_logger(__name__)


def pre_execution_checklist(
    trade_data: dict,
    bankroll: float,
    active_positions: int,
) -> dict:
    """
    Validate 6 checkpoints before trade execution.

    trade_data must contain:
        - ev_net:              float (expected value after fees)
        - edge_pct:            float (edge percentage)
        - confidence:          str   ("LOW", "MEDIUM", "HIGH")
        - bet_size:            float (proposed bet in USDC)
        - base_rate:           float (must not be None)
        - market_volume:       float (market volume in USDC)
        - hours_to_resolution: float (hours until market resolves)

    Args:
        trade_data:       Dict with trade analysis data.
        bankroll:         Current bankroll in USDC.
        active_positions: Number of currently active positions.

    Returns:
        Dict with:
            - passed:        bool (True if all checks pass)
            - checks:        dict of individual check results
            - failed_checks: list of failed check names
    """
    checks = {
        "ev_positive":        trade_data.get("ev_net", 0) > 0,
        "edge_sufficient":    trade_data.get("edge_pct", 0) > 12.0,
        "confidence_ok":      trade_data.get("confidence", "LOW") != "LOW",
        "position_size_safe": trade_data.get("bet_size", 0) <= bankroll * 0.15,
        "market_liquid":      trade_data.get("market_volume", 0) >= 10_000,
        "not_overexposed":    active_positions < 3,
    }

    failed = [name for name, passed in checks.items() if not passed]

    result = {
        "passed": len(failed) == 0,
        "checks": checks,
        "failed_checks": failed,
    }

    if result["passed"]:
        logger.info("✅ Pre-execution checklist: ALL PASSED")
    else:
        logger.info(f"❌ Pre-execution checklist FAILED: {', '.join(failed)}")

    return result
