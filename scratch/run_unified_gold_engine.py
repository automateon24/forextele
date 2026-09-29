"""
UNIFIED ARCHITECTURE: TESTING THE COMPLETE OPTIMIZED SYSTEM ACROSS M1, M3, M5, M15 ON GOLD
=============================================================================================
Rules:
1. Opening Candle Range at Asian Open (00:00 UTC / 03:00 Server).
2. Breakout: Price pushes beyond high/low.
3. Retest: Price returns to touch the breakout line.
4. Entry Confirmation: Rejection candle (Close back in trend direction, no falling knives).
5. Dynamic Risk Management:
   - For M1: SL = Opposite end of candle (since M1 range is small, avg $1.80).
   - For M3, M5, M15: SL = Structural Invalidation (Max $2.50 - $3.00, or Midpoint if range is tight).
6. Target: Check 1:1, 1:1.5, 1:2, 1:3, 1:5.
7. Break-Even Protection: Move SL to Entry once +1.0 R is reached.
"""
import sys
from pathlib import Path
BASE_DIR = Path(r"C:\anlyzeforex\forextele")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import json

def fetch_gold_data(days=35):
    if not mt5.initialize():
        return pd.DataFrame()
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=days)
    rates = mt5.copy_rates_range("GOLD", mt5.TIMEFRAME_M1, from_date, now)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time_utc', inplace=True)
    df.sort_index(inplace=True)
    return df

def simulate_unified(df, tf_minutes, rr_ratio, spread=0.25):
    trades = []
    dates = np.unique(df.index.date)
    
    for d in dates:
        day_df = df[df.index.date == d]
        if len(day_df) < tf_minutes + 30:
            continue
        asian_start = day_df.index[0]
        if asian_start.hour > 3:
            continue
            
        ref_candles = day_df[(day_df.index >= asian_start) & (day_df.index < asian_start + timedelta(minutes=tf_minutes))]
        if len(ref_candles) < tf_minutes:
            continue
            
        ref_high = ref_candles['high'].max()
        ref_low = ref_candles['low'].min()
        ref_size = ref_high - ref_low
        ref_mid = (ref_high + ref_low) / 2.0
        
        # Volatility check: Skip extreme gap days
        if ref_size < 0.30 or ref_size > 12.0:
            continue
            
        session_end = asian_start + timedelta(hours=6)
        post_candles = day_df[(day_df.index >= asian_start + timedelta(minutes=tf_minutes)) & (day_df.index <= session_end)]
        if len(post_candles) == 0:
            continue
            
        broken_out_bull = False
        broken_out_bear = False
        in_trade = False
        trade_dir = None
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        retest_tol = 0.25
        is_be = False
        
        for t, row in post_candles.iterrows():
            c_open = row['open']
            c_high = row['high']
            c_low = row['low']
            c_close = row['close']
            
            if not in_trade:
                if not broken_out_bull and not broken_out_bear:
                    if c_high > ref_high + retest_tol:
                        broken_out_bull = True
                    elif c_low < ref_low - retest_tol:
                        broken_out_bear = True
                        
                elif broken_out_bull:
                    if c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol:
                        # Rejection confirmation: buyer response
                        if (c_close >= c_open) or (c_close > ref_high):
                            in_trade = True
                            trade_dir = "BUY"
                            entry_price = ref_high + spread
                            
                            # Adaptive SL:
                            # For M1: use ref_low (tight)
                            # For M3/M5/M15: use min(ref_low, entry - $2.50) or midpoint
                            if tf_minutes == 1:
                                sl_price = ref_low
                            elif tf_minutes == 3:
                                sl_price = max(ref_low, entry_price - 2.20)
                            else: # M5 and M15
                                sl_price = max(ref_mid, entry_price - 2.50)
                                
                            risk = entry_price - sl_price
                            if risk < 0.80:
                                risk = 1.00
                            tp_price = entry_price + (risk * rr_ratio)
                            is_be = False
                            continue
                    elif c_low <= ref_low:
                        break
                        
                elif broken_out_bear:
                    if c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol:
                        if (c_close <= c_open) or (c_close < ref_low):
                            in_trade = True
                            trade_dir = "SELL"
                            entry_price = ref_low - spread
                            
                            if tf_minutes == 1:
                                sl_price = ref_high
                            elif tf_minutes == 3:
                                sl_price = min(ref_high, entry_price + 2.20)
                            else:
                                sl_price = min(ref_mid, entry_price + 2.50)
                                
                            risk = sl_price - entry_price
                            if risk < 0.80:
                                risk = 1.00
                            tp_price = entry_price - (risk * rr_ratio)
                            is_be = False
                            continue
                    elif c_high >= ref_high:
                        break
                        
            else:
                # ── TRADE IN PROGRESS ──
                risk = abs(entry_price - sl_price) if not is_be else 1.50
                
                if trade_dir == "BUY":
                    # Break-even trigger at +1.0 R
                    if not is_be and (c_high >= entry_price + risk):
                        sl_price = entry_price + 0.10
                        is_be = True
                        
                    if c_low <= sl_price:
                        pnl_pts = sl_price - entry_price
                        trades.append({
                            "result": "WIN" if pnl_pts > 0 else ("BE" if abs(pnl_pts) < 0.20 else "LOSS"),
                            "pnl_pts": pnl_pts
                        })
                        in_trade = False
                        break
                    elif c_high >= tp_price:
                        trades.append({
                            "result": "WIN",
                            "pnl_pts": tp_price - entry_price
                        })
                        in_trade = False
                        break
                        
                elif trade_dir == "SELL":
                    if not is_be and (c_low <= entry_price - risk):
                        sl_price = entry_price - 0.10
                        is_be = True
                        
                    if c_high >= sl_price:
                        pnl_pts = entry_price - sl_price
                        trades.append({
                            "result": "WIN" if pnl_pts > 0 else ("BE" if abs(pnl_pts) < 0.20 else "LOSS"),
                            "pnl_pts": pnl_pts
                        })
                        in_trade = False
                        break
                    elif c_low <= tp_price:
                        trades.append({
                            "result": "WIN",
                            "pnl_pts": entry_price - tp_price
                        })
                        in_trade = False
                        break
                        
    total = len(trades)
    if total == 0:
        return {"trades": 0, "wins": 0, "losses": 0, "be": 0, "win_rate": 0, "net_pnl": 0, "pf": 0}
        
    wins = sum(1 for tr in trades if tr['result'] == "WIN")
    be_count = sum(1 for tr in trades if tr['result'] == "BE")
    losses = sum(1 for tr in trades if tr['result'] == "LOSS")
    
    LOT_MULTIPLIER = 2.0 # 0.02 lot
    pnl_dollars = [tr['pnl_pts'] * LOT_MULTIPLIER for tr in trades]
    net_pnl = sum(pnl_dollars)
    gp = sum(p for p in pnl_dollars if p > 0)
    gl = abs(sum(p for p in pnl_dollars if p < 0))
    pf = round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else 0.0)
    wr = round((wins / total) * 100.0, 1)
    
    return {
        "trades": total,
        "wins": wins,
        "be": be_count,
        "losses": losses,
        "win_rate": wr,
        "net_pnl": round(net_pnl, 2),
        "pf": pf
    }

