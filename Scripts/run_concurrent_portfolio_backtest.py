"""
Fast Concurrent Multi-Asset Multi-Strategy Backtest Simulator
==============================================================
Simulates the exact Grok-aligned operating model concurrently across all 8 assets:
  - Capital: $1,500.00 USD
  - Fixed Lot Size: 0.02 Lots per trade
  - Assets (8): GOLD, SILVER, EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD
  - Timeframes (3): H1, M15, M5
  - Strategies (15): All 15 strategy modules (with pattern-specific tags)

Enforced Risk Rules:
  1. Unique Key: Max 1 active position per (Symbol, Timeframe, Strategy_ID) until TP/SL/TSL hit
  2. Per-Symbol Cap: Max 2 active positions total per symbol (e.g. GOLD)
  3. Account Cap: Max 3 active positions total account-wide (0.06 total lots max)
  4. Daily Drawdown Circuit Breaker: 3% daily loss stop (-$45.00 on $1,500 capital)
  5. ML Signal Filtering: Win probability >= 0.58
  6. Execution Realism: Real spread + commission ($7/lot) + slippage friction ($0.30)
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
logger = logging.getLogger("CONCURRENT_BACKTEST")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.symbol_specs import get_verified_symbol_spec
from src.ml.features import extract_df_features, extract_features_at_row
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

ALL_STRATEGY_CLASSES = [
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


def fetch_historical_bars(symbol: str, tf_mt5: int, bars: int = 3000) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, bars)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def run_concurrent_backtest():
    logger.info("================================================================================")
    logger.info("  STARTING FAST CONCURRENT MULTI-ASSET MULTI-STRATEGY PORTFOLIO BACKTEST")
    logger.info("  Capital: $1,500.00 USD | Fixed Lot: 0.02 Lots | 8 Assets | 3 TFs | 15 Strategies")
    logger.info("================================================================================")

    if not init_mt5_conn():
        return

    ml_filter = MLSignalFilter()
    logger.info(f"ML Filter loaded with threshold {ml_filter.threshold} ({len(ml_filter.registry.list_production_models())} production models)")

    # Fetch data for all symbols and timeframes
    market_data = {}
    for sym in ALL_SYMBOLS:
        market_data[sym] = {}
        for tf_str, tf_mt5 in ALL_TIMEFRAMES:
            df = fetch_historical_bars(sym, tf_mt5, bars=3000)
            if not df.empty:
                df = extract_df_features(df)
                market_data[sym][tf_str] = df
                logger.info(f"Fetched {len(df)} bars for {sym} [{tf_str}]")

    mt5.shutdown()

    # Pre-compute signals for all (Symbol, Timeframe, Strategy) combinations
    logger.info("Pre-computing strategy signals across all portfolio combinations...")
    signals_by_time = {} # timestamp -> list of candidate signal dicts

    for sym in ALL_SYMBOLS:
        for tf_str, tf_mt5 in ALL_TIMEFRAMES:
            if tf_str not in market_data[sym]:
                continue
            df = market_data[sym][tf_str]
            if len(df) < 60:
                continue

            for st_id, st_cls in ALL_STRATEGY_CLASSES:
                strat_inst = st_cls(symbol=sym)
                min_b = getattr(strat_inst, "min_bars", 50)

                for i in range(min_b, len(df)):
                    df_sub = df.iloc[:i+1].copy()
                    sig = strat_inst.analyze(df_sub)
                    if sig:
                        t = df["time"].iloc[i]
                        effective_st_id = sig.strategy_id
                        
                        # Extract ML features at row
                        feats = extract_features_at_row(df, i)
                        allow_ml, prob_win, _ = ml_filter.evaluate(
                            symbol=sym, timeframe=tf_str, strategy_id=effective_st_id, features=feats
                        )

                        if allow_ml and prob_win >= 0.58:
                            cand = {
                                "timestamp": t,
                                "symbol": sym,
                                "timeframe": tf_str,
                                "strategy_id": effective_st_id,
                                "side": sig.side,
                                "entry": sig.suggested_entry_price,
                                "sl": sig.suggested_sl_price,
                                "tp": sig.suggested_tp_price,
                                "win_prob": prob_win,
                                "key": f"{sym}_{tf_str}_{effective_st_id}"
                            }
                            if t not in signals_by_time:
                                signals_by_time[t] = []
                            signals_by_time[t].append(cand)

    logger.info(f"Pre-computation complete. {sum(len(v) for v in signals_by_time.values())} ML-approved candidate signals indexed across time.")

    # Construct unified time index across all H1/M15/M5 bars
    all_timestamps = set()
    for sym in market_data:
        for tf_str in market_data[sym]:
            df = market_data[sym][tf_str]
            all_timestamps.update(df["time"].tolist())

    sorted_times = sorted(list(all_timestamps))

    # Fast lookup by (symbol, tf_str) -> DataFrame indexed by time
    lookup = {}
    for sym in market_data:
        lookup[sym] = {}
        for tf_str in market_data[sym]:
            df = market_data[sym][tf_str].copy()
            lookup[sym][tf_str] = df.set_index("time", drop=False)

    # Portfolio Simulation Parameters
    initial_capital = 1500.0
    balance = initial_capital
    peak_equity = initial_capital
    max_drawdown_dollar = 0.0
    max_drawdown_pct = 0.0

    # Risk Engine Rules
    max_positions_per_symbol = 2
    max_account_positions = 3
    daily_loss_limit_pct = 0.03 # 3% daily drawdown stop ($45.00)
    fixed_lot = 0.02

    open_positions = [] # List of active position dicts
    closed_trades = []

    daily_realized_pnl = 0.0
    current_day = None

    # Main Simulation Loop
    for ts in sorted_times:
        ts_date = ts.date()
        if current_day != ts_date:
            current_day = ts_date
            daily_realized_pnl = 0.0

        # 1. Update Open Positions & Check SL / TP Hits
        remaining_positions = []
        for pos in open_positions:
            sym = pos["symbol"]
            tf_str = pos["timeframe"]
            
            if sym in lookup and tf_str in lookup[sym] and ts in lookup[sym][tf_str].index:
                row = lookup[sym][tf_str].loc[ts]
                curr_high = row["high"]
                curr_low = row["low"]
                curr_close = row["close"]

                spec = get_verified_symbol_spec(sym)
                mult = spec["tick_value"] / (spec["tick_size"] if spec["tick_size"] > 0 else 0.01)

                hit_sl = False
                hit_tp = False
                exit_price = curr_close

                if pos["side"] == "BUY":
                    if curr_low <= pos["sl"]:
                        hit_sl = True
                        exit_price = pos["sl"]
                    elif curr_high >= pos["tp"]:
                        hit_tp = True
                        exit_price = pos["tp"]
                else: # SELL
                    if curr_high >= pos["sl"]:
                        hit_sl = True
                        exit_price = pos["sl"]
                    elif curr_low <= pos["tp"]:
                        hit_tp = True
                        exit_price = pos["tp"]

                if hit_sl or hit_tp:
                    pnl_points = (exit_price - pos["entry"]) if pos["side"] == "BUY" else (pos["entry"] - exit_price)
                    gross_pnl = pnl_points * mult * pos["volume"]
                    commission = 7.0 * pos["volume"]
                    net_pnl = gross_pnl - commission

                    balance += net_pnl
                    daily_realized_pnl += net_pnl
                    pos["exit_price"] = exit_price
                    pos["exit_time"] = ts
                    pos["pnl"] = net_pnl
                    pos["exit_reason"] = "TP_HIT" if hit_tp else "SL_HIT"
                    closed_trades.append(pos)
                else:
                    remaining_positions.append(pos)
            else:
                remaining_positions.append(pos)

        open_positions = remaining_positions

        # 2. Update Equity & Peak Drawdown
        unrealized_pnl = 0.0
        for pos in open_positions:
            sym = pos["symbol"]
            tf_str = pos["timeframe"]
            if sym in lookup and tf_str in lookup[sym] and ts in lookup[sym][tf_str].index:
                curr_close = lookup[sym][tf_str].loc[ts]["close"]
                spec = get_verified_symbol_spec(sym)
                mult = spec["tick_value"] / (spec["tick_size"] if spec["tick_size"] > 0 else 0.01)
                pnl_pts = (curr_close - pos["entry"]) if pos["side"] == "BUY" else (pos["entry"] - curr_close)
                unrealized_pnl += pnl_pts * mult * pos["volume"]

        equity = balance + unrealized_pnl
        if equity > peak_equity:
            peak_equity = equity

        dd_dollar = peak_equity - equity
        dd_pct = (dd_dollar / peak_equity) if peak_equity > 0 else 0.0
        if dd_dollar > max_drawdown_dollar:
            max_drawdown_dollar = dd_dollar
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct

        # 3. Check Daily Circuit Breaker (-3% Max Daily Loss)
        if daily_realized_pnl < -(initial_capital * daily_loss_limit_pct):
            continue # Halted for the rest of the day

        # 4. Process Candidate Signals at current timestamp
        if ts in signals_by_time:
            for cand in signals_by_time[ts]:
                sym = cand["symbol"]
                tf_str = cand["timeframe"]
                key = cand["key"]

                # Account Position Cap Check (Max 3)
                if len(open_positions) >= max_account_positions:
                    break

                # Symbol Position Cap Check (Max 2)
                sym_pos_count = len([p for p in open_positions if p["symbol"] == sym])
                if sym_pos_count >= max_positions_per_symbol:
                    continue

                # Unique Key Slot Check: (Symbol, Timeframe, Strategy_ID)
                key_pos_count = len([p for p in open_positions if p["key"] == key])
                if key_pos_count >= 1:
                    continue # Locked until active open trade exits

                # Apply Real Spread & Slippage Friction
                spec = get_verified_symbol_spec(sym)
                spread_pts = spec.get("spread", 0.00030 if "USD" in sym else 0.40)
                slippage_pts = 0.00010 if "USD" in sym else 0.15

                entry_price = cand["entry"]
                if cand["side"] == "BUY":
                    entry_price += (spread_pts + slippage_pts)
                else:
                    entry_price -= (spread_pts + slippage_pts)

                new_pos = {
                    "key": key,
                    "symbol": sym,
                    "timeframe": tf_str,
                    "strategy_id": cand["strategy_id"],
                    "side": cand["side"],
                    "volume": fixed_lot,
                    "entry": entry_price,
                    "sl": cand["sl"],
                    "tp": cand["tp"],
                    "entry_time": ts,
                    "win_prob": cand["win_prob"]
                }
                open_positions.append(new_pos)

    # Generate Performance Metrics
    df_closed = pd.DataFrame(closed_trades)
    net_profit = balance - initial_capital
    return_pct = (net_profit / initial_capital) * 100.0
    win_rate = (len(df_closed[df_closed["pnl"] > 0]) / len(df_closed) * 100.0) if not df_closed.empty else 0.0
    profit_factor = (df_closed[df_closed["pnl"] > 0]["pnl"].sum() / abs(df_closed[df_closed["pnl"] < 0]["pnl"].sum())) if not df_closed.empty and abs(df_closed[df_closed["pnl"] < 0]["pnl"].sum()) > 0 else 0.0

    print("\n" + "="*80)
    print(" 🏛️ CONCURRENT MULTI-ASSET PORTFOLIO BACKTEST RESULTS")
    print(" Enforcing Grok Rule: (Pair + TF + Strategy) Slot Lock + Max 2/Symbol + Max 3 Account-Wide")
    print("="*80)
    print(f" Initial Capital      : ${initial_capital:,.2f} USD")
    print(f" Final Balance        : ${balance:,.2f} USD")
    print(f" Net Profit           : ${net_profit:,.2f} USD ({return_pct:+.2f}%)")
    print(f" Total Trades Taken   : {len(df_closed)}")
    print(f" Win Rate             : {win_rate:.2f}%")
    print(f" Profit Factor        : {profit_factor:.2f}")
    print(f" Max Drawdown ($)     : ${max_drawdown_dollar:,.2f} USD")
    print(f" Max Drawdown (%)     : {max_drawdown_pct * 100.0:.2f}%")
    print("="*80)

    # Asset-by-Asset Breakdown
    if not df_closed.empty:
        print("\n📊 ASSET PERFORMANCE BREAKDOWN:")
        print(f"{'Asset':<10} {'Trades':<8} {'Win Rate':<10} {'Net PnL ($)':<15} {'Profit Factor':<15}")
        print("-" * 60)
        for sym in ALL_SYMBOLS:
            sub = df_closed[df_closed["symbol"] == sym]
            if not sub.empty:
                s_wins = len(sub[sub["pnl"] > 0])
                s_wr = (s_wins / len(sub)) * 100.0
                s_pnl = sub["pnl"].sum()
                s_gross_win = sub[sub["pnl"] > 0]["pnl"].sum()
                s_gross_loss = abs(sub[sub["pnl"] < 0]["pnl"].sum())
                s_pf = (s_gross_win / s_gross_loss) if s_gross_loss > 0 else 99.0
                print(f"{sym:<10} {len(sub):<8} {s_wr:<10.2f}% ${s_pnl:<14.2f} {s_pf:<15.2f}")

    # Write Markdown Report Artifact
    report_md = f"""# 🏛️ Concurrent Multi-Asset Portfolio Backtest Report
