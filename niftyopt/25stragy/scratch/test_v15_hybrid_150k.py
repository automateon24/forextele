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

# We will run the standard run_index function from BACKTEST_V8_AI, which implements the full Hybrid architecture.
# We will configure it dynamically in-memory.

def run_test_hybrid_150k():
    print("\n" + "="*70)
    print("RUNNING FULL HYBRID ARCHITECTURE (23 Strategies)")
    print("  Capital per index: Rs. 150,000 | Max Lots Cap: 60")
    print("="*70)
    
    # Configure in memory
    bt.CAPITAL_PER_INDEX = 150000
    bt.MAX_LOTS_CAP = 60
    
    # Load active strategies exactly from config.json
    with open(r'C:\25stragy\config.json', 'r') as f:
        config_db = json.load(f)
        
    for idx_name, idx_cfg in config_db["index_profiles"].items():
        bt.ACTIVE_STRATEGIES_BY_INDEX[idx_name] = set(idx_cfg.get("active_strategies", []))

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
    run_test_hybrid_150k()
