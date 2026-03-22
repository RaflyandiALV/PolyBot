"""
Live Trader — Polymarket CLOB API wrapper.

GUARDED: Every function raises RuntimeError if PAPER_TRADING=true.
This module is ONLY active when PAPER_TRADING=false in .env.
"""

import os
from typing import Dict, Optional

from dotenv import load_dotenv

from utils.logger import get_logger

logger = get_logger(__name__)
load_dotenv()


def _check_live_mode() -> None:
    """Guard: raise error if still in paper trading mode."""
    if os.getenv("PAPER_TRADING", "true").lower() == "true":
        raise RuntimeError(
            "PAPER_TRADING=true. Set PAPER_TRADING=false di .env untuk live trading."
        )


class LiveTrader:
    """Polymarket CLOB API wrapper for live trading."""

    def __init__(self):
        _check_live_mode()
        self.client = self.get_client()

    def get_client(self):
        """
        Initialize ClobClient with credentials from .env.

        Returns:
            Configured ClobClient instance.
        """
        _check_live_mode()

        api_key = os.getenv("POLY_API_KEY", "")
        api_secret = os.getenv("POLY_API_SECRET", "")
        passphrase = os.getenv("POLY_PASSPHRASE", "")
        private_key = os.getenv("POLY_PRIVATE_KEY", "")

        if not all([api_key, api_secret, passphrase, private_key]):
            raise RuntimeError(
                "Missing Polymarket credentials. Check .env file: "
                "POLY_API_KEY, POLY_API_SECRET, POLY_PASSPHRASE, POLY_PRIVATE_KEY"
            )

        try:
            from py_clob_client.client import ClobClient

            client = ClobClient(
                host="https://clob.polymarket.com",
                key=private_key,
                chain_id=137,  # Polygon mainnet
                creds={
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "api_passphrase": passphrase,
                },
            )

            logger.info("ClobClient initialized for live trading")
            return client

        except ImportError:
            raise RuntimeError(
                "py-clob-client not installed. Run: pip install py-clob-client"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ClobClient: {e}")

    def place_order(
        self,
        market_id: str,
        side: str,
        price: float,
        size: float,
    ) -> Optional[Dict]:
        """
        Place a limit order on Polymarket.

        Args:
            market_id: The condition ID of the market.
            side:      "YES" or "NO".
            price:     Limit price (0.0-1.0).
            size:      Number of shares.

        Returns:
            Order response dict, or None on failure.
        """
        _check_live_mode()

        try:
            logger.info(
                f"[LIVE] Placing order: {side} {market_id} | "
                f"Price: ${price:.2f} | Size: {size}"
            )

            # Build order
            order = self.client.create_order(
                token_id=market_id,
                price=price,
                size=size,
                side="BUY",
            )

            result = self.client.post_order(order)

            logger.info(f"[LIVE] Order placed: {result}")
            return result

        except Exception as e:
            logger.error(f"[LIVE] Order failed: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order.

        Args:
            order_id: The ID of the order to cancel.

        Returns:
            True if cancelled successfully.
        """
        _check_live_mode()

        try:
            self.client.cancel(order_id)
            logger.info(f"[LIVE] Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"[LIVE] Cancel failed for {order_id}: {e}")
            return False

    def get_balance(self) -> Optional[float]:
        """
        Check USDC balance in proxy wallet.

        Returns:
            Balance in USDC, or None on failure.
        """
        _check_live_mode()

        try:
            balance = self.client.get_balance()
            logger.info(f"[LIVE] Wallet balance: ${balance}")
            return float(balance)
        except Exception as e:
            logger.error(f"[LIVE] Failed to get balance: {e}")
            return None
