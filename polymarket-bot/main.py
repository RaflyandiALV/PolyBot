"""
Polymarket Trading Bot — Main Entry Point

Usage:
    python main.py --mode paper     ← paper trading (default)
    python main.py --mode live      ← live trading (needs PAPER_TRADING=false)
    python main.py --mode once      ← single analysis cycle, then exit
    python main.py --mode status    ← show status, no trading
    python main.py --mode backtest  ← analyze log.json statistics
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

from utils.logger import get_logger
from utils.sleep_prevention import prevent_sleep, allow_sleep
from risk.survival_engine import SurvivalEngine
from engine.decision_engine import run_analysis_cycle
from execution.paper_trader import PaperTrader
from collector.rss_collector import collect_rss
from collector.newsapi_collector import collect_newsapi
from collector.market_collector import collect_markets, get_active_markets
from monitoring.telegram_alert import (
    alert_bot_started, alert_buy_signal, alert_position_win,
    alert_position_loss, alert_death, alert_status,
)

logger = get_logger("main")

# Track state for graceful shutdown
_running = True
_iteration = 0


def _signal_handler(sig, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global _running
    logger.info("\n⚠️  Shutdown signal received. Saving state...")
    _running = False


def _display_status(survival: SurvivalEngine) -> None:
    """Display current bot status to console."""
    status = survival.get_status_summary()

    print("\n" + "=" * 55)
    print("  📊 POLYMARKET BOT STATUS")
    print("=" * 55)
    print(f"  💰 Balance:       ${status['balance']:.2f}")
    print(f"  📅 Day:           {status['day_number']}")
    print(f"  🎯 Target:        ${status['target_balance']:.2f}")
    print(f"  📈 Today P&L:     ${status['today_pnl']:+.2f}")
    print(f"  🔄 Active Pos:    {status['active_positions']}")
    print(f"  📊 Total Trades:  {status['total_trades']}")
    print(f"  🏆 Win Rate:      {status['win_rate']:.1f}%")
    print(f"  🕐 Updated:       {status['last_updated']}")
    print("=" * 55 + "\n")


def _display_backtest(survival: SurvivalEngine) -> None:
    """Display backtest statistics from log.json."""
    log_file = _PROJECT_ROOT / "data" / "survival" / "log.json"

    if not log_file.exists():
        print("No trading log found. Run the bot first!")
        return

    with open(log_file, "r", encoding="utf-8") as f:
        logs = json.load(f)

    if not logs:
        print("Trading log is empty.")
        return

    status = survival.get_status_summary()

    print("\n" + "=" * 55)
    print("  📊 BACKTEST RESULTS")
    print("=" * 55)
    print(f"  📅 Total Days:     {len(logs)}")
    print(f"  💰 Starting:       $1000.00")
    print(f"  💰 Current:        ${status['balance']:.2f}")
    print(f"  📈 Total Return:   ${status['balance'] - 1000:.2f} "
          f"({(status['balance'] / 1000 - 1) * 100:.1f}%)")
    print(f"  📊 Total Trades:   {status['total_trades']}")
    print(f"  🏆 Win Rate:       {status['win_rate']}%")

    targets_hit = sum(1 for day in logs if day.get("target_achieved", False))
    print(f"  🎯 Targets Hit:    {targets_hit}/{len(logs)}")

    death = any(day.get("death", False) for day in logs)
    print(f"  💀 Death:          {'YES' if death else 'NO'}")
    print("=" * 55 + "\n")


def run_mode_status():
    """Show current status and exit."""
    survival = SurvivalEngine()
    _display_status(survival)


def run_mode_backtest():
    """Analyze log.json and show statistics."""
    survival = SurvivalEngine()
    _display_backtest(survival)


def run_mode_once():
    """Run a single analysis cycle and exit."""
    logger.info("Running single analysis cycle...")

    survival = SurvivalEngine()

    stale = survival.cleanup_stale_positions(max_age_hours=24)
    if stale > 0:
        logger.info(f"Startup cleanup: removed {stale} ghost positions")

    _display_status(survival)

    if survival.check_death():
        print("💀 SYSTEM IS DEAD. Reset state to restart.")
        return

    # Collect data
    print("\n📰 Collecting news from RSS feeds...")
    collect_rss()

    print("📰 Collecting from NewsAPI...")
    collect_newsapi()

    print("📊 Fetching Polymarket markets...")
    markets = collect_markets()

    if not markets:
        print("⚠️  No markets found meeting criteria. Using mock markets for demo.")
        # Create mock markets for paper trading demo
        markets = _create_mock_markets()

    print(f"\n🔍 Analyzing {len(markets)} markets...\n")
    decisions = run_analysis_cycle(markets, survival)

    # Execute BUY signals
    paper_trader = PaperTrader(survival)
    buy_count = 0

    for decision in decisions:
        if decision["action"] == "BUY":
            position = paper_trader.execute_buy(decision)
            if position:
                buy_count += 1

    print(f"\n✅ Cycle complete: {buy_count} trades executed, "
          f"{len(decisions) - buy_count} skipped")
    _display_status(survival)


def run_mode_trading(mode: str):
    """
    Run the main trading loop (paper or live).

    Args:
        mode: "paper" or "live".
    """
    global _running, _iteration

    is_live = mode == "live"

    if is_live:
        if os.getenv("PAPER_TRADING", "true").lower() == "true":
            logger.error(
                "Cannot start live mode: PAPER_TRADING=true in .env. "
                "Set PAPER_TRADING=false to enable live trading."
            )
            return

    logger.info(f"Starting {'LIVE' if is_live else 'PAPER'} trading mode...")

    # Initialize
    survival = SurvivalEngine()
    paper_trader = PaperTrader(survival)

    stale = survival.cleanup_stale_positions(max_age_hours=24)
    if stale > 0:
        logger.info(f"Startup cleanup: removed {stale} ghost positions")

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)

    # Prevent laptop sleep
    prevent_sleep()

    # Send startup alert
    status = survival.get_status_summary()
    alert_bot_started(status["balance"], status["day_number"])

    # Check death
    if survival.check_death():
        alert_death(status["day_number"], status["balance"])
        allow_sleep()
        return

    _display_status(survival)

    # Timing trackers
    last_newsapi_time = 0
    last_market_time = 0
    last_status_alert_time = 0
    newsapi_interval = 3600   # 60 minutes
    market_interval = 1800    # 30 minutes
    status_interval = 21600   # 6 hours
    loop_interval = 900       # 15 minutes

    logger.info(f"Main loop starting (every {loop_interval // 60} minutes)...")

    while _running:
        try:
            _iteration += 1
            now = time.time()
            logger.info(f"\n{'='*40} Iteration {_iteration} {'='*40}")

            # Check: new day?
            # (simplified: check if it's a new UTC day)
            current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            state_date = survival.state.get("last_updated", "")[:10]
            if current_date != state_date and _iteration > 1:
                survival.start_new_day()

            # Check death
            if survival.check_death():
                alert_death(
                    survival.state["day_number"],
                    survival.balance,
                )
                break

            # Collect RSS (every iteration)
            collect_rss()

            # Collect NewsAPI (every 60 min)
            if now - last_newsapi_time >= newsapi_interval:
                collect_newsapi()
                last_newsapi_time = now

            # Update markets (every 30 min)
            if now - last_market_time >= market_interval:
                markets = collect_markets()
                last_market_time = now
            else:
                markets = get_active_markets()

            if not markets:
                logger.info("No markets available, creating mock markets for paper trading")
                markets = _create_mock_markets()

            # Run decision engine
            decisions = run_analysis_cycle(markets, survival)

            # Resolve expiring positions (paper mode) first to free up balance
            if not is_live:
                results = paper_trader.check_and_resolve_expiring(hours_threshold=2.0)
                for result in results:
                    if result["outcome"] == "WIN":
                        alert_position_win(result["pnl"], result["new_balance"])
                    else:
                        alert_position_loss(result["pnl"], result["new_balance"])

            # Execute BUY signals
            for decision in decisions:
                if decision["action"] == "BUY":
                    if is_live:
                        logger.warning("[LIVE] Live execution not yet implemented in loop")
                    else:
                        position = paper_trader.execute_buy(decision)
                        if position:
                            alert_buy_signal(
                                decision["side"],
                                decision["question"],
                                decision["edge_pct"],
                                decision["bet_size"],
                                decision["confidence"],
                                decision.get("reasoning", ""),
                            )

            # Display status
            _display_status(survival)

            # Periodic status alert (every 6 hours)
            if now - last_status_alert_time >= status_interval:
                s = survival.get_status_summary()
                alert_status(
                    s["balance"], s["day_number"],
                    s["target_balance"], s["active_positions"],
                )
                last_status_alert_time = now

            # Wait for next iteration
            logger.info(f"Sleeping {loop_interval // 60} minutes until next cycle...")
            for _ in range(loop_interval):
                if not _running:
                    break
                time.sleep(1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            logger.info("Continuing to next iteration...")
            time.sleep(30)  # Brief cooldown on error

    # Graceful shutdown
    logger.info("Shutting down...")
    survival.save_state()
    allow_sleep()

    status = survival.get_status_summary()
    print(f"\n📋 Session summary: Balance=${status['balance']:.2f}, "
          f"Trades={status['total_trades']}, WinRate={status['win_rate']}%")
    logger.info("Bot shutdown complete.")


def _create_mock_markets():
    """Create mock markets for paper trading when no real markets are available."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    end = (now + timedelta(days=3)).isoformat()

    return [
        {
            "condition_id": "mock_fed_rate_001",
            "question": "Will the Federal Reserve cut interest rates at the next meeting?",
            "category": "economics",
            "end_date": end,
            "volume": 50000.0,
            "best_ask_yes": 0.38,
            "best_bid_yes": 0.36,
            "best_ask_no": 0.62,
            "liquidity": 25000.0,
            "last_updated": now.isoformat(),
        },
        {
            "condition_id": "mock_btc_100k_002",
            "question": "Will Bitcoin reach $100,000 by end of month?",
            "category": "crypto",
            "end_date": end,
            "volume": 120000.0,
            "best_ask_yes": 0.25,
            "best_bid_yes": 0.23,
            "best_ask_no": 0.75,
            "liquidity": 45000.0,
            "last_updated": now.isoformat(),
        },
        {
            "condition_id": "mock_ukraine_003",
            "question": "Will Ukraine and Russia reach a ceasefire agreement this month?",
            "category": "geopolitics",
            "end_date": end,
            "volume": 75000.0,
            "best_ask_yes": 0.42,
            "best_bid_yes": 0.40,
            "best_ask_no": 0.58,
            "liquidity": 30000.0,
            "last_updated": now.isoformat(),
        },
        {
            "condition_id": "mock_sec_crypto_004",
            "question": "Will the SEC approve new crypto regulation before Q3?",
            "category": "regulation",
            "end_date": end,
            "volume": 35000.0,
            "best_ask_yes": 0.55,
            "best_bid_yes": 0.53,
            "best_ask_no": 0.45,
            "liquidity": 15000.0,
            "last_updated": now.isoformat(),
        },
        {
            "condition_id": "mock_ai_regulation_005",
            "question": "Will Congress pass AI regulation legislation this year?",
            "category": "technology",
            "end_date": end,
            "volume": 28000.0,
            "best_ask_yes": 0.30,
            "best_bid_yes": 0.28,
            "best_ask_no": 0.70,
            "liquidity": 12000.0,
            "last_updated": now.isoformat(),
        },
    ]


def main():
    """Parse arguments and run the appropriate mode."""
    parser = argparse.ArgumentParser(
        description="Polymarket Trading Bot — News-based edge trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  paper    Paper trading simulation (default, $0 cost)
  live     Live trading (requires PAPER_TRADING=false)
  once     Single analysis cycle, then exit
  status   Show current status
  backtest Analyze trading log statistics
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["paper", "live", "once", "status", "backtest"],
        default="paper",
        help="Operating mode (default: paper)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("  🤖 POLYMARKET TRADING BOT")
    print(f"  Mode: {args.mode.upper()}")
    print(f"  MOCK_AI: {os.getenv('MOCK_AI', 'true')}")
    print(f"  PAPER_TRADING: {os.getenv('PAPER_TRADING', 'true')}")
    print("=" * 55)

    if args.mode == "status":
        run_mode_status()
    elif args.mode == "backtest":
        run_mode_backtest()
    elif args.mode == "once":
        run_mode_once()
    elif args.mode in ("paper", "live"):
        run_mode_trading(args.mode)


if __name__ == "__main__":
    main()
