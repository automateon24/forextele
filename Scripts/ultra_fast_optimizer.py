import sys
import os
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import MetaTrader5 as mt5

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtest.engine import BacktestEngine
from src.backtest.cost_model import CostModel
from src.strategy.trend_momentum import TrendMomentumStrategy
from src.strategy.asian_range_scalp import AsianRangeScalpStrategy
def get_base_params(sym: str):
    if "GOLD" in sym or "XAU" in sym:
        return CostModel(spread_points=0.10, commission_per_lot=0.0), 0.02
    elif "SILVER" in sym or "XAG" in sym:
        return CostModel(spread_points=0.01, commission_per_lot=0.0), 0.005
    elif "JPY" in sym:
        return CostModel(spread_points=0.002, commission_per_lot=0.0), 0.05
    else:
        return CostModel(spread_points=0.00002, commission_per_lot=0.0), 0.05

ALL_SYMBOLS = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD"]

def fetch_bars(symbol: str, count: int = 3000) -> pd.DataFrame:
    if not mt5.initialize():
        return pd.DataFrame()
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def test_parameters(symbol: str, strat_type: str, df: pd.DataFrame, params: dict) -> dict:
    cost_m, vol = get_base_params(symbol)
    
    if strat_type == "TREND_MOMENTUM":
        strat = TrendMomentumStrategy(symbol)
        strat.sl_dist = params['sl']
        strat.tp_ratio = params['tp_ratio']
    elif strat_type == "ASIAN_RANGE_SCALP":
        strat = AsianRangeScalpStrategy(symbol)
        strat.buffer = params['buffer']
        strat.tp_ratio = params['tp_ratio']
        
    engine = BacktestEngine(
        df=df,
        strategies=[strat],
        cost_model=cost_m,
        capital=1500.0,
        volume=vol,
        use_tsl=False,
        max_dd_pct=0.30,
        slippage_usd=0.00
    )
    engine.run()
    
    valid_trades = []
    for tr in engine.trades:
        # We removed MTF post filter, just keep prime hours
        time_hour = tr["time"].hour
        if time_hour in [11] or (18 <= time_hour <= 22):
            continue
        valid_trades.append(tr)
        
    net_pnl = sum(t["pnl"] for t in valid_trades)
    return {"params": params, "pnl": net_pnl, "trades": len(valid_trades)}

def optimize_symbol(symbol: str):
    df = fetch_bars(symbol)
    if df.empty:
        return symbol, None, None, None, None
        
    best_trend_params = None
    best_trend_pnl = -999999
    
    # Very small grid for Trend Momentum
    # Standard is sl=0.0030 (Forex), try wide SL and inverted Risk Reward to capture high win rate
    sl_grids = [0.0020, 0.0030, 0.0050, 0.0080, 0.0100]
    tp_ratios = [0.5, 1.0, 1.5, 2.0, 3.0]
    
    if "GOLD" in symbol or "XAU" in symbol:
        sl_grids = [2.0, 3.0, 5.0, 8.0, 12.0]
    elif "JPY" in symbol:
        sl_grids = [0.20, 0.30, 0.50, 0.80, 1.20]
    elif "SILVER" in symbol:
        sl_grids = [0.10, 0.20, 0.30, 0.50]
        
    for sl in sl_grids:
        for tp_r in tp_ratios:
            res = test_parameters(symbol, "TREND_MOMENTUM", df, {'sl': sl, 'tp_ratio': tp_r})
            if res['pnl'] > best_trend_pnl:
                best_trend_pnl = res['pnl']
                best_trend_params = res['params']

    # Asian Range Scalp grid
    best_asian_params = None
    best_asian_pnl = -999999
    
    buffer_grids = [0.0005, 0.0010, 0.0015, 0.0020]
    if "GOLD" in symbol or "XAU" in symbol:
        buffer_grids = [0.5, 1.0, 1.5, 2.0]
    elif "JPY" in symbol:
        buffer_grids = [0.05, 0.10, 0.15, 0.20]
    elif "SILVER" in symbol:
        buffer_grids = [0.02, 0.05, 0.08, 0.10]
        
    for buf in buffer_grids:
        for tp_r in tp_ratios:
            res = test_parameters(symbol, "ASIAN_RANGE_SCALP", df, {'buffer': buf, 'tp_ratio': tp_r})
            if res['pnl'] > best_asian_pnl:
                best_asian_pnl = res['pnl']
                best_asian_params = res['params']
                
    return symbol, best_trend_params, best_trend_pnl, best_asian_params, best_asian_pnl

if __name__ == "__main__":
    mt5.initialize()
    results = {}
    
    # Run sequentially for stability on Windows with MT5 (MT5 connection issues in ProcessPool)
    for sym in ALL_SYMBOLS:
        _, t_params, t_pnl, a_params, a_pnl = optimize_symbol(sym)
        print(f"{sym}: Trend={t_pnl:.2f} {t_params} | Asian={a_pnl:.2f} {a_params}")
        results[sym] = {
            "TREND_MOMENTUM": t_params,
            "ASIAN_RANGE_SCALP": a_params
        }
            
    # Save to file
    import json
    os.makedirs("data", exist_ok=True)
    with open("data/optimal_forex_dna.json", "w") as f:
        json.dump(results, f, indent=4)
        
    mt5.shutdown()
    print("Optimization Complete! Saved to data/optimal_forex_dna.json")