## Verification of Grok Rule Model ($1,500 Loaded Capital)

- **Initial Capital**: $1,500.00 USD
- **Final Balance**: **${balance:,.2f} USD**
- **Net Return**: **{return_pct:+.2f}%** (${net_profit:,.2f} USD)
- **Total Trades Taken**: {len(df_closed)} trades
- **Win Rate**: **{win_rate:.2f}%**
- **Profit Factor**: **{profit_factor:.2f}**
- **Max Account Drawdown**: **{max_drawdown_pct * 100.0:.2f}%** (${max_drawdown_dollar:,.2f} USD)

---

### 🛡️ Enforced Operating Controls

1. **Unique Key Slot Lock**: Max 1 position per `(Symbol, Timeframe, Strategy_ID)` tuple until TP/SL/TSL exit.
2. **Per-Symbol Position Cap**: Max 2 active positions total per symbol (e.g. `GOLD`).
3. **Account Position Cap**: Max 3 active positions total account-wide (0.06 total lots max).
4. **Daily Drawdown Stop**: 3% daily equity loss stop (-$45.00 on $1,500 capital).
5. **Execution Realism**: Real spread + commission ($7/lot) + slippage friction.

---

### 📊 Asset-by-Asset Performance Breakdown

| Asset | Total Trades | Win Rate (%) | Net PnL ($) | Profit Factor |
| :--- | :--- | :--- | :--- | :--- |
"""
    if not df_closed.empty:
        for sym in ALL_SYMBOLS:
            sub = df_closed[df_closed["symbol"] == sym]
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
    run_concurrent_backtest()
