import pandas as pd
from src.backtest.engine import BacktestEngine
from src.backtest.cost_model import CostModel
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.asian_range_scalp import AsianRangeScalpStrategy
from src.strategy.bollinger_mean_reversion import BollingerMeanReversionStrategy
import logging

logging.basicConfig(level=logging.ERROR)

symbols = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD"]

import MetaTrader5 as mt5

def load_data(symbol: str):
    if not mt5.initialize():
        return pd.DataFrame()
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 3000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def get_base_params(sym: str):
    if "GOLD" in sym:
        return CostModel(spread_points=0.30), 0.02
    elif "SILVER" in sym:
        return CostModel(spread_points=0.03), 0.005
    elif "JPY" in sym:
        return CostModel(spread_points=0.015), 0.05
    else:
        return CostModel(spread_points=0.00015), 0.05

def run_grid_search():
    results = []
    for sym in symbols:
        print(f"========================================\nOptimizing {sym}...\n========================================")
        df = load_data(sym)
        cost_m, vol = get_base_params(sym)
        
        # 1. Optimize Trend Momentum
        # For Forex, SL in pips (0.0010 = 10 pips)
        # For JPY, SL in pips (0.10 = 10 pips)
        # For GOLD, SL in USD (1.00 = 100 pips)
        if "GOLD" in sym:
            sl_options = [1.00, 2.00, 3.00, 4.00, 6.00]
            tp_options = [2.00, 4.00, 6.00, 8.00, 12.00]
        elif "SILVER" in sym:
            sl_options = [0.10, 0.20, 0.30]
            tp_options = [0.20, 0.40, 0.60]
        elif "JPY" in sym:
            sl_options = [0.10, 0.15, 0.25, 0.40] # 10 to 40 pips
            tp_options = [0.20, 0.30, 0.50, 0.80]
        else:
            sl_options = [0.0010, 0.0015, 0.0025, 0.0040] # 10 to 40 pips
            tp_options = [0.0020, 0.0030, 0.0050, 0.0080]
            
        best_tm = None
        best_tm_pf = 0.0
        
        for sl in sl_options:
            for tp in tp_options:
                # Need minimum 1:1 risk reward
                if tp < sl:
                    continue
                strat = TrendMomentumStrategy(sym, sl_dist=sl, tp_dist=tp)
                engine = BacktestEngine(df, [strat], cost_model=cost_m, volume=vol)
                trades_df = engine.run()
                if len(trades_df) < 5:
                    continue
                gross_prof = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
                gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
                pf = gross_prof / gross_loss if gross_loss > 0 else 999.0
                win_rate = len(trades_df[trades_df['outcome'] == 'WIN']) / len(trades_df)
                
                if pf > best_tm_pf and win_rate > 0.40:
                    best_tm_pf = pf
                    best_tm = {"sl": sl, "tp": tp, "pf": pf, "wr": win_rate, "trades": len(trades_df), "net": trades_df['pnl'].sum()}
                    
        if best_tm:
            print(f"[{sym}] Best TREND_MOMENTUM: SL={best_tm['sl']}, TP={best_tm['tp']} | PF: {best_tm['pf']:.2f}, WR: {best_tm['wr']:.1%}, Net: ${best_tm['net']:.2f}")
            results.append({"sym": sym, "strat": "TREND_MOMENTUM", **best_tm})
        else:
            print(f"[{sym}] TREND_MOMENTUM could not find profitable parameters.")
            
        # 2. Optimize Asian Range Scalp
        # Buffer and TP Ratio
        if "GOLD" in sym:
            buffer_opts = [0.50, 1.00, 1.50]
        elif "SILVER" in sym:
            buffer_opts = [0.05, 0.10]
        elif "JPY" in sym:
            buffer_opts = [0.05, 0.10, 0.15]
        else:
            buffer_opts = [0.0005, 0.0010, 0.0015]
            
        ratio_opts = [0.8, 1.0, 1.5, 2.0]
        
        best_as = None
        best_as_pf = 0.0
        
        for b in buffer_opts:
            for r in ratio_opts:
                strat = AsianRangeScalpStrategy(sym, buffer_override=b, tp_ratio_override=r)
                engine = BacktestEngine(df, [strat], cost_model=cost_m, volume=vol)
                trades_df = engine.run()
                if len(trades_df) < 5:
                    continue
                gross_prof = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
                gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
                pf = gross_prof / gross_loss if gross_loss > 0 else 999.0
                win_rate = len(trades_df[trades_df['outcome'] == 'WIN']) / len(trades_df)
                
                if pf > best_as_pf and win_rate > 0.45: # Scalping needs higher WR
                    best_as_pf = pf
                    best_as = {"buffer": b, "ratio": r, "pf": pf, "wr": win_rate, "trades": len(trades_df), "net": trades_df['pnl'].sum()}
                    
        if best_as:
            print(f"[{sym}] Best ASIAN_SCALP: Buffer={best_as['buffer']}, TP_Ratio={best_as['ratio']} | PF: {best_as['pf']:.2f}, WR: {best_as['wr']:.1%}, Net: ${best_as['net']:.2f}")
            results.append({"sym": sym, "strat": "ASIAN_SCALP", **best_as})
        else:
            print(f"[{sym}] ASIAN_SCALP could not find profitable parameters.")
            
    import json
    with open("data/optimal_forex_dna.json", "w") as f:
        json.dump(results, f, indent=4)
        print("\nSaved optimal DNA configuration to data/optimal_forex_dna.json")

if __name__ == "__main__":
    run_grid_search()
