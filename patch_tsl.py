import re

with open('backtest_high_res.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_sim = '''        else:
            sl_price = entry - sl_pts*point if is_buy else entry + sl_pts*point
            # Remove hard TP or set to massive 10 ATR to let TSL work
            tp_price = entry + (atr_pts*10.0)*point if is_buy else entry - (atr_pts*10.0)*point
            pnl_pts = 0.0
            
            # TSL Settings
            trail_activation_pts = sl_pts * 1.5 # Activate TSL after 1.5 R profit
            trail_distance_pts = sl_pts * 1.0 # Trail by 1 R
            
            max_fav_price = entry
            min_fav_price = entry
            
            for fwd in range(idx_m1, min(idx_m1+2880, len(closes))):
                h = highs[fwd]; l = lows[fwd]
                
                if is_buy:
                    # Update Max Price
                    if h > max_fav_price:
                        max_fav_price = h
                        if max_fav_price - entry > trail_activation_pts * point:
                            new_sl = max_fav_price - trail_distance_pts * point
                            if new_sl > sl_price:
                                sl_price = new_sl
                                
                    if l <= sl_price: 
                        outcome = "WIN" if sl_price > entry else "LOSS"
                        pnl_pts = (sl_price - entry)/point - spread_pts
                        close_time = times[fwd]; break
                    if h >= tp_price: 
                        outcome="WIN";  pnl_pts = (tp_price - entry)/point - spread_pts; close_time = times[fwd]; break
                else:
                    if l < min_fav_price:
                        min_fav_price = l
                        if entry - min_fav_price > trail_activation_pts * point:
                            new_sl = min_fav_price + trail_distance_pts * point
                            if new_sl < sl_price:
                                sl_price = new_sl
                                
                    if h >= sl_price: 
                        outcome = "WIN" if sl_price < entry else "LOSS"
                        pnl_pts = (entry - sl_price)/point - spread_pts
                        close_time = times[fwd]; break
                    if l <= tp_price: 
                        outcome="WIN";  pnl_pts = (entry - tp_price)/point - spread_pts; close_time = times[fwd]; break
            
            active_locks[strat_key] = close_time
            if outcome == "EXPIRED":
                pnl_pts = (closes[min(idx_m1+2879,len(closes)-1)] - entry)/point * (1 if is_buy else -1) - spread_pts
            results.append({**s, "outcome": outcome, "pnl_pts": round(pnl_pts,1)})'''

code = re.sub(r'        else:\n            sl_price = entry.*?results\.append\(\{\*\*s, "outcome": outcome, "pnl_pts": round\(pnl_pts,1\)\}\)', new_sim, code, flags=re.DOTALL)

with open('backtest_high_res.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched TSL in backtester')
