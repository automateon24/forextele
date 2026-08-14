import sys
import os
import time
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GOLD_SMC_BACKTEST")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MetaTrader5 as mt5

from src.backtest.cost_model import CostModel
from src.backtest.engine import BacktestEngine
from src.ml.features import extract_df_features
from src.common.mtf_filter import get_htf_trend_bias, validate_mtf_alignment

# Import our new advanced SMC strategies
from src.strategy.smc_order_block import SMCOrderBlockStrategy
from src.strategy.liquidity_sweep import LiquiditySweepStrategy
from src.strategy.smc_choch import SMCCHoCHStrategy

STRATEGIES = [
    ("SMC_ORDER_BLOCK", SMCOrderBlockStrategy),
    ("LIQUIDITY_SWEEP", LiquiditySweepStrategy),
    ("SMC_CHOCH", SMCCHoCHStrategy),
]

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
    logger.info("==========================================================")
    logger.info(" GOLD-ONLY ADVANCED SMC BACKTEST (M5 & M15)")
    logger.info("==========================================================")

    if not init_mt5():
        return

    symbol = "GOLD"
    timeframes = [("M15", mt5.TIMEFRAME_M15), ("M5", mt5.TIMEFRAME_M5)]
    
    # Fetch H1 for HTF momentum alignment
    df_h1 = fetch_bars(symbol, mt5.TIMEFRAME_H1, count=3000)
    htf_bias = get_htf_trend_bias(df_h1) if not df_h1.empty else "NEUTRAL"
    logger.info(f"GOLD H1 Institutional Bias: {htf_bias}")

    all_executed_trades = []

    for tf_str, tf_mt5 in timeframes:
        logger.info(f"\nProcessing {symbol} on {tf_str}...")
        df = fetch_bars(symbol, tf_mt5, count=3000)
        if df.empty:
            continue
            
        df = extract_df_features(df)
        
        # REALISTIC Cost Model: True Spread + $0.30 slippage + $7/lot commission
        cost_m = CostModel(spread_points=0.30)
        
        for strat_name, strat_cls in STRATEGIES:
            strat_inst = strat_cls(symbol=symbol)
            
            # Run engine independently for each strategy to track their distinct performance
            engine = BacktestEngine(
                df=df,
                strategies=[strat_inst],
                cost_model=cost_m,
                capital=1500.0,
                volume=0.02,
                use_tsl=False, # Disable TSL to allow SMC 2:1 RR to hit
                max_dd_pct=0.30,
                slippage_usd=0.15 # $0.15 in, $0.15 out
            )
            engine.run()
            
            # Filter trades by HTF Alignment
            valid_trades = []
            for tr in engine.trades:
                if validate_mtf_alignment(tr.get("side", "BUY"), htf_bias):
                    tr["strategy"] = strat_name
                    tr["timeframe"] = tf_str
                    valid_trades.append(tr)
            
            # Simple chronological PnL aggregation for this specific strategy+TF combo
            balance = 1500.0
            peak = 1500.0
            max_dd = 0.0
            gross_win = 0.0
            gross_loss = 0.0
            wins = 0
            
            for tr in valid_trades:
                balance += tr["pnl"]
                if balance > peak:
                    peak = balance
                dd = (peak - balance) / peak
                if dd > max_dd:
                    max_dd = dd
                    
                if tr["pnl"] > 0:
                    gross_win += tr["pnl"]
                    wins += 1
                else:
                    gross_loss += abs(tr["pnl"])
                    
            net_profit = balance - 1500.0
            win_rate = (wins / len(valid_trades) * 100) if valid_trades else 0
            pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0)
            
            logger.info(f"[{tf_str}] {strat_name: <20} | Trades: {len(valid_trades):<3} | WR: {win_rate:>5.1f}% | Net: ${net_profit:>7.2f} | PF: {pf:>4.2f} | MaxDD: {max_dd*100:>4.1f}%")

    mt5.shutdown()
    logger.info("==========================================================")
    logger.info(" GOLD-ONLY SMC BACKTEST COMPLETE")

if __name__ == "__main__":
    main()
