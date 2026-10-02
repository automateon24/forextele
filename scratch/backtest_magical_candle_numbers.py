import os
import sys
from datetime import datetime, timezone, timedelta, time as dtime
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

SYMBOL = "GOLD"
LOT_SIZE = 0.02
LOT_MULTIPLIER = 2.0  # 1.0 point on 0.02 lot = $2.00 USD
SPREAD = 0.20

def fetch_m1_data(days=35):
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return None
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, now)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time_utc', inplace=True)
    df.sort_index(inplace=True)
    return df

def run_magical_candles_backtest(df_m1, counting_mode="session_bars", rr_ratio=2.0):
    """
    counting_mode:
    - 'session_bars': Candle #1 is the first traded bar after daily rollover (01:00 UTC).
      Candle #72 is index 71. Candle #144 is index 143.
    - 'clock_minutes': 72 minutes after 00:00 UTC (= 01:12 UTC).
      144 minutes after 00:00 UTC (= 02:24 UTC).
    """
    results = []
    
    unique_dates = sorted(list(set(df_m1.index.date)))
    
    # We test candle #72 and candle #144
    target_candles = [72, 144]
    
    for d in unique_dates:
        if d.weekday() >= 5:
            continue
            
        # Get day's bars from 00:00 UTC to 20:50 UTC
        day_start = datetime(d.year, d.month, d.day, 0, 0, tzinfo=timezone.utc)
        day_end = datetime(d.year, d.month, d.day, 20, 50, tzinfo=timezone.utc)
        
        day_bars = df_m1[(df_m1.index >= day_start) & (df_m1.index <= day_end)]
        if len(day_bars) < 150:
            continue
            
        for c_num in target_candles:
            ref_bar = None
            ref_time = None
            
            if counting_mode == "session_bars":
                # Market opens at ~01:00 UTC. The c_num-th bar of this day
                # Filter bars after 00:50 UTC
                session_bars = day_bars[day_bars.index >= datetime(d.year, d.month, d.day, 0, 50, tzinfo=timezone.utc)]
                if len(session_bars) < c_num:
                    continue
                ref_bar = session_bars.iloc[c_num - 1]
                ref_time = session_bars.index[c_num - 1]
            elif counting_mode == "clock_minutes":
                # c_num minutes after 00:00 UTC
                target_dt = day_start + timedelta(minutes=c_num)
                match_bars = day_bars[day_bars.index == target_dt]
                if len(match_bars) == 0:
                    continue
                ref_bar = match_bars.iloc[0]
                ref_time = target_dt
                
            ref_high = ref_bar['high']
            ref_low = ref_bar['low']
            ref_range = ref_high - ref_low
            ref_mid = (ref_high + ref_low) / 2.0
            
            # Basic sanity filter: candle must have at least 0.20 range and not be an absurd 15-dollar freak wick
            if ref_range < 0.20 or ref_range > 8.0:
                continue
                
            retest_tol = 0.25
            
            # Post bars starting AFTER the reference candle until 20:50 UTC
            post_bars = day_bars[day_bars.index > ref_time]
            if len(post_bars) == 0:
                continue
                
            broken_bull = False
            broken_bear = False
            in_trade = False
            trade_dir = None
            entry_price = 0.0
            sl_price = 0.0
            tp_price = 0.0
            trade_pnl = 0.0
            trade_outcome = None
            
            for t, row in post_bars.iterrows():
                c_open, c_high, c_low, c_close = row['open'], row['high'], row['low'], row['close']
                
                # Active trade management
                if in_trade:
                    if trade_dir == "BUY":
                        if c_low <= sl_price:
                            trade_pnl = (sl_price - entry_price) * LOT_MULTIPLIER
                            trade_outcome = "LOSS"
                            in_trade = False
                            break
                        elif c_high >= tp_price:
                            trade_pnl = (tp_price - entry_price) * LOT_MULTIPLIER
                            trade_outcome = "WIN"
                            in_trade = False
                            break
                    elif trade_dir == "SELL":
                        if c_high >= sl_price:
                            trade_pnl = (entry_price - sl_price) * LOT_MULTIPLIER
                            trade_outcome = "LOSS"
                            in_trade = False
                            break
                        elif c_low <= tp_price:
                            trade_pnl = (entry_price - tp_price) * LOT_MULTIPLIER
                            trade_outcome = "WIN"
                            in_trade = False
                            break
                    continue
                    
                # Breakout detection
                if not broken_bull and not broken_bear:
                    if c_high > ref_high + retest_tol:
                        broken_bull = True
                    elif c_low < ref_low - retest_tol:
                        broken_bear = True
                    continue
                    
                # Retest & Rejection Confirmation
                if broken_bull and not broken_bear:
                    is_touch = (c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol)
                    is_rejection = (c_close >= c_open) or (c_close > ref_high)
                    if is_touch and is_rejection:
                        in_trade = True
                        trade_dir = "BUY"
                        entry_price = ref_high + SPREAD
                        sl_price = ref_low
                        risk = max(entry_price - sl_price, 0.60)
                        tp_price = entry_price + (risk * rr_ratio)
                        continue
                    elif c_low <= ref_low:
                        break  # Invalidation
                        
                elif broken_bear and not broken_bull:
                    is_touch = (c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol)
                    is_rejection = (c_close <= c_open) or (c_close < ref_low)
                    if is_touch and is_rejection:
                        in_trade = True
                        trade_dir = "SELL"
                        entry_price = ref_low - SPREAD
                        sl_price = ref_high
                        risk = max(sl_price - entry_price, 0.60)
                        tp_price = entry_price - (risk * rr_ratio)
                        continue
                    elif c_high >= ref_high:
                        break  # Invalidation
            
            # EOD close if still open
            if in_trade:
                last_c = post_bars.iloc[-1]['close']
                trade_pnl = (last_c - entry_price) * LOT_MULTIPLIER if trade_dir == "BUY" else (entry_price - last_c) * LOT_MULTIPLIER
                trade_outcome = "WIN" if trade_pnl > 0.20 else "LOSS"
                
            if trade_outcome is not None:
                results.append({
                    "date": str(d),
                    "candle_num": c_num,
                    "ref_time": str(ref_time),
                    "dir": trade_dir,
                    "entry": entry_price,
                    "pnl": trade_pnl,
                    "outcome": trade_outcome
                })
                
    return pd.DataFrame(results)

