import sys
import os
import time
import logging
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GROK_FAST_SWEEP")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.symbol_specs import get_verified_symbol_spec
from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.ml.features import extract_df_features
from src.ml.filter import MLSignalFilter
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

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

BLOCKS = [(h, h + 1) for h in range(0, 24, 2)]

def fetch_bars(symbol: str, tf_mt5: int, count: int = 3000) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

def run_stage2(candidate_trades, initial_capital=1500.0):
    balance = initial_capital
    peak_equity = initial_capital
    max_drawdown_dollar = 0.0
    max_drawdown_pct = 0.0

    max_positions_per_symbol = 1
    max_account_positions = 2
    daily_loss_limit_pct = 0.03

    open_positions = []
    executed_trades = []

    daily_realized_pnl = 0.0
    current_day = None

    for tr in candidate_trades:
        tr_time = tr["time"]
        tr_date = tr_time.date()
        sym = tr["symbol"]
        key = tr["key"]

        if current_day != tr_date:
            current_day = tr_date
            daily_realized_pnl = 0.0

        remaining = []
        for pos in open_positions:
            pos_exit_time = pos.get("exit_time", pos["time"] + timedelta(hours=1))
            if pos_exit_time <= tr_time:
                balance += pos["pnl"]
                daily_realized_pnl += pos["pnl"]
                executed_trades.append(pos)
            else:
                remaining.append(pos)

        open_positions = remaining

        if balance > peak_equity:
            peak_equity = balance
        dd_dollar = peak_equity - balance
        dd_pct = (dd_dollar / peak_equity) if peak_equity > 0 else 0.0
        if dd_dollar > max_drawdown_dollar:
            max_drawdown_dollar = dd_dollar
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct

        if daily_realized_pnl < -(initial_capital * daily_loss_limit_pct):
            continue

        if len(open_positions) >= max_account_positions:
            continue

        sym_pos_count = len([p for p in open_positions if p["symbol"] == sym])
        if sym_pos_count >= max_positions_per_symbol:
            continue

        key_pos_count = len([p for p in open_positions if p["key"] == key])
        if key_pos_count >= 1:
            continue

        open_positions.append(tr)

    for pos in open_positions:
        balance += pos["pnl"]
        executed_trades.append(pos)

    df_executed = pd.DataFrame(executed_trades)
    net_profit = balance - initial_capital
    return_pct = (net_profit / initial_capital) * 100.0
    win_rate = (len(df_executed[df_executed["pnl"] > 0]) / len(df_executed) * 100.0) if not df_executed.empty else 0.0
    profit_factor = (df_executed[df_executed["pnl"] > 0]["pnl"].sum() / abs(df_executed[df_executed["pnl"] < 0]["pnl"].sum())) if not df_executed.empty and abs(df_executed[df_executed["pnl"] < 0]["pnl"].sum()) > 0 else 0.0

    return {
        "balance": balance,
        "net_profit": net_profit,
        "return_pct": return_pct,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown_pct * 100.0
    }

def main():
    if not mt5.initialize():
        logger.error("MT5 initialize failed.")
        return

    logger.info("Starting FAST SWEEP (Stage 1)...")
    raw_candidate_trades = []

    for sym in ALL_SYMBOLS:
        for tf_str, tf_mt5 in ALL_TIMEFRAMES:
            df = fetch_bars(sym, tf_mt5, count=3000)
            if df.empty or len(df) < 60: continue

            df = extract_df_features(df)
            cost_m = CostModel(spread_points=0.30 if "GOLD" in sym else 0.00030)
            strats_inst = [st_cls(symbol=sym) for _, st_cls in ALL_STRATEGIES]
            volume_size = 0.005 if "SILVER" in sym else 0.02

            df_h1 = fetch_bars(sym, mt5.TIMEFRAME_H1, count=3000) if tf_str != "H1" else df
            htf_bias = get_htf_trend_bias(df_h1) if not df_h1.empty else "NEUTRAL"

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
                if not validate_mtf_alignment(tr.get("side", "BUY"), htf_bias):
                    continue

                tr["symbol"] = sym
                tr["timeframe"] = tf_str
                tr["key"] = f"{sym}_{tf_str}_{tr['strategy_id']}"
                raw_candidate_trades.append(tr)

    mt5.shutdown()
    logger.info(f"Stage 1 Complete: {len(raw_candidate_trades)} raw trades generated.")

    raw_candidate_trades.sort(key=lambda x: x["time"])
    
    csv_path = Path("reports/fast_sweep_results.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Window', 'Profit Factor', 'Win Rate (%)', 'Max Drawdown (%)', 'Net Profit ($)', 'Return (%)'])
        
        for start, end in BLOCKS:
            filtered_trades = []
            for tr in raw_candidate_trades:
                hour = tr["time"].hour
                
                # Default failure zones
                if 21 <= hour <= 22: continue
                if hour == 11: continue
                
                # Custom sweep block
                if start <= hour <= end: continue
                
                filtered_trades.append(tr)
            
            res = run_stage2(filtered_trades)
            writer.writerow([
                f"{start:02d}-{end:02d}",
                f"{res['profit_factor']:.2f}",
                f"{res['win_rate']:.2f}",
                f"{res['max_drawdown_pct']:.2f}",
                f"{res['net_profit']:.2f}",
                f"{res['return_pct']:.2f}"
            ])
            logger.info(f"Window {start:02d}-{end:02d} | PF: {res['profit_factor']:.2f} | Net: ${res['net_profit']:.2f} | DD: {res['max_drawdown_pct']:.2f}%")

if __name__ == "__main__":
    main()
