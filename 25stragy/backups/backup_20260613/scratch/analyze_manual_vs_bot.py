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

# We will run the backtest for the top 5 strategies with aggressive sizing
# Top 5 strategies: MOMENTUM_BURST, ATR_BREAK, MACD_DIVERGENCE, VWAP_BOUNCE, ZERO_HERO
aggressive_strategies = ["MOMENTUM_BURST", "ATR_BREAK", "MACD_DIVERGENCE", "VWAP_BOUNCE", "ZERO_HERO"]

def run_concentrated_backtest():
    print("\n" + "="*70)
    print("RUNNING PROFILE 1: CONCENTRATED HIGH-CONVICTION PORTFOLIO")
    print("  Capital per index: Rs. 250,000 | Max Lots Cap: 150")
    print("  Strategies: MOMENTUM_BURST, ATR_BREAK, MACD_DIVERGENCE, VWAP_BOUNCE, ZERO_HERO")
    print("="*70)
    
    # Modify parameters in memory
    bt.CAPITAL_PER_INDEX = 250000
    bt.MAX_LOTS_CAP = 150
    bt.ENABLE_REGIME_SCALING = True
    bt.EXPIRY_UNCAP_TIGHT = True
    
    # Only update ACTIVE_STRATEGIES_BY_INDEX
    for idx in bt.INDEX_CONFIGS:
        bt.ACTIVE_STRATEGIES_BY_INDEX[idx] = set(aggressive_strategies)

    datasets: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, bt.IndexConfig]] = {}
    total_days = 0
    for idx_name, cfg in bt.INDEX_CONFIGS.items():
        opt = bt.load_option_data_for_index(idx_name)
        if opt.empty:
            continue
        eod = bt.build_eod_from_option_data(opt)
        datasets[idx_name] = (opt, eod, cfg)
        total_days = max(total_days, opt['date'].nunique())

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
            except Exception as e:
                print(f"  [{idx_name}] ERROR: {e}")
                
    bt.report_multi(results, total_days)


def run_expiry_gamma_backtest():
    print("\n" + "="*70)
    print("RUNNING PROFILE 2: HYPER-AGGRESSIVE EXPIRY-ONLY GAMMA PORTFOLIO")
    print("  Capital per index: Rs. 500,000 | Max Lots Cap: 300")
    print("  Strategies: ZERO_HERO, GAMMA_BLAST (Expiry Days Only)")
    print("="*70)
    
    # Modify parameters in memory
    bt.CAPITAL_PER_INDEX = 500000
    bt.MAX_LOTS_CAP = 300
    bt.ENABLE_REGIME_SCALING = True
    bt.EXPIRY_UNCAP_TIGHT = True
    
    expiry_strategies = ["ZERO_HERO", "GAMMA_BLAST"]
    
    # Only update ACTIVE_STRATEGIES_BY_INDEX
    for idx in bt.INDEX_CONFIGS:
        bt.ACTIVE_STRATEGIES_BY_INDEX[idx] = set(expiry_strategies)

    datasets: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, bt.IndexConfig]] = {}
    total_days = 0
    for idx_name, cfg in bt.INDEX_CONFIGS.items():
        opt = bt.load_option_data_for_index(idx_name)
        if opt.empty:
            continue
        eod = bt.build_eod_from_option_data(opt)
        datasets[idx_name] = (opt, eod, cfg)
        total_days = max(total_days, opt['date'].nunique())

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
            except Exception as e:
                print(f"  [{idx_name}] ERROR: {e}")
                
    bt.report_multi(results, total_days)


if __name__ == '__main__':
    run_concentrated_backtest()
    run_expiry_gamma_backtest()
