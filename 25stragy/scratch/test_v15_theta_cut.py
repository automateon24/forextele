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

# Define execute_tsl_idx with Theta-Preservation Cut
def execute_tsl_idx_v15_theta(entry_bar: pd.Series, remaining: pd.DataFrame, hard_exit: int = 1430, 
                             premium_scale: float = 1.0, regime: str = 'NORMAL', strat_name: str = '',
                             index_name: str = 'NIFTY', is_expiry: bool = False):
    dna = bt.get_index_strategy_dna(index_name, strat_name)
    
    # Standard high-performing TSL parameters
    tsl_activate = min(0.06, dna.tsl_activate)
    tsl_trail = min(0.04, dna.tsl_trail)
    target_pct = dna.target_pct
    sl_backstop = dna.sl_backstop
    
    tsl_trail = max(tsl_trail, 0.02)  # Floor to prevent noise stops
    
    is_reversal = 'REVERSAL' in strat_name or 'MEAN' in strat_name or 'BLOCK' in strat_name or 'CRUSH' in strat_name or 'CLIMAX' in strat_name
    is_trend = 'TREND' in strat_name or 'BREAK' in strat_name or 'BURST' in strat_name or 'DRIVE' in strat_name
    
    # Apply standard regime multipliers
    if bt.ENABLE_REGIME_SCALING or index_name == 'NIFTY':
        if 'TRENDING' in regime:
            target_pct *= 2.0
            tsl_activate *= 2.0
            tsl_trail *= 1.5
        elif regime == 'RANGE_BOUND':
            target_pct *= 0.6
            tsl_activate *= 0.6
            tsl_trail *= 0.6
    
    # Handle explosive gap overrides
    if regime == 'EXPLOSIVE_GAP':
        if is_reversal:
            tsl_activate *= 0.6
            tsl_trail *= 0.7
            target_pct *= 0.8
        elif is_trend:
            tsl_activate *= 1.3
            tsl_trail *= 1.2
            target_pct *= 1.5
            
    # Uncapped expiry trails for ZERO_HERO and GAMMA_BLAST on expiry days
    if bt.ENABLE_EXPIRY_UNCAP:
        if is_expiry and (strat_name in ['ZERO_HERO', 'GAMMA_BLAST']):
            target_pct = 999.0
            tsl_activate = 0.25
            tsl_trail = 0.15
    
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
            
        # 4. TSL
        if thi >= ep * (1 + tsl_activate):
            floor = thi * (1 - tsl_trail)
            if lo <= floor and floor > sl:
                xp = max(floor, sl); xr = 'TSL'; xt = ts; break
                
        # 5. V15 THETA-PRESERVATION CUT
        # If past 13:00 (1:00 PM) and trade is flat or negative, cut it to preserve premium
        if hhmm >= 1300 and close < ep:
            xp = close; xr = 'THETA_CUT'; xt = ts; break

    if xp is None:
        xp = float(remaining.iloc[-1]['close'])
        xr = 'TIME'
        xt = bt._get_ts(remaining.iloc[-1])
        
    return xp, xr, xt

# Patch the engine function in memory
bt.execute_tsl_idx = execute_tsl_idx_v15_theta

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
    print("RUNNING V15 THETA-PRESERVATION CUT BACKTEST")
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
