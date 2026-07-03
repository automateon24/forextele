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

# Define the new execute_tsl_idx with V15 Conviction/Holding Power upgrades
def execute_tsl_idx_v15(entry_bar: pd.Series, remaining: pd.DataFrame, hard_exit: int = 1430, 
                        premium_scale: float = 1.0, regime: str = 'NORMAL', strat_name: str = '',
                        index_name: str = 'NIFTY', is_expiry: bool = False):
    dna = bt.get_index_strategy_dna(index_name, strat_name)
    
    # Cap parameters for option safety to guard against theta decay
    # In V15, we allow more breathing room (relaxed caps)
    tsl_activate = min(0.15, dna.tsl_activate) # relaxed from 0.06
    tsl_trail = min(0.10, dna.tsl_trail)       # relaxed from 0.04
    target_pct = dna.target_pct
    sl_backstop = dna.sl_backstop
    
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
            
    if regime == 'EXPLOSIVE_GAP':
        if is_reversal:
            tsl_activate *= 0.6
            tsl_trail *= 0.7
            target_pct *= 0.8
        elif is_trend:
            tsl_activate *= 1.3
            tsl_trail *= 1.2
            target_pct *= 1.5
            
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

    # V15 ATR-based calculations on option premium
    closes = remaining['close'].astype(float).values
    highs = remaining['high'].astype(float).values if 'high' in remaining.columns else closes
    lows = remaining['low'].astype(float).values if 'low' in remaining.columns else closes
    
    tr = []
    for k in range(len(remaining)):
        prev_close = ep if k == 0 else closes[k-1]
        val1 = highs[k] - lows[k]
        val2 = abs(highs[k] - prev_close)
        val3 = abs(prev_close - lows[k])
        tr.append(max(val1, val2, val3))
        
    tr_series = pd.Series(tr)
    # 14-period ATR of option premium
    atr_series = tr_series.rolling(window=14, min_periods=1).mean().values
    
    # K-multiplier for Chandelier exit (defaults to 2.5)
    chandelier_k = 2.5
    
    for k, (idx_label, bar) in enumerate(remaining.iterrows()):
        ts   = bt._get_ts(bar)
        hhmm = ts.hour * 100 + ts.minute
        hi   = float(bar.get('high', bar['close']))
        lo   = float(bar.get('low',  bar['close']))
        thi  = max(thi, hi)
        
        # 1. TIME EXIT
        if hhmm >= hard_exit:
            xp = float(bar['close'])
            xr = 'TIME'
            xt = ts
            break
            
        # 2. HARD SL EXIT
        if lo <= sl:
            xp = sl
            xr = 'SL'
            xt = ts
            break
            
        # 3. TARGET EXIT
        if hi >= tgt:
            xp = tgt
            xr = 'TARGET'
            xt = ts
            break
            
        # 4. V15 CHANDELIER EXIT / ATR-BASED TRAILING
        # Calculate trailing stop level using Chandelier logic
        current_atr = max(atr_series[k], ep * 0.015) # floor at 1.5% of entry price
        
        # We start trailing once the peak goes above entry * (1 + tsl_activate)
        if thi >= ep * (1 + tsl_activate):
            # Trailing stop set K * ATR below the highest high reached
            chandelier_stop = thi - (chandelier_k * current_atr)
            
            # Ensure trailing stop only moves up and doesn't violate hard SL
            if chandelier_stop > sl:
                sl = chandelier_stop
                
            if lo <= sl:
                xp = sl
                xr = 'TSL'
                xt = ts
                break
                
        # 5. V15 STAGNANCY CUT (45-Minute Cut)
        # If trade is flat/negative after 45 mins, cut it to avoid theta decay
        if k >= 45:
            # If peak high hasn't reached a 5% gain and close is currently in loss/flat
            if thi < ep * 1.05 and float(bar['close']) <= ep:
                xp = float(bar['close'])
                xr = 'STAGNANT'
                xt = ts
                break

    if xp is None:
        xp = float(remaining.iloc[-1]['close'])
        xr = 'TIME'
        xt = bt._get_ts(remaining.iloc[-1])
        
    return xp, xr, xt

# Patch the engine function in memory
bt.execute_tsl_idx = execute_tsl_idx_v15

# Set up active strategies to our optimized 23 list
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
    print("RUNNING V15 CHANDELIER EXIT + STAGNANCY CUT BACKTEST")
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