def analyze_df(df, label):
    if len(df) == 0:
        print(f"\n{label}: No trades taken.")
        return
    trades = len(df)
    wins = len(df[df['outcome'] == 'WIN'])
    losses = len(df[df['outcome'] == 'LOSS'])
    wr = (wins / trades) * 100
    pnl = df['pnl'].sum()
    gp = df[df['pnl'] > 0]['pnl'].sum()
    gl = abs(df[df['pnl'] < 0]['pnl'].sum())
    pf = (gp / gl) if gl > 0 else 99.0
    
    cum = df['pnl'].cumsum()
    peak = cum.cummax()
    max_dd = (peak - cum).max()
    
    print(f"\n{'='*70}")
    print(f"📊 {label}")
    print(f"{'='*70}")
    print(f"  Total Trades   : {trades}")
    print(f"  Win / Loss     : {wins}W / {losses}L ({wr:.1f}% Win Rate)")
    print(f"  Net Profit ($) : {'+$' if pnl>=0 else '-$'}{abs(pnl):.2f} USD (on fixed 0.02 lot)")
    print(f"  Profit Factor  : {pf:.2f}")
    print(f"  Max Drawdown   : -${max_dd:.2f}")
    
    # Breakdown by candle 72 vs 144
    c72 = df[df['candle_num'] == 72]
    c144 = df[df['candle_num'] == 144]
    
    def sub_stat(sub, name):
        if len(sub) == 0: return f"    - {name}: 0 trades"
        sw = len(sub[sub['outcome'] == 'WIN'])
        sl = len(sub[sub['outcome'] == 'LOSS'])
        spnl = sub['pnl'].sum()
        return f"    - {name:<12}: {len(sub)} trades | {sw}W / {sl}L ({sw/len(sub)*100:.1f}%) | Net: {'+$' if spnl>=0 else '-$'}{abs(spnl):.2f}"
        
    print(f"  Breakdown by Candle:")
    print(sub_stat(c72, "Candle #72"))
    print(sub_stat(c144, "Candle #144"))

def main():
    print("Fetching 30 days of Gold M1 data from MT5...")
    df_m1 = fetch_m1_data(35)
    if df_m1 is None:
        print("Failed to get data.")
        return
        
    print(f"Data range: {df_m1.index[0]} to {df_m1.index[-1]} ({len(df_m1)} bars)")
    
    # Test 1: Session Bars (Candle #72 = ~02:12 UTC, Candle #144 = ~03:24 UTC)
    for rr in [1.5, 2.0, 3.0, 5.0]:
        df_res = run_magical_candles_backtest(df_m1, counting_mode="session_bars", rr_ratio=rr)
        analyze_df(df_res, f"MODE 1: Session Bars (From 01:00 UTC Open) | R:R 1:{rr:.1f}")
        
    # Test 2: Clock Minutes (From 00:00 UTC Midnight)
    for rr in [1.5, 2.0, 3.0]:
        df_res2 = run_magical_candles_backtest(df_m1, counting_mode="clock_minutes", rr_ratio=rr)
        analyze_df(df_res2, f"MODE 2: Clock Minutes (From 00:00 UTC Midnight) | R:R 1:{rr:.1f}")

if __name__ == "__main__":
    main()
