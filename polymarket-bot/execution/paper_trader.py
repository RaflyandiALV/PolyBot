"""
Paper Trader — Simulated trade execution.

No real money involved. Simulates market resolution using
AI probability + Gaussian noise.
"""

import random
from typing import Dict, Optional

from risk.survival_engine import SurvivalEngine
from utils.logger import get_logger

logger = get_logger(__name__)


class PaperTrader:
    """Simulates trade execution for paper trading mode."""

    def __init__(self, survival: SurvivalEngine):
        self.survival = survival

    def execute_buy(self, decision: Dict) -> Optional[Dict]:
        """
        Execute a simulated BUY order.

        Args:
            decision: Decision dict from decision_engine (action must be "BUY").

        Returns:
            Position dict, or None if execution failed.
        """
        if decision.get("action") != "BUY":
            logger.warning("PaperTrader.execute_buy called with non-BUY decision")
            return None

        bet_size = decision.get("bet_size", 0)
        if bet_size <= 0:
            logger.warning("Bet size is 0, skipping")
            return None

        if bet_size > self.survival.balance:
            logger.warning(
                f"Bet size ${bet_size:.2f} exceeds balance "
                f"${self.survival.balance:.2f}, skipping"
            )
            return None

        # Open position via survival engine
        trade_data = {
            "market_id": decision.get("market_id", ""),
            "question": decision.get("question", ""),
            "side": decision.get("side", "YES"),
            "entry_price": decision.get("entry_price", 0.5),
            "bet_size": bet_size,
            "ai_probability": decision.get("ai_probability", 0.5),
            "edge_pct": decision.get("edge_pct", 0),
        }

        position = self.survival.open_position(trade_data)
        logger.info(
            f"[PAPER] Executed BUY: {decision['side']} "
            f"'{decision['question'][:50]}' | "
            f"Cost: ${bet_size:.2f}"
        )

        return position

    def simulate_market_resolution(
        self,
        position: Dict,
        actual_prob: Optional[float] = None,
    ) -> Dict:
        """
        Simulate market resolution for a position.

        If actual_prob is not provided, uses AI probability + Gaussian noise
        to create a realistic simulation where AI isn't always right.

        Args:
            position:    Position dict from survival engine.
            actual_prob: Optional override probability for testing.

        Returns:
            Dict with outcome details.
        """
        position_id = position["position_id"]
        ai_prob = position.get("ai_probability", 0.5)
        side = position.get("side", "YES")

        # Determine resolution probability
        if actual_prob is not None:
            resolution_prob = actual_prob
        else:
            # Add Gaussian noise to simulate real-world uncertainty
            noise = random.gauss(0, 0.1)  # mean=0, std=0.1
            resolution_prob = max(0, min(1, ai_prob + noise))

        # Determine outcome
        market_resolves_yes = random.random() < resolution_prob

        if side == "YES":
            won = market_resolves_yes
        else:
            won = not market_resolves_yes

        outcome = "WIN" if won else "LOSS"

        # Close position
        closed = self.survival.close_position(
            position_id=position_id,
            outcome=outcome,
            final_price=1.0 if won else 0.0,
        )

        result = {
            "position_id": position_id,
            "question": position.get("question", ""),
            "side": side,
            "outcome": outcome,
            "ai_probability": ai_prob,
            "resolution_probability": round(resolution_prob, 4),
            "pnl": closed["pnl"] if closed else 0,
            "new_balance": self.survival.balance,
        }

        logger.info(
            f"[PAPER] Resolution: {outcome} | "
            f"'{position['question'][:40]}' | "
            f"PnL: ${result['pnl']:+.2f} | "
            f"Balance: ${result['new_balance']:.2f}"
        )

        return result

    def check_and_resolve_expiring(self, hours_threshold: float = 2.0) -> list:
        """
        Check for positions nearing resolution and simulate them.

        Args:
            hours_threshold: Resolve positions expiring within this many hours.

        Returns:
            List of resolution result dicts.
        """
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        results = []

        # Copy the list since we're modifying it during iteration
        positions = list(self.survival.active_positions)

        for position in positions:
            # For paper trading, simulate resolution after some time
            opened_at_str = position.get("opened_at", "")
            try:
                opened_at = datetime.fromisoformat(opened_at_str)
                elapsed_hours = (now - opened_at).total_seconds() / 3600

                # Simulate resolution if position has been open > threshold hours
                if elapsed_hours >= hours_threshold:
                    logger.info(
                        f"Position {position['position_id']} has been open "
                        f"{elapsed_hours:.1f}h, simulating resolution..."
                    )
                    result = self.simulate_market_resolution(position)
                    results.append(result)

            except (ValueError, TypeError):
                continue

        if results:
            logger.info(f"Resolved {len(results)} expiring positions")

        return results
