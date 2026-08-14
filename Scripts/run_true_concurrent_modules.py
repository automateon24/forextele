import sys
import json
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TRUE_CONCURRENT_MODULES")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment
from src.common.session_filter import is_prime_trading_hour

from src.strategy.fvg_retest import FVGRetestStrategy
from src.strategy.smc_choch import SMCCHoCHStrategy
from src.strategy.forex_asian_sweep_regime import ForexAsianSweepRegimeStrategy
from src.strategy.smc_order_block import SMCOrderBlockStrategy

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

    capital = 1500.0
    
    # Risk Config
    risk_config_path = ROOT / "config" / "risk_config.json"
    max_total_positions = 3
    max_per_symbol = 2
    if risk_config_path.exists():
        with open(risk_config_path) as f:
            cfg = json.load(f)
            max_total_positions = cfg["global"].get("max_open_positions", 3)
            max_per_symbol = cfg["global"].get("max_positions_per_symbol", 2)
            
    logger.info(f"Master Risk Caps: Max Total={max_total_positions}, Max Per Symbol={max_per_symbol}")
    
    asset_data = {}
    
    # ── MODULE 1: GOLD CORE (M15 FVG + CHoCH) ──────────────────────────────────
    df_gold_m5  = fetch_bars("GOLD", mt5.TIMEFRAME_M5,  count=30000)
    df_gold_m15 = fetch_bars("GOLD", mt5.TIMEFRAME_M15, count=10000)
    df_gold_h1  = fetch_bars("GOLD", mt5.TIMEFRAME_H1,  count=2500)
    
    if not df_gold_m15.empty:
        cost_gold = CostModel(spread_points=0.30)
        engine_gold = BacktestEngine(
            df=df_gold_m15, strategies=[], cost_model=cost_gold, 
            capital=capital, volume=0.02, slippage_usd=0.15, use_tsl=False
        )
        asset_data["GOLD"] = {
            "m5": df_gold_m5, "m15": df_gold_m15, "h1": df_gold_h1,
            "strats": {
                "GOLD_FVG_RETEST_M15": FVGRetestStrategy(symbol="GOLD"),
                "GOLD_SMC_CHOCH_M15": SMCCHoCHStrategy(symbol="GOLD")
            },
            "engine": engine_gold,
            "module": "MODULE 1 (GOLD CORE)"
        }

    # ── MODULE 2: FOREX INSTITUTIONAL ENGINE (EURUSD & GBPUSD) ────────────────
    for fx_sym in ["EURUSD", "GBPUSD"]:
        df_fx_m5  = fetch_bars(fx_sym, mt5.TIMEFRAME_M5,  count=30000)
        df_fx_m15 = fetch_bars(fx_sym, mt5.TIMEFRAME_M15, count=10000)
        df_fx_h1  = fetch_bars(fx_sym, mt5.TIMEFRAME_H1,  count=2500)
        
        if not df_fx_m15.empty:
            cost_fx = CostModel(spread_points=0.00015)
            engine_fx = BacktestEngine(
                df=df_fx_m15, strategies=[], cost_model=cost_fx, 
                capital=capital, volume=0.02, slippage_usd=0.15, use_tsl=False
            )
            asset_data[fx_sym] = {
                "m5": df_fx_m5, "m15": df_fx_m15, "h1": df_fx_h1,
                "strats": {
                    f"{fx_sym}_ASIAN_SWEEP_REGIME": ForexAsianSweepRegimeStrategy(symbol=fx_sym)
                },
                "engine": engine_fx,
                "module": f"MODULE 2 ({fx_sym} FOREX)"
            }

    # ── MODULE 3: SILVER H1 STRUCTURAL ENGINE (SILVER / XAGUSD) ───────────────
    df_ag_m5 = fetch_bars("SILVER", mt5.TIMEFRAME_M5, count=30000)
    df_ag_h1 = fetch_bars("SILVER", mt5.TIMEFRAME_H1, count=5000)
    
    if not df_ag_h1.empty:
        cost_ag = CostModel(spread_points=0.03)
        # STRICT 0.01 LOT FOR SILVER CONTRACT SIZE
        engine_ag = BacktestEngine(
            df=df_ag_h1, strategies=[], cost_model=cost_ag, 
            capital=capital, volume=0.01, slippage_usd=0.15, use_tsl=False
        )
        asset_data["SILVER"] = {
            "m5": df_ag_m5, "m15": df_ag_h1, "h1": df_ag_h1,
            "strats": {
                "SILVER_SMC_OB_H1": SMCOrderBlockStrategy(symbol="SILVER")
            },
            "engine": engine_ag,
            "module": "MODULE 3 (SILVER H1 STRUCTURAL)"
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
    logger.info(f"Starting True Concurrent Modules Simulation at {start_time}")
    
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
                
        # Risk Gate: Portfolio Capacity
        if len(active_trades) >= max_total_positions:
            continue
            
        signals_to_process = []
        
        # Check M15 boundary for Gold & Forex, H1 boundary for Silver
        is_m15_bar = (current_time.minute % 15 == 0)
        is_h1_bar  = (current_time.minute == 0)
        
        for sym, data in asset_data.items():
            if sym == "SILVER" and not is_h1_bar:
                continue
            if sym != "SILVER" and not is_m15_bar:
                continue
                
            sym_trades_open = sum(1 for tr in active_trades if tr["symbol"] == sym)
            if sym_trades_open >= max_per_symbol:
                continue
                
            # Metals session filter
            if sym in ["GOLD", "SILVER"] and not is_prime_trading_hour(current_time):
                continue
                
            df_m15 = data["m15"]
            df_h1  = data["h1"]
            
            window_m15 = df_m15[df_m15["time"] <= current_time]
            window_h1  = df_h1[df_h1["time"] <= current_time]
            
            if len(window_m15) < 50 or len(window_h1) < 50:
                continue
                
            htf_bias = get_htf_trend_bias(window_h1)
            
            for strat_id, strat in data["strats"].items():
                sig = strat.analyze(window_m15)
                if sig:
                    if sym in ["GOLD", "SILVER"]:
                        if validate_mtf_alignment(sig.side, htf_bias):
                            signals_to_process.append((sig, strat_id, data["engine"], window_m15, data["module"]))
                    else:
                        signals_to_process.append((sig, strat_id, data["engine"], window_m15, data["module"]))

        for sig, strat_id, engine, window, mod_name in signals_to_process:
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
                trade["module"] = mod_name
                trade["entry_time"] = current_time
                trade["exit_time"] = engine.df.iloc[trade["exit_bar_idx"]]["time"]
                
                active_trades.append(trade)
                logger.info(f"EXECUTED [{sig.symbol} {strat_id}] {sig.side} at {current_time} | Exit: {trade['exit_time']} | PnL: ${trade['pnl']:.2f}")

    logger.info("=== TRUE CONCURRENT MODULES SIMULATION COMPLETE ===")
    total_pnl = sum(tr["pnl"] for tr in trade_history)
    wins = sum(1 for tr in trade_history if tr["pnl"] > 0)
    losses = len(trade_history) - wins
    
    wr_pct = (wins/len(trade_history)*100) if len(trade_history) > 0 else 0
    logger.info(f"Total Shared Trades Taken: {len(trade_history)}")
    logger.info(f"Wins: {wins} | Losses: {losses} | Win Rate: {wr_pct:.2f}%")
    logger.info(f"Final Shared PnL: ${total_pnl:.2f}")
    
    modules = set(tr["module"] for tr in trade_history)
    for mod in sorted(modules):
        mod_trades = [tr for tr in trade_history if tr["module"] == mod]
        m_pnl = sum(tr["pnl"] for tr in mod_trades)
        m_wins = sum(1 for tr in mod_trades if tr["pnl"] > 0)
        m_wr = (m_wins / len(mod_trades) * 100) if mod_trades else 0
        logger.info(f"   {mod: <30} | Trades: {len(mod_trades):<3} | WR: {m_wr:.1f}% | PnL: ${m_pnl:.2f}")
        
    mt5.shutdown()

if __name__ == "__main__":
    main()
