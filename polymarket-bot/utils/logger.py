"""
Centralized logging module for the Polymarket Trading Bot.

All modules should import the logger from here:
    from utils.logger import get_logger
    logger = get_logger(__name__)

Output: console AND file (data/bot.log) simultaneously.
Format: [TIMESTAMP] [LEVEL] [MODULE] message
"""

import logging
import os
import sys
from pathlib import Path


# Resolve data directory relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _PROJECT_ROOT / "data"
_LOG_FILE = _LOG_DIR / "bot.log"

# Custom formatter
_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Track whether root logger has been configured
_configured = False


def _setup_root_logger() -> None:
    """Configure root logger with console and file handlers (once only)."""
    global _configured
    if _configured:
        return

    # Ensure data directory exists
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("polybot")
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler — DEBUG and above (captures everything)
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger under the 'polybot' namespace.

    Args:
        name: Module name, typically __name__.

    Returns:
        Configured logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Bot started")
    """
    _setup_root_logger()
    return logging.getLogger(f"polybot.{name}")
