import sys
import json
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CRYPTO_BACKTEST")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

from src.strategy.fvg_retest import FVGRetestStrategy
from src.strategy.smc_choch import SMCCHoCHStrategy
from src.strategy.liquidity_sweep import LiquiditySweepStrategy
from src.strategy.smc_order_block import SMCOrderBlockStrategy
from src.strategy.chart_pattern_swing import ChartPatternSwingStrategy
from src.strategy.macd_momentum import MACDMomentumStrategy
from src.strategy.ema_crossover import EMACrossoverStrategy

SYMBOLS = ["BTCUSD", "ETHUSD"]

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

def build_strategies(sym):
    strats = {
        "FVG_RETEST_M15": FVGRetestStrategy(symbol=sym),
        "SMC_CHOCH_M15": SMCCHoCHStrategy(symbol=sym),
        "LIQUIDITY_SWEEP_M15": LiquiditySweepStrategy(symbol=sym),
        "SMC_ORDER_BLOCK_M15": SMCOrderBlockStrategy(symbol=sym),
        "CHART_PATTERN_H1": ChartPatternSwingStrategy(symbol=sym),
        "MACD_12_26_9_H1": MACDMomentumStrategy(symbol=sym, fast=12, slow=26, signal=9),
        "MACD_19_39_9_H1": MACDMomentumStrategy(symbol=sym, fast=19, slow=39, signal=9),
        "EMA_21_55_H1": EMACrossoverStrategy(symbol=sym, fast=21, slow=55),
        "EMA_50_200_H1": EMACrossoverStrategy(symbol=sym, fast=50, slow=200)
    }
    return strats

def main():
    if not init_mt5():
        return

    capital = 1500.0
    volume = 0.02
    
    max_total_positions = 3
    max_per_symbol = 2
    logger.info(f"Crypto Backtest Active: Symbols={SYMBOLS}, Volume={volume}, Max Positions={max_total_positions}")
    
    asset_data = {}
    
    for sym in SYMBOLS:
        df_m5 = fetch_bars(sym, mt5.TIMEFRAME_M5, count=30000)
        df_m15 = fetch_bars(sym, mt5.TIMEFRAME_M15, count=10000)
        df_h1 = fetch_bars(sym, mt5.TIMEFRAME_H1, count=3000)
        df_h4 = fetch_bars(sym, mt5.TIMEFRAME_H4, count=1000)
        
        if df_m5.empty or df_m15.empty or df_h1.empty:
            logger.error(f"Failed to fetch data for {sym}. Skipping...")
            continue
            
        if "BTC" in sym:
            cost_m = CostModel(spread_points=10.00)  # $10.00 spread on BTC
            slippage = 0.50
        else:
            cost_m = CostModel(spread_points=1.00)   # $1.00 spread on ETH
            slippage = 0.05
            
        engine_m15 = BacktestEngine(
            df=df_m15, strategies=[], cost_model=cost_m, 
            capital=capital, volume=volume, slippage_usd=slippage, use_tsl=False
        )
        
        asset_data[sym] = {
            "m5": df_m5,
            "m15": df_m15,
            "h1": df_h1,
            "h4": df_h4,
            "strats": build_strategies(sym),
            "engine": engine_m15
        }

    if "BTCUSD" not in asset_data:
        logger.error("BTCUSD data missing. Cannot run master clock.")
        return

    active_trades = []
    trade_history = []
    running_equity = capital
    peak_equity = capital
    
    master_timeline = asset_data["BTCUSD"]["m5"]
    start_time = master_timeline.iloc[3000]["time"]
    logger.info(f"Starting Crypto Concurrent Simulation at {start_time}")
    
    for i in range(3000, len(master_timeline)):
        current_time = master_timeline.iloc[i]["time"]
        
        # 1. Close expired trades
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
        
        # Risk Gate: Max Drawdown 30%
        if peak_equity > 0:
            current_dd = (peak_equity - running_equity) / peak_equity
            if current_dd >= 0.30:
                logger.warning("Max Drawdown 30% hit. Trading halted.")
                break
                
        if len(active_trades) >= max_total_positions:
            continue
            
        signals_to_process = []
        is_m15_bar = (current_time.minute % 15 == 0)
        
        if is_m15_bar:
            for sym, data in asset_data.items():
                sym_trades_open = sum(1 for tr in active_trades if tr["symbol"] == sym)
                if sym_trades_open >= max_per_symbol:
                    continue
                    
                df_m15 = data["m15"]
                df_h1  = data["h1"]
                
                window_m15 = df_m15[df_m15["time"] <= current_time]
                window_h1  = df_h1[df_h1["time"] <= current_time]
                
                if len(window_m15) < 50 or len(window_h1) < 50:
                    continue
                    
                htf_bias = get_htf_trend_bias(window_h1)
                
                for strat_id, strat in data["strats"].items():
                    target_window = window_h1 if "_H1" in strat_id else window_m15
                    sig = strat.analyze(target_window)
                    if sig:
                        if validate_mtf_alignment(sig.side, htf_bias):
                            signals_to_process.append((sig, strat_id, data["engine"], target_window))

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
                logger.info(f"EXECUTED [{sig.symbol} {strat_id}] {sig.side} at {current_time} | Exit: {trade['exit_time']} | PnL: ${trade['pnl']:.2f}")

    logger.info("=== CRYPTO CONCURRENT SIMULATION COMPLETE ===")
    total_pnl = sum(tr["pnl"] for tr in trade_history)
    wins = sum(1 for tr in trade_history if tr["pnl"] > 0)
    losses = len(trade_history) - wins
    
    wr_pct = (wins/len(trade_history)*100) if len(trade_history) > 0 else 0
    logger.info(f"Total Crypto Trades Taken: {len(trade_history)}")
    logger.info(f"Wins: {wins} | Losses: {losses} | Win Rate: {wr_pct:.2f}%")
    logger.info(f"Final Shared PnL: ${total_pnl:.2f}")
    
    for sym in SYMBOLS:
        sym_trades = [tr for tr in trade_history if tr["symbol"] == sym]
        if not sym_trades:
            continue
        s_pnl = sum(tr["pnl"] for tr in sym_trades)
        s_wins = sum(1 for tr in sym_trades if tr["pnl"] > 0)
        s_wr = (s_wins / len(sym_trades) * 100)
        logger.info(f"   {sym: <10} | Trades: {len(sym_trades):<3} | WR: {s_wr:.1f}% | PnL: ${s_pnl:.2f}")

    logger.info("--- Strategy Breakdown for Crypto ---")
    all_strats = set(tr["strategy_id"] for tr in trade_history)
    for st_id in sorted(all_strats):
        st_trades = [tr for tr in trade_history if tr["strategy_id"] == st_id]
        st_pnl = sum(tr["pnl"] for tr in st_trades)
        st_wins = sum(1 for tr in st_trades if tr["pnl"] > 0)
        st_wr = (st_wins / len(st_trades) * 100)
        logger.info(f"   {st_id: <25} | Trades: {len(st_trades):<3} | WR: {st_wr:.1f}% | PnL: ${st_pnl:.2f}")
        
    mt5.shutdown()

if __name__ == "__main__":
    main()
