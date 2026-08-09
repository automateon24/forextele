import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from backtest_high_res import build_indicators, generate_signals, load_tf, SYMBOLS, POINT, DIGITS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
DNA_PATH = BASE_DIR / "25stragy" / "ai_optimized_forex_dna.json"
OUT_CSV  = BASE_DIR / "backtest_highres_signals.csv"

def simulate_realistic_outcomes(signals, df_m1, point):
    if not signals: return []
    closes = df_m1['close'].values
    highs  = df_m1['high'].values
    lows   = df_m1['low'].values
    times  = df_m1.index.values.astype('datetime64[ns]')

    # Sort signals by time!
    signals = sorted(signals, key=lambda x: x['time'])
    
    active_locks = {} # key: strategy_name, value: close_time
    
    results = []
    for s in signals:
        strat_key = s['strategy']
        t_entry = np.datetime64(s['time'], 'ns')
        
        # Concurrency Lock (No Pyramiding)
        if strat_key in active_locks and t_entry <= active_locks[strat_key]:
            continue # Trade still open! Discard signal.
            
        entry   = s['entry']
        sl_pts  = s['sl_pts']
        tp_pts  = s['tp_pts']
        dr      = s['direction']
        
        is_buy  = (dr == "BUY")
        sl_price = entry - sl_pts*point if is_buy else entry + sl_pts*point
        tp_price = entry + tp_pts*point if is_buy else entry - tp_pts*point

        idx_m1 = int(np.searchsorted(times, t_entry)) + 1
        if idx_m1 >= len(closes): continue

        outcome  = "EXPIRED"
        pnl_pts  = 0.0
        close_time = times[idx_m1]
        
        spread_pts = 10.0 if "JPY" not in s['symbol'] else 0.010 

        for fwd in range(idx_m1, min(idx_m1+1440, len(closes))):
            h = highs[fwd]; l = lows[fwd]
            if is_buy:
                if l <= sl_price: 
                    outcome="LOSS"; pnl_pts = -sl_pts - spread_pts; close_time = times[fwd]; break
                if h >= tp_price: 
                    outcome="WIN";  pnl_pts = tp_pts - spread_pts; close_time = times[fwd]; break
            else:
                if h >= sl_price: 
                    outcome="LOSS"; pnl_pts = -sl_pts - spread_pts; close_time = times[fwd]; break
                if l <= tp_price: 
                    outcome="WIN";  pnl_pts = tp_pts - spread_pts; close_time = times[fwd]; break
        
        # Lock this strategy until the trade fully closes
        active_locks[strat_key] = close_time

        if outcome == "EXPIRED":
            pnl_pts = (closes[min(idx_m1+1439,len(closes)-1)] - entry)/point * (1 if is_buy else -1) - spread_pts

        results.append({**s, "outcome": outcome, "pnl_pts": round(pnl_pts,1)})
        
    return results

def main():
    with open(DNA_PATH) as f:
        dna_db = json.load(f).get("strategies", {})

    all_results = []
    
    # We only care about the last 10 days to prove the analysis!
    
    for symbol in SYMBOLS:
        log.info("=== %s ===", symbol)
        df_m15 = load_tf(symbol, "M15")
        df_m5  = load_tf(symbol, "M5")
        df_m1  = load_tf(symbol, "M1")
        df_h1  = load_tf(symbol, "H1")

        if df_m15 is None or df_m5 is None or df_m1 is None:
            continue
            
        # Filter explicitly for last 10 days for speed!
        cutoff = df_m1.index.max() - pd.Timedelta(days=10)
        df_m15 = df_m15[df_m15.index >= cutoff].copy()
        df_m5  = df_m5[df_m5.index >= cutoff].copy()
        df_m1  = df_m1[df_m1.index >= cutoff].copy()
        if df_h1 is not None: df_h1 = df_h1[df_h1.index >= cutoff - pd.Timedelta(days=5)].copy()

        df_m15, df_m5, df_h1_ended = build_indicators(df_m15, df_m5, df_h1)
        signals = generate_signals(symbol, df_m15, df_m5, df_h1_ended, dna_db)
        
        point = POINT.get(symbol, 0.00001)
        results = simulate_realistic_outcomes(signals, df_m1, point)
        log.info("  Generated %d realistic trades (Pyramiding Blocked)", len(results))
        all_results.extend(results)

    df = pd.DataFrame(all_results)
    out_10d = BASE_DIR / "backtest_10d_realistic.csv"
    df.to_csv(out_10d, index=False)
    log.info("Saved %d realistic trades -> %s", len(df), out_10d)
    
if __name__ == "__main__":
    main()
