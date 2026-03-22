"""
Telegram Alert Module for the Polymarket Trading Bot.

Sends notifications to Telegram. OPTIONAL — silently skips
if TELEGRAM_BOT_TOKEN is not configured in .env.

Rate limited: max 1 alert per minute.
"""

import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

from utils.logger import get_logger

logger = get_logger(__name__)
load_dotenv()

# Rate limiting
_last_sent_time: float = 0.0
_MIN_INTERVAL_SECONDS = 60  # 1 alert per minute max


def _get_config() -> tuple:
    """Get Telegram bot token and chat ID from env."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    return token, chat_id


def _is_configured() -> bool:
    """Check if Telegram alerts are configured."""
    token, chat_id = _get_config()
    return bool(token and chat_id
                and token != "your_telegram_bot_token_here"
                and chat_id != "your_chat_id_here")


def _rate_limited() -> bool:
    """Check if we're rate limited."""
    global _last_sent_time
    now = time.time()
    if now - _last_sent_time < _MIN_INTERVAL_SECONDS:
        return True
    return False


def send_message(text: str) -> bool:
    """
    Send a message to Telegram.

    Args:
        text: Message text (supports Telegram markdown).

    Returns:
        True if sent successfully, False otherwise.
    """
    global _last_sent_time

    if not _is_configured():
        logger.debug("Telegram not configured, skipping alert")
        return False

    if _rate_limited():
        logger.debug("Telegram rate limited, skipping")
        return False

    token, chat_id = _get_config()

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )

        if response.status_code == 200:
            _last_sent_time = time.time()
            logger.debug(f"Telegram alert sent: {text[:50]}...")
            return True
        else:
            logger.warning(f"Telegram API error: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.warning(f"Telegram send failed: {e}")
        return False


# ========== Alert Functions ==========

def alert_bot_started(balance: float, day: int) -> bool:
    """Alert: Bot started."""
    return send_message(f"🚀 Bot started. Balance: ${balance:.2f} | Day: {day}")


def alert_buy_signal(
    side: str,
    question: str,
    edge_pct: float,
    bet_size: float,
    confidence: str,
    reasoning: str = "",
) -> bool:
    """Alert: BUY signal detected with reasoning."""
    question_short = question[:70]
    msg = (
        f"📈 *BUY {side}* | {question_short}...\n"
        f"Edge: {edge_pct:.1f}% | Bet: ${bet_size:.2f} | Conf: {confidence}"
    )
    if reasoning:
        msg += f"\n\n🤖 *AI Reasoning:*\n_{reasoning}_"
    
    return send_message(msg)


def alert_position_win(pnl: float, new_balance: float) -> bool:
    """Alert: Position closed with WIN."""
    return send_message(f"✅ WIN +${pnl:.2f} | New balance: ${new_balance:.2f}")


def alert_position_loss(pnl: float, new_balance: float) -> bool:
    """Alert: Position closed with LOSS."""
    return send_message(f"❌ LOSS -${abs(pnl):.2f} | New balance: ${new_balance:.2f}")


def alert_death(days_survived: int, final_balance: float) -> bool:
    """Alert: System DEAD."""
    return send_message(
        f"💀 SYSTEM DEAD | Survived: {days_survived} days | "
        f"Final: ${final_balance:.2f}"
    )


def alert_status(
    balance: float,
    day: int,
    target: float,
    active_positions: int,
) -> bool:
    """Alert: Periodic status update (every 6 hours)."""
    return send_message(
        f"📊 Status | Balance: ${balance:.2f} | Day {day} | "
        f"Target: ${target:.2f} | Positions: {active_positions} active"
    )
