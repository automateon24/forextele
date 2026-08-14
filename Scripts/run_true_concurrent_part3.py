import sys
import os
import json
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TRUE_CONCURRENT_PART3")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment
from src.common.session_filter import is_prime_trading_hour

from src.strategy.liquidity_sweep import LiquiditySweepStrategy
from src.strategy.smc_order_block import SMCOrderBlockStrategy
from src.strategy.fvg_retest import FVGRetestStrategy
from src.strategy.smc_choch import SMCCHoCHStrategy

def init_mt5():
    if not mt5.initialize():
        logger.error("MT5 initialize failed")
        return False
    return True

def fetch_bars(symbol, tf_mt5, count=30000):
    rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

def main():
    if not init_mt5():
        return

    symbols = ["GOLD", "EURUSD"]
    
    logger.info("Fetching multi-asset data arrays...")
    capital = 1500.0
    volume = 0.02
    
    risk_config_path = ROOT / "config" / "risk_config.json"
    max_total_positions = 3
    max_per_symbol = 2
    if risk_config_path.exists():
        with open(risk_config_path) as f:
            cfg = json.load(f)
            max_total_positions = cfg["global"].get("max_open_positions", 3)
            max_per_symbol = cfg["global"].get("max_positions_per_symbol", 2)
            
    logger.info(f"Risk Caps Active: Max Total = {max_total_positions}, Max Per Symbol = {max_per_symbol}")
    
    asset_data = {}
    
    for sym in symbols:
        df_m5 = fetch_bars(sym, mt5.TIMEFRAME_M5, count=30000)
        df_m15 = fetch_bars(sym, mt5.TIMEFRAME_M15, count=10000)
        df_h1 = fetch_bars(sym, mt5.TIMEFRAME_H1, count=2500)
        
        if df_m5.empty or df_m15.empty or df_h1.empty:
            logger.error(f"Failed to fetch data for {sym}. Skipping...")
            continue
            
        strats = {}
        if "GOLD" in sym:
            strats["FVG_RETEST_M15"] = FVGRetestStrategy(symbol=sym)
            strats["SMC_CHOCH_M15"] = SMCCHoCHStrategy(symbol=sym)
            cost_m = CostModel(spread_points=0.30)
        elif "SILVER" in sym:
            strats["LIQUIDITY_SWEEP_M15"] = LiquiditySweepStrategy(symbol=sym)
            strats["SMC_ORDER_BLOCK_M15"] = SMCOrderBlockStrategy(symbol=sym)
            cost_m = CostModel(spread_points=0.03)
        elif "EURUSD" in sym:
            strats["LIQUIDITY_SWEEP_M15"] = LiquiditySweepStrategy(symbol=sym)
            strats["SMC_ORDER_BLOCK_M15"] = SMCOrderBlockStrategy(symbol=sym)
            cost_m = CostModel(spread_points=0.00015)
            
        engine_m15 = BacktestEngine(
            df=df_m15, 
            strategies=[], 
            cost_model=cost_m, 
            capital=capital, 
            volume=volume, 
            slippage_usd=0.15,
            use_tsl=True
        )
        
        asset_data[sym] = {
            "m5": df_m5,
            "m15": df_m15,
            "h1": df_h1,
            "strats": strats,
            "engine": engine_m15
        }

    if "GOLD" not in asset_data:
        logger.error("GOLD data missing. Cannot run master clock.")
        return

    active_trades = []
    trade_history = []
    running_equity = capital
    peak_equity = capital
    
    master_timeline = asset_data["GOLD"]["m5"]
    start_time = master_timeline.iloc[3000]["time"]
    logger.info(f"Starting true concurrent Part 3 timeline (TSL Active) at {start_time}")
    
    for i in range(3000, len(master_timeline)):
        current_time = master_timeline.iloc[i]["time"]
        
        still_open = []
        for tr in active_trades:
            if current_time >= tr["exit_time"]:
                running_equity += tr["pnl"]
                if running_equity > peak_equity:
                    peak_equity = running_equity
                trade_history.append(tr)
            else:
                still_open.append(tr)
        active_trades = still_open
        
        if peak_equity > 0:
            current_dd = (peak_equity - running_equity) / peak_equity
            if current_dd >= 0.50:
                logger.warning("Max Drawdown 50% hit. Emergency stop.")
                break
                
        if len(active_trades) >= max_total_positions:
            continue
            
        if not is_prime_trading_hour(current_time):
            continue
            
        signals_to_process = []
        
        if current_time.minute % 15 == 0:
            for sym, data in asset_data.items():
                sym_trades_open = sum(1 for tr in active_trades if tr["symbol"] == sym)
                if sym_trades_open >= max_per_symbol:
                    continue
                    
                df_m15 = data["m15"]
                df_h1 = data["h1"]
                
                window_m15 = df_m15[df_m15["time"] <= current_time]
                window_h1 = df_h1[df_h1["time"] <= current_time]
                
                if len(window_m15) < 50 or len(window_h1) < 50:
                    continue
                    
                htf_bias = get_htf_trend_bias(window_h1)
                
                for strat_id, strat in data["strats"].items():
                    sig = strat.analyze(window_m15)
                    if sig:
                        if validate_mtf_alignment(sig.side, htf_bias):
                            signals_to_process.append((sig, strat_id, data["engine"], window_m15))

        for sig, strat_id, engine, window in signals_to_process:
            if any(tr["strategy_id"] == strat_id and tr["symbol"] == sig.symbol for tr in active_trades):
                continue
                
            if sum(1 for tr in active_trades if tr["symbol"] == sig.symbol) >= max_per_symbol:
                continue
                
            if len(active_trades) >= max_total_positions:
                continue
                
            idx = len(window) - 1
            trade = engine._simulate_execution(sig, idx)
            if trade:
                trade["strategy_id"] = strat_id
                trade["entry_time"] = current_time
                trade["exit_time"] = engine.df.iloc[trade["exit_bar_idx"]]["time"]
                
                active_trades.append(trade)
                tsl_str = "[TSL HIT]" if trade.get("tsl_active") else "[FIXED OUT]"
                logger.info(f"EXECUTED [{sig.symbol} {strat_id}] {sig.side} at {current_time} | Exit: {trade['exit_time']} | PnL: ${trade['pnl']:.2f} {tsl_str}")

    logger.info("=== TRUE CONCURRENT PART 3 COMPLETE ===")
    total_pnl = sum(tr["pnl"] for tr in trade_history)
    wins = sum(1 for tr in trade_history if tr["pnl"] > 0)
    losses = len(trade_history) - wins
    
    logger.info(f"Total Shared Trades Taken: {len(trade_history)}")
    logger.info(f"Wins: {wins} | Losses: {losses} | Win Rate: {(wins/len(trade_history)*100 if len(trade_history)>0 else 0):.2f}%")
    logger.info(f"Final Shared PnL: ${total_pnl:.2f}")
    
    for sym in symbols:
        sym_trades = [tr for tr in trade_history if tr["symbol"] == sym]
        if not sym_trades:
            continue
        s_pnl = sum(tr["pnl"] for tr in sym_trades)
        logger.info(f"   {sym: <10} | Trades: {len(sym_trades):<3} | PnL: ${s_pnl:.2f}")
        
    mt5.shutdown()

if __name__ == "__main__":
    main()
