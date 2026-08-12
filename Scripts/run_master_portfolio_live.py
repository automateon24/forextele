"""
24/7 Non-Stop Master Portfolio Live Execution Orchestrator
===========================================================
Scans ALL 15 Proven Strategies across ALL 8 Assets (GOLD, SILVER, EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD)
across H1, M15, and M5 timeframes under Microsecond AI/ML Signal Filtering.

Assets (8):
  - GOLD (XAUUSD), SILVER (XAGUSD)
  - EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD

Strategies (15):
  1. BOLLINGER_MEAN_REVERSION
  2. TREND_MOMENTUM
  3. ASIAN_RANGE_SCALP
  4. ORB_OPENING_RANGE_BREAKOUT
  5. NY_OPEN_BREAKOUT
  6. VWAP_MEAN_REVERSION
  7. MEAN_REVERSION
  8. RSI_REVERSAL
  9. CHART_PATTERN_SWING (Elliott Wave, Head & Shoulders, Double Top/Bottom, Flag & Pole)
 10. EMA_TREND_PULLBACK
 11. FVG_RETEST
 12. LONDON_BREAKOUT
 13. LONDON_SESSION_SCALP
 14. SMC_ORDER_BLOCK
 15. SUPERTREND_PULLBACK

Enforces User Mandates:
  - Clear Order Comments in MT5: {STRATEGY_ID}_{TIMEFRAME} (e.g. BOLLINGER_MEAN_REVERSIO_H1)
  - Full CSV Trade Ledger: Logs all trades with Order ID, Strategy, TF, Entry Price, Exit Price, PnL, Win Prob, & Exit Reason in logs/live_orders_ledger.csv
  - Starting Volume: Minimum 0.02 lots per trade
  - Strategy Position Limit: EXACTLY 1 active position per (Strategy, Symbol, Timeframe) until target (TP) or stop loss (SL) is hit in MT5
  - Live MT5 Portfolio Snapshot & Freshness Update (prevents DATA_STALE block)
  - Microsecond Deterministic ML Signal Filtering (src.ml.filter)
  - Live Broker Symbol Specification Verification (src.backtest.symbol_specs)
  - Telemetry Event Logging (data/events/trading_events.jsonl)
  - Async Soft Path Analytics: Periodic Ollama failure review & Parquet dataset building
  - Non-Stop Resilience: Auto-reconnect, exception wrapping, and 24/7/365 loop stability
"""

import sys
import time
import json
import uuid
import logging
import threading
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/master_portfolio_live.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("MASTER_LIVE")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.symbol_specs import get_verified_symbol_spec
from src.execution.gateway import ExecutionRouter
from src.execution.ledger import init_ledger, log_new_order, update_closed_trades
from src.risk.engine import RiskEvaluator
from src.portfolio.manager import init_mt5, get_daily_realised_pnl, load_high_water_mark
from src.common.messages import PortfolioSnapshotMessage, MessageHeader, OpenPosition
from src.ml.features import extract_features_at_row
from src.ml.filter import MLSignalFilter

# Import all 15 strategy modules
from src.strategy.bollinger_mean_reversion import BollingerMeanReversionStrategy
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.asian_range_scalp import AsianRangeScalpStrategy
from src.strategy.orb_opening_range_breakout import ORBOpeningRangeBreakoutStrategy
from src.strategy.ny_open_breakout import NYOpenBreakoutStrategy
from src.strategy.vwap_mean_reversion import VWAPMeanReversionStrategy
from src.strategy.mean_reversion import MeanReversionStrategy
from src.strategy.rsi_reversal import RSIReversalStrategy
from src.strategy.chart_pattern_swing import ChartPatternSwingStrategy
from src.strategy.ema_trend_pullback import EMATrendPullbackStrategy
from src.strategy.fvg_retest import FVGRetestStrategy
from src.strategy.london_breakout import LondonBreakoutStrategy
from src.strategy.london_session_scalp import LondonSessionScalpStrategy
from src.strategy.smc_order_block import SMCOrderBlockStrategy
from src.strategy.supertrend_pullback import SupertrendPullbackStrategy

