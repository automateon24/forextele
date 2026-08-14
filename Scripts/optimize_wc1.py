import sys
import os
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WC1_OPTIMIZER")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.ml.features import extract_df_features
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

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

def main():
    if not init_mt5():
        return

    symbol = "GOLD"
    df_h1 = fetch_bars(symbol, mt5.TIMEFRAME_H1, count=3000)
    htf_bias = get_htf_trend_bias(df_h1) if not df_h1.empty else "NEUTRAL"
    cost_m = CostModel(spread_points=0.30)
    
    configs = [
        ("M15", mt5.TIMEFRAME_M15, "FVG_RETEST", FVGRetestStrategy, True),
        ("H1", mt5.TIMEFRAME_H1, "TREND_MOMENTUM", TrendMomentumStrategy, False),
        ("M15", mt5.TIMEFRAME_M15, "SMC_CHOCH", SMCCHoCHStrategy, True),
        ("M5", mt5.TIMEFRAME_M5, "SMC_CHOCH", SMCCHoCHStrategy, True),
    ]
    
    total_unfiltered_net = 0
    total_filtered_net = 0

    for tf_str, tf_mt5, strat_name, strat_cls, use_mtf in configs:
        df = fetch_bars(symbol, tf_mt5, count=3000)
        if df.empty:
            continue
            
        strat_inst = strat_cls(symbol=symbol)
        
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
        
        # Base Trades (Unfiltered)
        base_trades = []
        filtered_trades = []
        
        for tr in engine.trades:
            if use_mtf and not validate_mtf_alignment(tr.get("side", "BUY"), htf_bias):
                continue
                
            entry_hour = tr["time"].hour
            
            # Baseline constraints that were already in WC1
            is_valid_base = True
            if strat_name == "TREND_MOMENTUM":
                if not (7 <= entry_hour <= 17):
                    is_valid_base = False
                    
            if is_valid_base:
                base_trades.append(tr)
                
            # NEW Optimized Constraints based on failure analysis
            is_valid_opt = True
            if strat_name == "FVG_RETEST":
                if entry_hour in [14, 23, 4]:
                    is_valid_opt = False
            elif strat_name == "TREND_MOMENTUM":
                if not (8 <= entry_hour <= 15):
                    is_valid_opt = False
            elif strat_name == "SMC_CHOCH":
                if entry_hour in [12, 13, 14, 15]: # Block the chaotic NY open / mid-NY 
                    is_valid_opt = False
            
            # Also requires base constraints
            if strat_name == "TREND_MOMENTUM" and not (7 <= entry_hour <= 17):
                is_valid_opt = False
                
            if is_valid_opt and is_valid_base:
                filtered_trades.append(tr)
                
        # Calculate PnL
        def calc_metrics(trades):
            balance = 1500.0
            for t in trades: balance += t["pnl"]
            return balance - 1500.0, len(trades)
            
        un_pnl, un_ct = calc_metrics(base_trades)
        opt_pnl, opt_ct = calc_metrics(filtered_trades)
        
        total_unfiltered_net += un_pnl
        total_filtered_net += opt_pnl
        
        logger.info(f"[{tf_str}] {strat_name: <15} | Base PnL: ${un_pnl:>7.2f} ({un_ct} trades) -> OPTIMIZED PnL: ${opt_pnl:>7.2f} ({opt_ct} trades)")

    logger.info("=====================================================")
    logger.info(f"Total WC1 Base Profit:     ${total_unfiltered_net:.2f}")
    logger.info(f"Total WC1 OPTIMIZED Profit: ${total_filtered_net:.2f}")
    logger.info(f"Profit Increase:           +${(total_filtered_net - total_unfiltered_net):.2f}")
    logger.info("=====================================================")
    
    mt5.shutdown()

if __name__ == "__main__":
    main()
