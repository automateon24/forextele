import sys
import os
import json
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TRUE_CONCURRENT")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

from src.strategy.fvg_retest import FVGRetestStrategy
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.smc_choch import SMCCHoCHStrategy

def init_mt5():
    if not mt5.initialize():
        logger.error("MT5 initialize failed")
        return False
    return True

def fetch_bars(symbol, tf_mt5, count=6000):
    rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

def main():
    if not init_mt5():
        return

    symbol = "GOLD"
    
    logger.info("Fetching M5, M15, and H1 data arrays...")
    # Fetch data. 30000 M5 = 10000 M15 = 2500 H1
    df_m5 = fetch_bars(symbol, mt5.TIMEFRAME_M5, count=30000)
    df_m15 = fetch_bars(symbol, mt5.TIMEFRAME_M15, count=10000)
    df_h1 = fetch_bars(symbol, mt5.TIMEFRAME_H1, count=2500)
    
    if df_m5.empty or df_m15.empty or df_h1.empty:
        logger.error("Failed to fetch data.")
        return

    cost_m = CostModel(spread_points=0.30)
    capital = 1500.0
    volume = 0.02
    
    # Read Risk Config
    risk_config_path = ROOT / "config" / "risk_config.json"
    max_total_positions = 3
    max_per_symbol = 2
    if risk_config_path.exists():
        with open(risk_config_path) as f:
            cfg = json.load(f)
            max_total_positions = cfg["global"].get("max_open_positions", 3)
            max_per_symbol = cfg["global"].get("max_positions_per_symbol", 2)
            
    logger.info(f"Risk Caps Active: Max Total = {max_total_positions}, Max Per Symbol = {max_per_symbol}")
    
    strat_m5_choch = SMCCHoCHStrategy(symbol=symbol)
    strat_m15_choch = SMCCHoCHStrategy(symbol=symbol)
    strat_m15_fvg = FVGRetestStrategy(symbol=symbol)
    strat_h1_trend = TrendMomentumStrategy(symbol=symbol)
    
    # Unified execution engine for simulation
    engine_m5 = BacktestEngine(df=df_m5, strategies=[], cost_model=cost_m, capital=capital, volume=volume, slippage_usd=0.15)
    engine_m15 = BacktestEngine(df=df_m15, strategies=[], cost_model=cost_m, capital=capital, volume=volume, slippage_usd=0.15)
    engine_h1 = BacktestEngine(df=df_h1, strategies=[], cost_model=cost_m, capital=capital, volume=volume, slippage_usd=0.15)

    active_trades = []
    trade_history = []
    running_equity = capital
    peak_equity = capital
    
    # The master loop steps through the M5 timeline (highest resolution)
    # Start at index 3000 to ensure we have enough lookback for H1 (200 H1 bars = 2400 M5 bars).
    start_time = df_m5.iloc[3000]["time"]
    logger.info(f"Starting true concurrent timeline at {start_time}")
    
    for i in range(3000, len(df_m5)):
        current_time = df_m5.iloc[i]["time"]
        
        # 1. Close expired trades
        still_open = []
        for tr in active_trades:
            if current_time >= tr["exit_time"]:
                # Trade closes!
                running_equity += tr["pnl"]
                if running_equity > peak_equity:
                    peak_equity = running_equity
                trade_history.append(tr)
            else:
                still_open.append(tr)
        active_trades = still_open
        
        # Risk Gate: Max Drawdown
        if peak_equity > 0:
            current_dd = (peak_equity - running_equity) / peak_equity
            if current_dd >= 0.30:
                logger.warning("Max Drawdown 30% hit. Trading halted.")
                break
                
        # Risk Gate: Portfolio Capacity
        if len(active_trades) >= max_total_positions:
            continue
        gold_trades_open = sum(1 for tr in active_trades if tr["symbol"] == "GOLD")
        if gold_trades_open >= max_per_symbol:
            continue
            
        # 2. Check Strategies at this precise time
        # Get exact slices up to current_time
        # For M5, the bar closing AT current_time is at index `i` (meaning window is up to i)
        window_m5 = df_m5.iloc[:i+1]
        
        # For M15 and H1, we only want bars that have CLOSED <= current_time.
        # But wait, df.iloc[:x] means bars up to index x-1. 
        # Actually, mt5 returns the bar OPEN time. A 15m bar opening at 10:00 closes at 10:15.
        # So at 10:15, the 10:00 bar is fully closed.
        window_m15 = df_m15[df_m15["time"] <= current_time]
        window_h1 = df_h1[df_h1["time"] <= current_time]
        
        signals_to_process = []
        
        # --- M15 CHoCH & FVG ---
        # Only check M15 strategies if an M15 bar just closed (time is divisible by 15 mins)
        if current_time.minute % 15 == 0:
            sig_m15_choch = strat_m15_choch.analyze(window_m15)
            if sig_m15_choch:
                signals_to_process.append((sig_m15_choch, "SMC_CHOCH_M15", engine_m15, window_m15))
                
            sig_m15_fvg = strat_m15_fvg.analyze(window_m15)
            if sig_m15_fvg:
                # MTF Check for FVG
                htf_bias = get_htf_trend_bias(window_h1)
                if validate_mtf_alignment(sig_m15_fvg.side, htf_bias):
                    signals_to_process.append((sig_m15_fvg, "FVG_RETEST_M15", engine_m15, window_m15))
                    
        for sig, strat_id, engine, window in signals_to_process:
            # Enforce 1 trade per strategy
            if any(tr["strategy_id"] == strat_id for tr in active_trades):
                continue
                
            # Re-check capacity (in case multiple signals fired at the exact same minute)
            if sum(1 for tr in active_trades if tr["symbol"] == "GOLD") >= max_per_symbol:
                logger.info(f"Blocked {strat_id} signal due to max 2 GOLD positions cap.")
                continue
                
            # Simulate to end using the specific timeframe engine to get exit time and exact pnl
            # The current index for the simulation engine is the last row of 'window'
            idx = len(window) - 1
            trade = engine._simulate_execution(sig, idx)
            if trade:
                trade["strategy_id"] = strat_id
                trade["entry_time"] = current_time
                # _simulate_execution returns exit_bar_idx. We need exact exit_time.
                trade["exit_time"] = engine.df.iloc[trade["exit_bar_idx"]]["time"]
                
                active_trades.append(trade)
                logger.info(f"EXECUTED [{strat_id}] {sig.side} at {current_time} | Exit projected at {trade['exit_time']} | PnL: ${trade['pnl']:.2f}")

    logger.info("=== TRUE CONCURRENT BACKTEST COMPLETE ===")
    total_pnl = sum(tr["pnl"] for tr in trade_history)
    wins = sum(1 for tr in trade_history if tr["pnl"] > 0)
    losses = len(trade_history) - wins
    
    logger.info(f"Total Shared Trades Taken: {len(trade_history)}")
    logger.info(f"Wins: {wins} | Losses: {losses}")
    logger.info(f"Final Shared PnL: ${total_pnl:.2f}")
    
    # Strat Breakdown
    for sid in ["SMC_CHOCH_M5", "SMC_CHOCH_M15", "FVG_RETEST_M15", "TREND_MOMENTUM_H1"]:
        s_trades = [tr for tr in trade_history if tr["strategy_id"] == sid]
        if not s_trades:
            continue
        s_pnl = sum(tr["pnl"] for tr in s_trades)
        logger.info(f"   {sid: <20} | Trades: {len(s_trades):<3} | PnL: ${s_pnl:.2f}")
        
    mt5.shutdown()

if __name__ == "__main__":
    main()