def main():
    df = fetch_gold_data(days=35)
    print(f"Total Gold M1 Bars: {len(df)}")
    
    timeframes = [1, 3, 5, 15]
    rr_ratios = [1.0, 1.5, 2.0, 3.0, 5.0]
    
    print("\n" + "="*95)
    print("UNIFIED ADAPTIVE ARCHITECTURE FOR GOLD ACROSS ALL TIMEFRAMES (0.02 LOT)")
    print("="*95)
    header = f"{'TF':<6} | {'R:R':<6} | {'Trades':<8} | {'Wins':<6} | {'BE':<5} | {'Loss':<6} | {'WinRate%':<10} | {'Net PnL (USD)':<16} | {'PF':<6}"
    print(header)
    print("-" * 95)
    
    summary_data = {}
    for tf in timeframes:
        summary_data[f"M{tf}"] = {}
        for rr in rr_ratios:
            res = simulate_unified(df, tf_minutes=tf, rr_ratio=rr)
            summary_data[f"M{tf}"][f"1:{rr}"] = res
            print(f"M{tf:<5} | 1:{rr:<4} | {res['trades']:<8} | {res['wins']:<6} | {res['be']:<5} | {res['losses']:<6} | {res['win_rate']:<10.1f} | +{res['net_pnl']:<14.2f} USD | {res['pf']:<6.2f}" if res['net_pnl'] >= 0 else f"M{tf:<5} | 1:{rr:<4} | {res['trades']:<8} | {res['wins']:<6} | {res['be']:<5} | {res['losses']:<6} | {res['win_rate']:<10.1f} | -{abs(res['net_pnl']):<14.2f} USD | {res['pf']:<6.2f}")
        print("-" * 95)
        
    out_path = BASE_DIR / "scratch" / "unified_gold_results.json"
    with open(out_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Results saved to {out_path}")

if __name__ == "__main__":
    main()
