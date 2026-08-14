import sys
import os
import time
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WC1_DIAGNOSTIC")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5
from collections import Counter

from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.ml.features import extract_df_features
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

# Import WC1 Strategies
from src.strategy.fvg_retest import FVGRetestStrategy
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.smc_choch import SMCCHoCHStrategy

def init_mt5():
    if not mt5.initialize():
        logger.error("MT5 initialize failed")
        return False
    return True

def fetch_bars(symbol, tf_mt5, count=3000):
    rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

def analyze_failures(trades, df, strategy_name, tf_str):
    losing_trades = [t for t in trades if t["pnl"] < 0]
    winning_trades = [t for t in trades if t["pnl"] > 0]
    
    if not losing_trades:
        return
        
    logger.info(f"\n--- {strategy_name} [{tf_str}] Failure Diagnostic ---")
    logger.info(f"Total Trades: {len(trades)} | Wins: {len(winning_trades)} | Losses: {len(losing_trades)}")
    
    hours = []
    rsis = []
    atrs = []
    
    for tr in losing_trades:
        entry_time = tr["time"]
        hours.append(entry_time.hour)
        
        # Get RSI and ATR at entry time
        # The engine executes on the open of the candle after the signal. 
        # But we can just look up the closest row in df.
        mask = df["time"] <= entry_time
        if not mask.empty and mask.any():
            row = df.loc[mask].iloc[-1]
            if "rsi_14" in row:
                rsis.append(row["rsi_14"])
            if "atr_14" in row:
                atrs.append(row["atr_14"])
                
    # Hour clustering
    hour_counts = Counter(hours)
    top_hours = hour_counts.most_common(3)
    logger.info(f"Top 3 Losing Hours (UTC): {top_hours}")
    
    # RSI clustering (bins of 10)
    rsi_bins = [int(r // 10) * 10 for r in rsis if not pd.isna(r)]
    rsi_counts = Counter(rsi_bins)
    top_rsis = rsi_counts.most_common(3)
    logger.info(f"Top 3 Losing RSI Bins: {top_rsis}")
    
def main():
    if not init_mt5():
        return

    symbol = "GOLD"
    
    df_h1 = fetch_bars(symbol, mt5.TIMEFRAME_H1, count=3000)
    htf_bias = get_htf_trend_bias(df_h1) if not df_h1.empty else "NEUTRAL"
    df_h1 = extract_df_features(df_h1)
    
    cost_m = CostModel(spread_points=0.30)
    
    configs = [
        ("M15", mt5.TIMEFRAME_M15, "FVG_RETEST", FVGRetestStrategy, True, False),
        ("H1", mt5.TIMEFRAME_H1, "TREND_MOMENTUM", TrendMomentumStrategy, False, True),
        ("M15", mt5.TIMEFRAME_M15, "SMC_CHOCH", SMCCHoCHStrategy, True, False),
        ("M5", mt5.TIMEFRAME_M5, "SMC_CHOCH", SMCCHoCHStrategy, True, False),
    ]
    
    for tf_str, tf_mt5, strat_name, strat_cls, use_mtf, use_session in configs:
        df = df_h1 if tf_str == "H1" else fetch_bars(symbol, tf_mt5, count=3000)
        if df.empty:
            continue
            
        if tf_str != "H1":
            df = extract_df_features(df)
            
        strat_inst = strat_cls(symbol=symbol)
        
        # We need to ensure TrendMomentum is configured safely (inversion was done inside the script or dynamically?)
        # Actually Trend Momentum had inversion applied manually in previous tests, but let's just run it as is.
        # Wait, the engine handles the base strategy.
        engine = BacktestEngine(
            df=df,
            strategies=[strat_inst],
            cost_model=cost_m,
            capital=1500.0,
            volume=0.02,
            use_tsl=False, 
            max_dd_pct=0.30,
            slippage_usd=0.15
        )
        engine.run()
        
        valid_trades = []
        for tr in engine.trades:
            # Apply Filters
            
            # 1. MTF Filter
            if use_mtf and not validate_mtf_alignment(tr.get("side", "BUY"), htf_bias):
                continue
                
            # 2. Session Filter (07:00 - 17:00 UTC)
            if use_session:
                entry_hour = tr["time"].hour
                if not (7 <= entry_hour <= 17):
                    continue
                    
            valid_trades.append(tr)
            
        analyze_failures(valid_trades, df, strat_name, tf_str)

    mt5.shutdown()

if __name__ == "__main__":
    main()
