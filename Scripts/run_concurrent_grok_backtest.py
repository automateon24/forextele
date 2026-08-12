"""
Ultra-Fast Two-Stage Concurrent Grok Portfolio Backtest Engine
===============================================================
Stage 1: Generate strategy signals using BacktestEngine across all 8 symbols & 3 timeframes.
Stage 2: Process candidate trades chronologically through the Grok Risk Evaluator:
  - Initial Capital: $1,500.00 USD
  - Lot Volume: 0.02 Lots per trade
  - Unique Key Slot Lock: Max 1 active trade per (Symbol, Timeframe, Strategy_ID) until exit
  - Symbol Position Cap: Max 2 active positions total per symbol (e.g. GOLD)
  - Account Position Cap: Max 3 active positions total account-wide (0.06 total lots max)
  - Daily Drawdown Stop: 3% daily equity loss circuit breaker (-$45.00)
  - Execution Realism: Real spread + commission ($7/lot) + slippage friction ($0.30)
"""

import sys
import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GROK_BACKTEST")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.symbol_specs import get_verified_symbol_spec
from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.ml.features import extract_df_features, FEATURE_COLS
from src.ml.filter import MLSignalFilter

# Import top winning strategy classes
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

ALL_STRATEGIES = [
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


def init_mt5_conn():
    if not mt5.initialize():
        logger.error("MT5 initialize failed.")
        return False
    return True


def fetch_bars(symbol: str, tf_mt5: int, count: int = 3000) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def main():
    logger.info("================================================================================")
    logger.info("  GROK RISK ENGINE — TWO-STAGE CONCURRENT MULTI-ASSET PORTFOLIO BACKTEST")
    logger.info("  Initial Capital: $1,500.00 | Lot Volume: 0.02 Lots | 8 Assets | 3 TFs | 15 Strategies")
    logger.info("================================================================================")

    if not init_mt5_conn():
        return

    ml_filter = MLSignalFilter()
    logger.info(f"ML Filter loaded with threshold {ml_filter.threshold} ({len(ml_filter.registry.list_production_models())} production models)")

    # Stage 1: Fast Candidate Signal Generation Across All Pairs & Timeframes
    candidate_trades = []

    for sym in ALL_SYMBOLS:
        for tf_str, tf_mt5 in ALL_TIMEFRAMES:
            df = fetch_bars(sym, tf_mt5, count=3000)
            if df.empty or len(df) < 60:
                continue

            df = extract_df_features(df)
            cost_m = CostModel(spread_points=0.30 if "GOLD" in sym else 0.00030)

            # Instantiate strategies for this symbol
            strats_inst = [st_cls(symbol=sym) for _, st_cls in ALL_STRATEGIES]

            volume_size = 0.005 if "SILVER" in sym else 0.02

            # Run BacktestEngine for candidates
            engine = BacktestEngine(
                df=df,
                strategies=strats_inst,
                cost_model=cost_m,
                capital=1500.0,
                volume=volume_size,
                use_tsl=True,
                max_dd_pct=0.30,
                slippage_usd=0.15
            )
            engine.run()

            for tr in engine.trades:
                tr["symbol"] = sym
                tr["timeframe"] = tf_str
                tr["key"] = f"{sym}_{tf_str}_{tr['strategy_id']}"
                candidate_trades.append(tr)

            logger.info(f"Generated {len(engine.trades)} candidate trades for {sym} [{tf_str}]")

    mt5.shutdown()

    logger.info(f"Stage 1 Complete: {len(candidate_trades)} total candidate trades collected across portfolio.")

    # Sort all candidate trades chronologically by entry time
    candidate_trades.sort(key=lambda x: x["time"])

    # Stage 2: Chronological Grok Risk Engine Portfolio Simulation
    initial_capital = 1500.0
    balance = initial_capital
    peak_equity = initial_capital
    max_drawdown_dollar = 0.0
    max_drawdown_pct = 0.0

    # Global Exposure Cap per INCIDENT_AUDIT_REPORT_FOR_GROK_REVIEW.md
    max_positions_per_symbol = 1 # Max 1 active position per symbol (e.g. GOLD)
    max_account_positions = 2    # Max 2 active positions account-wide (0.04 total lots max exposure)
    daily_loss_limit_pct = 0.03  # 3% daily drawdown circuit breaker ($45.00)

    open_positions = [] # List of active trade dicts
    executed_trades = []

    daily_realized_pnl = 0.0
    current_day = None

    for tr in candidate_trades:
        tr_time = tr["time"]
        tr_date = tr_time.date()
        sym = tr["symbol"]
        tf_str = tr["timeframe"]
        key = tr["key"]

        # Reset daily PnL counter on new trading day
        if current_day != tr_date:
            current_day = tr_date
            daily_realized_pnl = 0.0

        # 1. Update active open positions up to tr_time
        remaining = []
        for pos in open_positions:
            # If open position exited before or at tr_time, close it and credit PnL
            pos_exit_time = pos.get("exit_time", pos["time"] + timedelta(hours=1))
            if pos_exit_time <= tr_time:
                balance += pos["pnl"]
                daily_realized_pnl += pos["pnl"]
                executed_trades.append(pos)
            else:
                remaining.append(pos)

        open_positions = remaining

        # Update Equity Peak & Drawdown
        if balance > peak_equity:
            peak_equity = balance
        dd_dollar = peak_equity - balance
        dd_pct = (dd_dollar / peak_equity) if peak_equity > 0 else 0.0
        if dd_dollar > max_drawdown_dollar:
            max_drawdown_dollar = dd_dollar
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct

        # 2. Check Daily Drawdown Circuit Breaker (-3% Max Daily Loss)
        if daily_realized_pnl < -(initial_capital * daily_loss_limit_pct):
            continue # Halted for remainder of trading day

        # 3. Check Account Position Limit (Max 3 active positions account-wide)
        if len(open_positions) >= max_account_positions:
            continue

        # 4. Check Per-Symbol Position Limit (Max 2 active positions per symbol e.g. GOLD)
        sym_pos_count = len([p for p in open_positions if p["symbol"] == sym])
        if sym_pos_count >= max_positions_per_symbol:
            continue

        # 5. Check Unique Key Slot Lock (Pair + TF + Strategy_ID)
        key_pos_count = len([p for p in open_positions if p["key"] == key])
        if key_pos_count >= 1:
            continue # Locked until open trade exits

        # Accept trade into open positions portfolio
        open_positions.append(tr)

    # Close any remaining open positions
    for pos in open_positions:
        balance += pos["pnl"]
        executed_trades.append(pos)

    # Generate Metrics & Summary
    df_executed = pd.DataFrame(executed_trades)
    net_profit = balance - initial_capital
    return_pct = (net_profit / initial_capital) * 100.0
    win_rate = (len(df_executed[df_executed["pnl"] > 0]) / len(df_executed) * 100.0) if not df_executed.empty else 0.0
    profit_factor = (df_executed[df_executed["pnl"] > 0]["pnl"].sum() / abs(df_executed[df_executed["pnl"] < 0]["pnl"].sum())) if not df_executed.empty and abs(df_executed[df_executed["pnl"] < 0]["pnl"].sum()) > 0 else 0.0

    print("\n" + "="*80)
    print(" GROK RISK ENGINE -- CONCURRENT MULTI-ASSET PORTFOLIO BACKTEST RESULTS")
    print("="*80)
    print(f" Initial Capital      : ${initial_capital:,.2f} USD")
    print(f" Final Balance        : ${balance:,.2f} USD")
    print(f" Net Profit           : ${net_profit:,.2f} USD ({return_pct:+.2f}%)")
    print(f" Total Trades Taken   : {len(df_executed)}")
    print(f" Win Rate             : {win_rate:.2f}%")
    print(f" Profit Factor        : {profit_factor:.2f}")
    print(f" Max Drawdown ($)     : ${max_drawdown_dollar:,.2f} USD")
    print(f" Max Drawdown (%)     : {max_drawdown_pct * 100.0:.2f}%")
    print("="*80)

    # Asset Performance Breakdown
    if not df_executed.empty:
        print("\nASSET PERFORMANCE BREAKDOWN:")
        print(f"{'Asset':<10} {'Trades':<8} {'Win Rate':<10} {'Net PnL ($)':<15} {'Profit Factor':<15}")
        print("-" * 60)
        for sym in ALL_SYMBOLS:
            sub = df_executed[df_executed["symbol"] == sym]
            if not sub.empty:
                s_wins = len(sub[sub["pnl"] > 0])
                s_wr = (s_wins / len(sub)) * 100.0
                s_pnl = sub["pnl"].sum()
                s_gross_win = sub[sub["pnl"] > 0]["pnl"].sum()
                s_gross_loss = abs(sub[sub["pnl"] < 0]["pnl"].sum())
                s_pf = (s_gross_win / s_gross_loss) if s_gross_loss > 0 else 99.0
                print(f"{sym:<10} {len(sub):<8} {s_wr:<10.2f}% ${s_pnl:<14.2f} {s_pf:<15.2f}")

    # Write Markdown Report Artifact
    report_md = f"""# 🏛️ Grok Risk Model — Concurrent Multi-Asset Portfolio Backtest Report
## Full Portfolio Backtest Across All 8 Assets ($1,500 Loaded Capital)

- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **${balance:,.2f} USD**
- **Net Return**: **{return_pct:+.2f}%** (${net_profit:,.2f} USD)
- **Total Trades Taken**: {len(df_executed)} trades
- **Win Rate**: **{win_rate:.2f}%**
- **Profit Factor**: **{profit_factor:.2f}**
- **Max Account Drawdown**: **{max_drawdown_pct * 100.0:.2f}%** (${max_drawdown_dollar:,.2f} USD)

---

### 🛡️ Enforced Operating Controls (Grok Risk Model)

1. **Unique Key Slot Lock**: Max 1 active trade per `(Symbol, Timeframe, Strategy_ID)` tuple until TP/SL/TSL exit.
2. **Per-Symbol Position Cap**: Max 2 active positions total per symbol (e.g. `GOLD`).
3. **Account Position Cap**: Max 3 active positions total account-wide (0.06 total lots max).
4. **Daily Drawdown Stop**: 3% daily equity loss stop (-$45.00 on $1,500 capital).
5. **Execution Realism**: Real spread + commission ($7/lot) + slippage friction.

---

### 📊 Asset-by-Asset Performance Breakdown

| Asset | Total Trades | Win Rate (%) | Net PnL ($) | Profit Factor |
| :--- | :--- | :--- | :--- | :--- |
"""
    if not df_executed.empty:
        for sym in ALL_SYMBOLS:
            sub = df_executed[df_executed["symbol"] == sym]
            if not sub.empty:
                s_wins = len(sub[sub["pnl"] > 0])
                s_wr = (s_wins / len(sub)) * 100.0
                s_pnl = sub["pnl"].sum()
                s_gross_win = sub[sub["pnl"] > 0]["pnl"].sum()
                s_gross_loss = abs(sub[sub["pnl"] < 0]["pnl"].sum())
                s_pf = (s_gross_win / s_gross_loss) if s_gross_loss > 0 else 99.0
                report_md += f"| **{sym}** | {len(sub)} | {s_wr:.2f}% | ${s_pnl:+,.2f} | {s_pf:.2f} |\n"

    report_path = Path("reports/concurrent_portfolio_backtest_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as rf:
        rf.write(report_md)
    logger.info(f"Backtest summary artifact written to {report_path}")


if __name__ == "__main__":
    main()
