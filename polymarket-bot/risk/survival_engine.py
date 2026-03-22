"""
Survival Engine — "Survive or Die" system.

Tracks bankroll, active positions, daily targets, and trade history.
All state persists to disk — survives laptop sleep/restart.
Death condition: balance < $10.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from utils.logger import get_logger

logger = get_logger(__name__)
load_dotenv()

# Project root and data paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_STATE_FILE = _PROJECT_ROOT / "data" / "survival" / "state.json"
_LOG_FILE = _PROJECT_ROOT / "data" / "survival" / "log.json"

# Config
_DEATH_THRESHOLD = 10.0
_STARTING_BALANCE = float(os.getenv("STARTING_BALANCE", "1000.0"))
_DAILY_TARGET_PCT = float(os.getenv("DAILY_TARGET_PCT", "0.25"))


class SurvivalEngine:
    """Manages bot bankroll, positions, and survival state."""

    def __init__(self):
        self.state = self.load_state()

    @property
    def balance(self) -> float:
        return self.state["balance"]

    @property
    def active_positions(self) -> List[Dict]:
        return self.state["active_positions"]

    def load_state(self) -> Dict:
        """
        Load state from disk. Create default state if file doesn't exist.

        Returns:
            State dictionary.
        """
        if _STATE_FILE.exists():
            try:
                with open(_STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                logger.info(f"Loaded state: balance=${state['balance']:.2f}, "
                            f"day={state['day_number']}, "
                            f"positions={len(state.get('active_positions', []))}")
                return state
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error loading state: {e}. Creating fresh state.")

        # Default starting state
        state = {
            "balance": _STARTING_BALANCE,
            "day_number": 1,
            "day_start_balance": _STARTING_BALANCE,
            "target_balance": _STARTING_BALANCE * (1 + _DAILY_TARGET_PCT),
            "active_positions": [],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_trades": 0,
            "winning_trades": 0,
        }

        self.state = state
        self.save_state()
        logger.info(f"Created fresh state: balance=${state['balance']:.2f}")
        return state

    def save_state(self) -> None:
        """Write current state to disk. Called after every balance change."""
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

        logger.debug(f"State saved: balance=${self.state['balance']:.2f}")

    def open_position(self, trade_data: Dict) -> Dict:
        """
        Open a new trading position.

        Args:
            trade_data: Dict with market_id, question, side, entry_price,
                        bet_size, ai_probability, edge_pct.

        Returns:
            The created position dict.
        """
        position_id = str(uuid.uuid4())[:8]
        entry_price = trade_data["entry_price"]
        cost = trade_data["bet_size"]
        shares = cost / entry_price if entry_price > 0 else 0

        position = {
            "position_id": position_id,
            "market_id": trade_data.get("market_id", ""),
            "question": trade_data.get("question", ""),
            "side": trade_data.get("side", "YES"),
            "entry_price": entry_price,
            "shares": round(shares, 4),
            "cost": cost,
            "ai_probability": trade_data.get("ai_probability", 0.5),
            "edge_pct": trade_data.get("edge_pct", 0),
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "status": "OPEN",
        }

        # Deduct cost from balance
        self.state["balance"] -= cost
        self.state["active_positions"].append(position)
        self.state["total_trades"] += 1
        self.save_state()

        logger.info(
            f"📈 Opened position {position_id}: {position['side']} "
            f"'{position['question'][:50]}' | "
            f"Cost: ${cost:.2f} | Shares: {shares:.2f} | "
            f"Balance: ${self.state['balance']:.2f}"
        )

        return position

    def close_position(
        self,
        position_id: str,
        outcome: str,
        final_price: float = 1.0,
    ) -> Optional[Dict]:
        """
        Close an existing position.

        Args:
            position_id: UUID of the position.
            outcome:     "WIN" or "LOSS".
            final_price: Final price at resolution (1.0 for win, 0.0 for loss).

        Returns:
            The closed position dict, or None if not found.
        """
        position = None
        idx = None

        for i, pos in enumerate(self.state["active_positions"]):
            if pos["position_id"] == position_id:
                position = pos
                idx = i
                break

        if position is None:
            logger.warning(f"Position {position_id} not found")
            return None

        # Calculate PnL
        cost = position["cost"]
        if outcome == "WIN":
            # Revenue = shares × $1.00, profit = revenue - cost
            revenue = position["shares"] * 1.0
            profit = revenue - cost
            fee = profit * 0.02  # 2% fee on profit
            net_pnl = profit - fee
            self.state["balance"] += cost + net_pnl  # Return cost + profit
            self.state["winning_trades"] += 1
            emoji = "✅"
        else:
            net_pnl = -cost  # Lose entire stake (already deducted)
            emoji = "❌"

        # Update position
        position["status"] = "CLOSED"
        position["closed_at"] = datetime.now(timezone.utc).isoformat()
        position["outcome"] = outcome
        position["pnl"] = round(net_pnl, 4)

        # Remove from active
        self.state["active_positions"].pop(idx)
        self.save_state()

        logger.info(
            f"{emoji} Closed position {position_id}: {outcome} | "
            f"PnL: ${net_pnl:+.2f} | Balance: ${self.state['balance']:.2f}"
        )

        return position

    def start_new_day(self) -> None:
        """
        Start a new trading day.
        Reset daily target. Log the previous day to log.json.
        """
        # Log previous day
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_log = {
            "date": today,
            "day_number": self.state["day_number"],
            "starting_balance": self.state["day_start_balance"],
            "ending_balance": self.state["balance"],
            "target_balance": self.state["target_balance"],
            "target_achieved": self.state["balance"] >= self.state["target_balance"],
            "trades_today": [],  # Will be filled by paper_trader
            "death": False,
        }

        self._append_log(day_log)

        # Advance day
        self.state["day_number"] += 1
        self.state["day_start_balance"] = self.state["balance"]
        self.state["target_balance"] = round(
            self.state["balance"] * (1 + _DAILY_TARGET_PCT), 2
        )
        self.save_state()

        logger.info(
            f"📅 Day {self.state['day_number']} started | "
            f"Balance: ${self.state['balance']:.2f} | "
            f"Target: ${self.state['target_balance']:.2f}"
        )

    def check_death(self) -> bool:
        """
        Check if balance is below death threshold.

        Returns:
            True if DEAD (balance < $10).
        """
        if self.state["balance"] < _DEATH_THRESHOLD:
            logger.critical(
                f"💀 SYSTEM DEAD | Balance: ${self.state['balance']:.2f} | "
                f"Survived: {self.state['day_number']} days | "
                f"Total trades: {self.state['total_trades']} | "
                f"Win rate: {self._win_rate():.1f}%"
            )

            # Log death
            day_log = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "day_number": self.state["day_number"],
                "starting_balance": self.state["day_start_balance"],
                "ending_balance": self.state["balance"],
                "target_balance": self.state["target_balance"],
                "target_achieved": False,
                "trades_today": [],
                "death": True,
            }
            self._append_log(day_log)

            return True
        return False

    def get_status_summary(self) -> Dict:
        """
        Get current status summary for display.

        Returns:
            Dict with all relevant status information.
        """
        today_pnl = self.state["balance"] - self.state["day_start_balance"]

        return {
            "balance": round(self.state["balance"], 2),
            "day_number": self.state["day_number"],
            "day_start_balance": round(self.state["day_start_balance"], 2),
            "target_balance": round(self.state["target_balance"], 2),
            "today_pnl": round(today_pnl, 2),
            "active_positions": len(self.state["active_positions"]),
            "total_trades": self.state["total_trades"],
            "win_rate": round(self._win_rate(), 1),
            "last_updated": self.state["last_updated"],
        }

    def _win_rate(self) -> float:
        """Calculate win rate percentage."""
        total = self.state["total_trades"]
        if total == 0:
            return 0.0
        return (self.state["winning_trades"] / total) * 100

    def _append_log(self, entry: Dict) -> None:
        """Append entry to log.json (append-only, never overwrite)."""
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        logs = []
        if _LOG_FILE.exists():
            try:
                with open(_LOG_FILE, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, IOError):
                logs = []

        logs.append(entry)

        with open(_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

        logger.debug(f"Appended log entry for day {entry.get('day_number', '?')}")
