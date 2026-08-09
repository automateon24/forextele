import re
with open('backtest_high_res.py', 'r') as f:
    code = f.read()

new_sim = '''def simulate_outcomes(signals, df_m1, point):
    if not signals: return []
    import numpy as np
    closes = df_m1['close'].values
    highs  = df_m1['high'].values
    lows   = df_m1['low'].values
    times  = df_m1.index.values.astype('datetime64[ns]')

    signals = sorted(signals, key=lambda x: x['time'])
    active_locks = {}
    
    results = []
    for s in signals:
        strat_key = s['strategy']
        t_entry = np.datetime64(s['time'], 'ns')
        
        if strat_key in active_locks and t_entry <= active_locks[strat_key]:
            continue 
            
        entry   = s['entry']
        sl_pts  = s['sl_pts']
        tp_pts  = s['tp_pts']
        dr      = s['direction']
        atr_pts = s['atr'] / point
        
        is_buy  = (dr == "BUY")
        idx_m1 = int(np.searchsorted(times, t_entry)) + 1
        if idx_m1 >= len(closes): continue

        outcome  = "EXPIRED"
        close_time = times[idx_m1]
        spread_pts = 10.0 if "JPY" not in s['symbol'] else 0.010 

        is_grid = strat_key in ("SCALPING", "ASIAN_RANGE_SCALP", "ZERO_HERO", "SWAP_ARBITRAGE")
        
        if is_grid:
            max_levels = 3
            grid_step = max(atr_pts * 1.5, 50.0)
            level = 0
            total_lots = 1.0
            avg_entry = entry
            
            grid_sl_pts = sl_pts * 3.0
            grid_tp_pts = tp_pts
            
            pnl_pts = 0.0
            for fwd in range(idx_m1, min(idx_m1+1440, len(closes))):
                h = highs[fwd]; l = lows[fwd]
                
                if is_buy:
                    current_tp = avg_entry + grid_tp_pts * point
                    current_sl = avg_entry - grid_sl_pts * point
                    
                    if h >= current_tp:
                        outcome = "WIN"
                        pnl_pts = (grid_tp_pts * total_lots) - (spread_pts * total_lots)
                        close_time = times[fwd]
                        break
                        
                    if l <= current_sl:
                        outcome = "LOSS"
                        pnl_pts = -(grid_sl_pts * total_lots) - (spread_pts * total_lots)
                        close_time = times[fwd]
                        break
                        
                    if level < max_levels and l <= avg_entry - (grid_step * point):
                        level += 1
                        new_lots = 2 ** level
                        avg_entry = ((avg_entry * total_lots) + (l * new_lots)) / (total_lots + new_lots)
                        total_lots += new_lots
                else:
                    current_tp = avg_entry - grid_tp_pts * point
                    current_sl = avg_entry + grid_sl_pts * point
                    
                    if l <= current_tp:
                        outcome = "WIN"
                        pnl_pts = (grid_tp_pts * total_lots) - (spread_pts * total_lots)
                        close_time = times[fwd]
                        break
                        
                    if h >= current_sl:
                        outcome = "LOSS"
                        pnl_pts = -(grid_sl_pts * total_lots) - (spread_pts * total_lots)
                        close_time = times[fwd]
                        break
                        
                    if level < max_levels and h >= avg_entry + (grid_step * point):
                        level += 1
                        new_lots = 2 ** level
                        avg_entry = ((avg_entry * total_lots) + (h * new_lots)) / (total_lots + new_lots)
                        total_lots += new_lots
            
            if outcome == "EXPIRED":
                final_close = closes[min(idx_m1+1439,len(closes)-1)]
                pnl_pts = ((final_close - avg_entry) / point * (1 if is_buy else -1)) * total_lots - (spread_pts * total_lots)
                
            active_locks[strat_key] = close_time
            results.append({**s, "outcome": outcome, "pnl_pts": round(pnl_pts,1)})
            
        else:
            sl_price = entry - sl_pts*point if is_buy else entry + sl_pts*point
            tp_price = entry + tp_pts*point if is_buy else entry - tp_pts*point
            pnl_pts = 0.0
            
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
            
            active_locks[strat_key] = close_time
            if outcome == "EXPIRED":
                pnl_pts = (closes[min(idx_m1+1439,len(closes)-1)] - entry)/point * (1 if is_buy else -1) - spread_pts
            results.append({**s, "outcome": outcome, "pnl_pts": round(pnl_pts,1)})
            
    return results'''

code = re.sub(r'def simulate_outcomes\(signals, df_m1, point\):.*?return results', new_sim, code, flags=re.DOTALL)

# Restore standard R:R
code = re.sub(r'# Hardcode Risk/Reward to 1:3.*?tp_atr = 3.0', 'sl_atr = max(dna.get("sl", 1.5), 0.5)\n        tp_atr = max(dna.get("tgt", 1.5), 0.5)', code, flags=re.DOTALL)

# Relax Anti-Bleed
code = code.replace('if tp_pts < expected_spread * 5:', 'if tp_pts < expected_spread * 2:')

with open('backtest_high_res.py', 'w') as f:
    f.write(code)
print("Updated successfully")
