"""
TEST ALL SOLUTIONS TO MAKE ALL TIMEFRAMES (M1, M3, M5, M15) PROFITABLE ON GOLD
=============================================================================
Hypotheses to test:
1. Baseline: Raw breakout + retest, SL at opposite extreme.
2. Solution 1 (Midpoint SL): SL at 50% equilibrium of the opening candle instead of opposite extreme.
3. Solution 2 (Close Confirmation): Candle close must be outside the high/low (not just a wick).
4. Solution 3 (Structure SL): SL is set to the swing extreme of the retest pullback (or fixed tight buffer $2.00).
5. Solution 4 (Trend Filter): Only take Buys when H1 Close > H1 EMA 50; Only Sells when H1 Close < H1 EMA 50.
6. Solution 5 (Rejection Confirmation): Retest candle must print a reversal / rejection candle (bullish close for buy, bearish close for sell).
7. Solution 6 (Golden Hybrid): Close confirmation + Midpoint/Structure SL + Rejection at Retest.
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
        print("MT5 initialization failed")
        return pd.DataFrame()
        
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=days)
    rates = mt5.copy_rates_range("GOLD", mt5.TIMEFRAME_M1, from_date, now)
    mt5.shutdown()
    
    if rates is None or len(rates) == 0:
        print("No rates fetched")
        return pd.DataFrame()
        
    df = pd.DataFrame(rates)
    df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time_utc', inplace=True)
    df.sort_index(inplace=True)
    return df

def run_simulation(df, tf_minutes, method="baseline", rr_ratio=1.0, spread=0.25):
    """
    Simulates a given method on Gold for a specific timeframe (M1, M3, M5, M15) and R:R ratio.
    """
    trades = []
    dates = np.unique(df.index.date)
    
    # Calculate H1 EMA 50 for trend filter
    df_h1 = df['close'].resample('1h').last().dropna()
    ema50_h1 = df_h1.ewm(span=50, adjust=False).mean()
    
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
        
        if ref_size <= 0.3: # Filter micro flat bars
            continue
            
        # Max window to scan (e.g. 6 hours after open)
        session_end = asian_start + timedelta(hours=6)
        post_candles = day_df[(day_df.index >= asian_start + timedelta(minutes=tf_minutes)) & (day_df.index <= session_end)]
        if len(post_candles) == 0:
            continue
            
        # Trend check at session open
        h1_time = asian_start.floor('h')
        trend_bullish = True
        trend_bearish = True
        if h1_time in ema50_h1.index:
            trend_bullish = day_df['close'].iloc[0] > ema50_h1.loc[h1_time]
            trend_bearish = day_df['close'].iloc[0] < ema50_h1.loc[h1_time]
            
        broken_out_bull = False
        broken_out_bear = False
        in_trade = False
        trade_dir = None
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        entry_time = None
        
        retest_tol = 0.25 # $0.25 tolerance on Gold
        
        for t, row in post_candles.iterrows():
            c_open = row['open']
            c_high = row['high']
            c_low = row['low']
            c_close = row['close']
            
            if not in_trade:
                # ── BREAKOUT DETECTION ──
                if not broken_out_bull and not broken_out_bear:
                    if method in ["close_confirm", "golden_hybrid", "trend_close"]:
                        # Requires candle CLOSE outside the range
                        if c_close > ref_high:
                            broken_out_bull = True
                        elif c_close < ref_low:
                            broken_out_bear = True
                    else:
                        # Standard wick breakout
                        if c_high > ref_high + retest_tol:
                            broken_out_bull = True
                        elif c_low < ref_low - retest_tol:
                            broken_out_bear = True
                            
                elif broken_out_bull:
                    # Filter: If trend filter active and not bullish trend, cancel
                    if "trend" in method and not trend_bullish:
                        break
                        
                    # Check for Retest of ref_high
                    is_touch = (c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol)
                    
                    if is_touch:
                        # Check rejection confirmation if required
                        rejection_ok = True
                        if "rejection" in method or "golden" in method:
                            rejection_ok = (c_close >= c_open) or (c_close > ref_high)
                            
                        if rejection_ok:
                            in_trade = True
                            trade_dir = "BUY"
                            entry_price = ref_high + spread
                            entry_time = t
                            
                            # Determine SL based on method
                            if "midpoint" in method or "golden" in method:
                                sl_price = ref_mid
                            elif "structure" in method:
                                sl_price = entry_price - max(1.80, ref_size * 0.4)
                            else: # Baseline
                                sl_price = ref_low
                                
                            risk = entry_price - sl_price
                            if risk <= 0:
                                risk = 1.0
                            tp_price = entry_price + (risk * rr_ratio)
                            continue
                            
                    elif c_low <= ref_low:
                        break
                        
                elif broken_out_bear:
                    if "trend" in method and not trend_bearish:
                        break
                        
                    is_touch = (c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol)
                    if is_touch:
                        rejection_ok = True
                        if "rejection" in method or "golden" in method:
                            rejection_ok = (c_close <= c_open) or (c_close < ref_low)
                            
                        if rejection_ok:
                            in_trade = True
                            trade_dir = "SELL"
                            entry_price = ref_low - spread
                            entry_time = t
                            
                            if "midpoint" in method or "golden" in method:
                                sl_price = ref_mid
                            elif "structure" in method:
                                sl_price = entry_price + max(1.80, ref_size * 0.4)
                            else: # Baseline
                                sl_price = ref_high
                                
                            risk = sl_price - entry_price
                            if risk <= 0:
                                risk = 1.0
                            tp_price = entry_price - (risk * rr_ratio)
                            continue
                            
                    elif c_high >= ref_high:
                        break
                        
            else:
                # ── IN TRADE: CHECK TP / SL ──
                if trade_dir == "BUY":
                    if c_low <= sl_price:
                        loss_pts = entry_price - sl_price
                        trades.append({
                            "result": "LOSS",
                            "pnl_pts": -loss_pts,
                            "entry": entry_price,
                            "exit": sl_price,
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break
                    elif c_high >= tp_price:
                        win_pts = tp_price - entry_price
                        trades.append({
                            "result": "WIN",
                            "pnl_pts": win_pts,
                            "entry": entry_price,
                            "exit": tp_price,
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break
                elif trade_dir == "SELL":
                    if c_high >= sl_price:
                        loss_pts = sl_price - entry_price
                        trades.append({
                            "result": "LOSS",
                            "pnl_pts": -loss_pts,
                            "entry": entry_price,
                            "exit": sl_price,
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break
                    elif c_low <= tp_price:
                        win_pts = entry_price - tp_price
                        trades.append({
                            "result": "WIN",
                            "pnl_pts": win_pts,
                            "entry": entry_price,
                            "exit": tp_price,
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break
                        
    total = len(trades)
    if total == 0:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "net_pnl": 0, "pf": 0}
        
    wins = sum(1 for tr in trades if tr['result'] == "WIN")
    losses = sum(1 for tr in trades if tr['result'] == "LOSS")
    win_rate = (wins / total) * 100.0
    
    # 0.02 lot = $2.00 per point
    LOT_MULTIPLIER = 2.0
    pnl_dollars = [tr['pnl_pts'] * LOT_MULTIPLIER for tr in trades]
    net_pnl = sum(pnl_dollars)
    gross_profit = sum(p for p in pnl_dollars if p > 0)
    gross_loss = abs(sum(p for p in pnl_dollars if p < 0))
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
    
    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "net_pnl": round(net_pnl, 2),
        "pf": pf
    }

def main():
    print("Fetching Gold data from MT5...")
    df = fetch_gold_data(days=35)
    print(f"Total bars loaded: {len(df)}")
    
    methods = [
        "baseline",
        "midpoint_sl",
        "close_confirm",
        "structure_sl",
        "rejection_confirm",
        "trend_close",
        "golden_hybrid"
    ]
    
    timeframes = [1, 3, 5, 15]
    rr_ratios = [1.0, 1.5, 2.0, 3.0]
    
    results = {}
    
    for tf in timeframes:
        results[f"M{tf}"] = {}
        for m in methods:
            results[f"M{tf}"][m] = {}
            for rr in rr_ratios:
                res = run_simulation(df, tf_minutes=tf, method=m, rr_ratio=rr)
                results[f"M{tf}"][m][f"1:{rr}"] = res
                
    out_file = BASE_DIR / "scratch" / "gold_all_tf_solutions_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nAll tests completed! Saved to {out_file}")
    
    print("\n" + "="*80)
    print("HIGHLIGHT COMPARISON TABLE: NET PNL ($ on 0.02 lot) & WIN RATE (%)")
    print("="*80)
    header = f"{'Method':<20} | {'M1 (1:1)':<16} | {'M3 (1:1)':<16} | {'M5 (1:1)':<16} | {'M15 (1:1)':<16}"
    print(header)
    print("-"*80)
    for m in methods:
        row_str = f"{m:<20} | "
        for tf in [1, 3, 5, 15]:
            d = results[f"M{tf}"][m]["1:1.0"]
            row_str += f"${d['net_pnl']:+6.2f} ({d['win_rate']:4.1f}%)  | "
        print(row_str)
        
    print("\n" + "="*80)
    print("HIGHLIGHT COMPARISON TABLE FOR 1:1.5 R:R")
    print("="*80)
    for m in methods:
        row_str = f"{m:<20} | "
        for tf in [1, 3, 5, 15]:
            d = results[f"M{tf}"][m]["1:1.5"]
            row_str += f"${d['net_pnl']:+6.2f} ({d['win_rate']:4.1f}%)  | "
        print(row_str)

if __name__ == "__main__":
    main()
