import sys
import os
import pandas as pd
import numpy as np
import json
import time
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add workspace to path
sys.path.append(r'C:\25stragy')

# Import modules and classes from main script
import BACKTEST_V8_AI as bt

# Define execute_tsl_idx with Two-Stage TSL
def execute_tsl_idx_v15_two_stage(entry_bar: pd.Series, remaining: pd.DataFrame, hard_exit: int = 1430, 
                                  premium_scale: float = 1.0, regime: str = 'NORMAL', strat_name: str = '',
                                  index_name: str = 'NIFTY', is_expiry: bool = False):
    dna = bt.get_index_strategy_dna(index_name, strat_name)
    
    # Standard parameters
    target_pct = dna.target_pct
    sl_backstop = dna.sl_backstop
    
    # We use Two-Stage TSL:
    # 1. Activate at 10% profit (or dna.tsl_activate if set, but let's standardise to 10%)
    activate_pct = 0.10
    # 2. Breakeven floor: entry + 1%
    breakeven_pct = 0.01
    # 3. Wide trail: 18% pullback allowed from peak
    trail_pct = 0.18
    
    is_reversal = 'REVERSAL' in strat_name or 'MEAN' in strat_name or 'BLOCK' in strat_name or 'CRUSH' in strat_name or 'CLIMAX' in strat_name
    is_trend = 'TREND' in strat_name or 'BREAK' in strat_name or 'BURST' in strat_name or 'DRIVE' in strat_name
    
    # Uncapped expiry trails for ZERO_HERO and GAMMA_BLAST on expiry days
    if bt.ENABLE_EXPIRY_UNCAP and is_expiry and (strat_name in ['ZERO_HERO', 'GAMMA_BLAST']):
        target_pct = 999.0
        activate_pct = 0.20
        trail_pct = 0.25
    
    ep  = float(entry_bar['open'])
    if index_name == 'SENSEX':
        sl_backstop = min(sl_backstop, 0.20)
    elif index_name == 'BANKNIFTY':
        sl_backstop = min(sl_backstop, 0.25)
    elif index_name in ['NIFTY', 'FINNIFTY']:
        sl_backstop = min(sl_backstop, 0.25)
        
    sl  = ep * (1 - sl_backstop)
    tgt = ep * (1 + target_pct)
    thi = ep
    xp = xr = xt = None

    for _, bar in remaining.iterrows():
        ts   = bt._get_ts(bar)
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        close = float(bar['close'])
        thi  = max(thi, hi)

        # 1. HARD EXIT (EOD)
        if hhmm >= hard_exit:
            xp = close; xr = 'TIME'; xt = ts; break
            
        # 2. HARD SL
        if lo <= sl:
            xp = sl; xr = 'SL'; xt = ts; break
            
        # 3. TARGET
        if hi >= tgt:
            xp = tgt; xr = 'TARGET'; xt = ts; break
            
        # 4. TWO-STAGE TSL
        if thi >= ep * (1 + activate_pct):
            # Move SL to breakeven (ep * 1.01) or wide trail from peak, whichever is higher
            floor = max(ep * (1 + breakeven_pct), thi * (1 - trail_pct))
            if lo <= floor:
                xp = max(floor, sl); xr = 'TSL'; xt = ts; break

    if xp is None:
        xp = float(remaining.iloc[-1]['close'])
        xr = 'TIME'
        xt = bt._get_ts(remaining.iloc[-1])
        
    return xp, xr, xt

# Patch the engine function in memory
bt.execute_tsl_idx = execute_tsl_idx_v15_two_stage

# Optimized 23 active list
final_active_23 = [
    "ZERO_HERO", "BEAR_TREND_FOLLOWER", "MACD_DIVERGENCE", "MOMENTUM_BURST",
    "VWAP_BOUNCE", "GAMMA_BLAST", "OPTIONS_GREEKS", "SCALPING", "MAGIC_SQUARE",
    "BOLLINGER_SQUEEZE", "ATR_BREAK", "ULTIMATE_DAY_HIGH_LOW", "DAY_LOW_BULLISH",
    "EMA_CROSSOVER", "VOLUME_CLIMAX", "RSI_REVERSAL", "DAY_HIGH_BEARISH",
    "LONG_UNWIND", "TREND_FOLLOWING", "PUT_WRITER_SUPPORT", "AI_ENHANCED",
    "BREAKOUT", "RESIST_BREAK"
]

config_path = r'C:\25stragy\config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

for idx in config['index_profiles']:
    config['index_profiles'][idx]['active_strategies'] = final_active_23

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

def main():
    print("=" * 70)
    print("RUNNING V15 TWO-STAGE TSL BACKTEST")
    print("=" * 70)

    # ── Step 1: Load real parquets for each index ─────────────────────────────
    print("\nLoading option data for all indices...")
    datasets: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, bt.IndexConfig]] = {}
    total_days = 0

    for idx_name, cfg in bt.INDEX_CONFIGS.items():
        opt = bt.load_option_data_for_index(idx_name)
        if opt.empty:
            print(f"  [{idx_name}] SKIPPED — no parquets found")
            continue
        eod = bt.build_eod_from_option_data(opt)
        datasets[idx_name] = (opt, eod, cfg)
        total_days = max(total_days, opt['date'].nunique())

    print(f"\nLoaded {len(datasets)} indices: {list(datasets.keys())}")

    # ── Step 2: Run all indices in parallel threads ───────────────────────────
    print(f"\nRunning backtests in parallel...")
    results: Dict[str, List[bt.Trade]] = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(bt.run_index, idx_name, opt, eod, cfg): idx_name
            for idx_name, (opt, eod, cfg) in datasets.items()
        }
        for future in as_completed(futures):
            idx_name = futures[future]
            try:
                trades, name = future.result()
                results[name] = trades
                print(f"  [{name}] Completed: {len(trades)} trades", flush=True)
            except Exception as e:
                print(f"  [{idx_name}] ERROR: {e}")
                import traceback; traceback.print_exc()

    # ── Step 3: Report ────────────────────────────────────────────────────────
    print()
    bt.report_multi(results, total_days)

if __name__ == '__main__':
    main()