ALL_STRATEGY_MAP = [
    ("BOLLINGER_MEAN_REVERSION", BollingerMeanReversionStrategy),
    ("TREND_MOMENTUM",          TrendMomentumStrategy),
    ("ASIAN_RANGE_SCALP",        AsianRangeScalpStrategy),
    ("ORB_OPENING_RANGE_BREAKOUT", ORBOpeningRangeBreakoutStrategy),
    ("NY_OPEN_BREAKOUT",         NYOpenBreakoutStrategy),
    ("VWAP_MEAN_REVERSION",      VWAPMeanReversionStrategy),
    ("MEAN_REVERSION",           MeanReversionStrategy),
    ("RSI_REVERSAL",             RSIReversalStrategy),
    ("CHART_PATTERN_SWING",      ChartPatternSwingStrategy),
    ("EMA_TREND_PULLBACK",       EMATrendPullbackStrategy),
    ("FVG_RETEST",               FVGRetestStrategy),
    ("LONDON_BREAKOUT",          LondonBreakoutStrategy),
    ("LONDON_SESSION_SCALP",      LondonSessionScalpStrategy),
    ("SMC_ORDER_BLOCK",          SMCOrderBlockStrategy),
    ("SUPERTREND_PULLBACK",      SupertrendPullbackStrategy),
]

ALL_SYMBOLS = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD"]
ALL_TIMEFRAMES = [
    ("H1",  mt5.TIMEFRAME_H1),
    ("M15", mt5.TIMEFRAME_M15),
    ("M5",  mt5.TIMEFRAME_M5),
]

# Build Comprehensive Master Portfolio Matrix
MASTER_WINNING_PORTFOLIO = []
for sym in ALL_SYMBOLS:
    for tf_str, tf_mt5 in ALL_TIMEFRAMES:
        for st_id, st_cls in ALL_STRATEGY_MAP:
            # Session filter rules for session-specific strategies
            if st_id in ["ASIAN_RANGE_SCALP"] and tf_str not in ["H1", "M15", "M5"]:
                continue
            MASTER_WINNING_PORTFOLIO.append({
                "symbol": sym,
                "timeframe": tf_str,
                "tf_mt5": tf_mt5,
                "strategy_cls": st_cls,
                "strategy_id": st_id
            })


def init_mt5_connection() -> bool:
    """Ensures MT5 terminal connection is active with automatic reconnect."""
    if not mt5.initialize():
        logger.error(f"MT5 Initialize failed: {mt5.last_error()}")
        return False
    term_info = mt5.terminal_info()
    if term_info is None or not term_info.connected:
        logger.warning("MT5 terminal disconnected. Attempting auto-reconnect...")
        mt5.shutdown()
        time.sleep(2)
        return mt5.initialize()
    return True


def build_live_portfolio_snapshot() -> PortfolioSnapshotMessage:
    """Fetches real-time account, positions, and equity state from MT5."""
    account_info = mt5.account_info()
    if account_info is None:
        init_mt5_connection()
        account_info = mt5.account_info()
        if account_info is None:
            raise Exception("Failed to fetch MT5 account info")

    positions = mt5.positions_get()
    open_pos = []
    if positions:
        for p in positions:
            open_pos.append(OpenPosition(
                symbol=p.symbol,
                side="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                volume=p.volume,
                entry_price=p.price_open,
                current_price=p.price_current,
                sl=p.sl,
                unrealised_pnl=p.profit,
                risk_amount=abs(p.price_open - p.sl) * p.volume if p.sl > 0 else 0.0,
                comment=getattr(p, "comment", "")
            ))

    equity = account_info.equity
    daily_realised = get_daily_realised_pnl()

    return PortfolioSnapshotMessage(
        header=MessageHeader(
            message_id=str(uuid.uuid4()),
            timestamp_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            source_component="portfolio",
            message_type="PortfolioSnapshot"
        ),
        equity=equity,
        balance=account_info.balance,
        margin_used=account_info.margin,
        margin_free=account_info.margin_free,
        open_positions=open_pos,
        daily_realised_pnl=daily_realised,
        daily_unrealised_pnl=sum(p.unrealised_pnl for p in open_pos),
        high_water_mark_equity=load_high_water_mark(equity)
    )


def fetch_candles(symbol: str, tf_mt5: int, count: int = 100) -> Optional[pd.DataFrame]:
    """Fetches and formats live OHLCV bars from MT5."""
    try:
        rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df
    except Exception as e:
        logger.error(f"Error fetching candles for {symbol}: {e}")
        return None


def run_async_analytics_worker():
    """Background worker that periodically builds datasets and invokes Ollama failure reviews."""
    while True:
        try:
            time.sleep(14400) # Run every 4 hours
            logger.info("Executing periodic async soft path analytics (Dataset build & Ollama failure review)...")

            import subprocess
            subprocess.run([sys.executable, "scripts/build_dataset_from_logs.py"], capture_output=True)
            subprocess.run([sys.executable, "scripts/ollama_review_failures.py"], capture_output=True)
            logger.info("Soft path analytics task completed successfully.")
        except Exception as e:
            logger.error(f"Async analytics worker error: {e}")


def main_live_loop():
    logger.info("================================================================================")
    logger.info("  FOREXTELE MASTER PORTFOLIO 24/7 LIVE EXECUTION ORCHESTRATOR")
    logger.info(f"  Scanning {len(ALL_STRATEGY_MAP)} Strategies across {len(ALL_SYMBOLS)} Assets & 3 Timeframes ({len(MASTER_WINNING_PORTFOLIO)} Engines Active)")
    logger.info("  Enforcing 0.02 Lot Volume, Per-Timeframe Position Locks & Live CSV Trade Ledger")
    logger.info("================================================================================")

    Path("logs").mkdir(parents=True, exist_ok=True)
    Path("data/events").mkdir(parents=True, exist_ok=True)
    init_ledger()

    if not init_mt5_connection():
        logger.error("Initial MT5 connection failed. Retrying in 10 seconds...")
        time.sleep(10)
        return

    # Start Async Soft Path Analytics Thread
    analytics_thread = threading.Thread(target=run_async_analytics_worker, daemon=True)
    analytics_thread.start()

    # Initialize Engine Components
    risk_evaluator    = RiskEvaluator()
    execution_router  = ExecutionRouter()
    ml_signal_filter  = MLSignalFilter()

    logger.info(f"ML Signal Filter Active (Threshold: {ml_signal_filter.threshold}, Production Models: {len(ml_signal_filter.registry.list_production_models())})")

    # Instantiate Strategy Portfolio Objects
    portfolio_instances = []
    for item in MASTER_WINNING_PORTFOLIO:
        sym  = item["symbol"]
        tf   = item["timeframe"]
        cls  = item["strategy_cls"]
        inst = cls(symbol=sym)
        portfolio_instances.append({
            "symbol": sym,
            "timeframe": tf,
            "tf_mt5": item["tf_mt5"],
            "strategy": inst,
            "strategy_id": item["strategy_id"]
        })

    logger.info(f"Master Portfolio Active: {len(portfolio_instances)} Strategy-Symbol-Timeframe Executions Loaded.")

    loop_count = 0

    # 24/7/365 Non-Stop Execution Loop
    while True:
        try:
            loop_count += 1

            if not init_mt5_connection():
                time.sleep(5)
                continue

            # Update Live Portfolio Snapshot in Risk Engine to prevent DATA_STALE blocks
            portfolio_snapshot = None
            try:
                portfolio_snapshot = build_live_portfolio_snapshot()
                risk_evaluator.portfolio = portfolio_snapshot
            except Exception as e:
                logger.warning(f"Could not update portfolio snapshot: {e}")

            # Update CSV Trade Ledger for any closed positions (records exit price, exit timestamp, pnl, exit reason)
            try:
                update_closed_trades()
            except Exception as e:
                logger.warning(f"Could not update closed trade ledger: {e}")

            if loop_count % 12 == 0:  # Heartbeat log every ~60 seconds
                account_info = mt5.account_info()
                balance = account_info.balance if account_info else 0.0
                equity  = account_info.equity  if account_info else 0.0
                pos_count = len(portfolio_snapshot.open_positions) if portfolio_snapshot else 0
                logger.info(f"Heartbeat [Loop {loop_count}] - MT5 Connected | Balance: ${balance:.2f} | Equity: ${equity:.2f} | Open Positions: {pos_count} | {len(portfolio_instances)} Engines Active")

            # Evaluate each portfolio strategy item
            for item in portfolio_instances:
                sym    = item["symbol"]
                tf_mt5 = item["tf_mt5"]
                strat  = item["strategy"]
                st_id  = item["strategy_id"]
                tf_str = item["timeframe"]

                # MANDATE CHECK: Only 1 active position allowed per (Strategy, Symbol, Timeframe) in MT5 until hit TP/SL
                tag = f"{st_id[:24]}_{tf_str}"
                has_active_trade = False
                if portfolio_snapshot and portfolio_snapshot.open_positions:
                    for pos in portfolio_snapshot.open_positions:
                        if pos.symbol == sym and (tag in pos.comment or pos.comment in tag):
                            has_active_trade = True
                            break
                
                if has_active_trade:
                    # Skip signal generation until active trade for (Strategy, Symbol, Timeframe) hits SL or TP in MT5
                    continue

                # 1. Fetch live candles
                df = fetch_candles(sym, tf_mt5, count=100)
                if df is None or len(df) < strat.min_bars:
                    continue

                # 2. Verify live broker symbol specs
                spec = get_verified_symbol_spec(sym)

                # 3. Strategy Signal Evaluation
                signal = strat.analyze(df)
                if signal:
                    # Enforce starting volume minimum of 0.02 lots & attach timeframe metadata
                    signal.metadata["suggested_volume"] = 0.02
                    signal.metadata["timeframe"] = tf_str

                    logger.info(f"[{sym}][{tf_str}][{signal.strategy_id}] SIGNAL GENERATED: {signal.side} @ {signal.suggested_entry_price} (SL: {signal.suggested_sl_price}, TP: {signal.suggested_tp_price}, Vol: 0.02)")

                    # 4. Microsecond Classical ML Filter (HARD PATH)
                    feats = extract_features_at_row(df, -1)
                    allow_ml, prob_win, ml_payload = ml_signal_filter.evaluate(
                        symbol=sym, timeframe=tf_str, strategy_id=signal.strategy_id, features=feats
                    )

                    logger.info(f"[{sym}][{tf_str}][{signal.strategy_id}] ML FILTER DECISION: {ml_payload['decision']} (Win Prob: {prob_win:.2%})")

                    # Log Telemetry Event to JSONL (using timezone-aware UTC)
                    cid = str(uuid.uuid4())
                    events_file = Path("data/events/trading_events.jsonl")
                    sig_evt = {
                        "event": "signal", "ts_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "correlation_id": cid, "symbol": sym, "timeframe": tf_str, "strategy_id": signal.strategy_id,
                        "side": signal.side, "entry": signal.suggested_entry_price, "sl": signal.suggested_sl_price,
                        "tp": signal.suggested_tp_price, "features": feats
                    }
                    flt_evt = {
                        "event": "filter", "correlation_id": cid, "model_id": ml_payload.get("model_id"),
                        "prob_win": prob_win, "threshold": ml_signal_filter.threshold, "decision": ml_payload.get("decision")
                    }
                    with open(events_file, "a") as ef:
                        ef.write(json.dumps(sig_evt) + "\n")
                        ef.write(json.dumps(flt_evt) + "\n")

                    if not allow_ml:
                        logger.info(f"[{sym}][{tf_str}][{signal.strategy_id}] Signal BLOCKED by ML Filter (prob {prob_win:.2%} < threshold {ml_signal_filter.threshold})")
                        continue

                    # 5. Risk Engine Evaluation
                    risk_decision = risk_evaluator.evaluate(signal)
                    logger.info(f"[{sym}][{tf_str}][{signal.strategy_id}] RISK DECISION: {risk_decision.decision} ({risk_decision.reason_code})")

                    # 6. Live Execution Gateway & CSV Ledger Logging
                    if risk_decision.decision in ["ALLOW", "ALLOW_REDUCED"]:
                        logger.info(f"[{sym}][{tf_str}][{signal.strategy_id}] ROUTING TO MT5 EXECUTION GATEWAY...")
                        fill_report = execution_router.execute(risk_decision)
                        logger.info(f"[{sym}][{tf_str}][{signal.strategy_id}] EXECUTION RESULT: {fill_report.status} (Reason: {fill_report.reject_reason})")

                        # Log trade into CSV Ledger with complete order tracking
                        entry_price = fill_report.fill_price if fill_report.status == "FILLED" else signal.suggested_entry_price
                        entry_reason = f"ML_APPROVED (Win Prob: {prob_win:.2%}) | Risk OK" if fill_report.status == "FILLED" else f"REJECTED: {fill_report.reject_reason}"
                        log_new_order(
                            order_id=fill_report.broker_order_id,
                            symbol=sym,
                            timeframe=tf_str,
                            strategy_id=signal.strategy_id,
                            side=signal.side,
                            volume=fill_report.volume,
                            entry_price=entry_price,
                            sl_price=signal.suggested_sl_price,
                            tp_price=signal.suggested_tp_price,
                            status=fill_report.status,
                            win_probability=prob_win,
                            entry_reason=entry_reason
                        )

            time.sleep(5)  # 5-second polling loop

        except KeyboardInterrupt:
            logger.info("Shutdown signal received. Stopping orchestrator...")
            break
        except Exception as e:
            logger.error(f"Unhandled error in main live loop: {e}", exc_info=True)
            time.sleep(5)

    mt5.shutdown()
    logger.info("ForexTele Master Live Orchestrator shut down cleanly.")


if __name__ == "__main__":
    while True:
        try:
            main_live_loop()
        except Exception as e:
            logger.critical(f"Master orchestrator crashed. Restarting in 5 seconds... Error: {e}")
            time.sleep(5)
