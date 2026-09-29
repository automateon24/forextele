import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

mt5.initialize()
now = datetime.now(timezone.utc)
from_date = now - timedelta(days=32)

rates_m1 = mt5.copy_rates_range("GOLD", mt5.TIMEFRAME_M1, from_date, now)
rates_h1 = mt5.copy_rates_range("GOLD", mt5.TIMEFRAME_H1, from_date, now)
mt5.shutdown()

df = pd.DataFrame(rates_m1)
df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
df.set_index('time_utc', inplace=True)
df.sort_index(inplace=True)

df_h1 = pd.DataFrame(rates_h1)
df_h1['time_utc'] = pd.to_datetime(df_h1['time'], unit='s', utc=True)
df_h1.set_index('time_utc', inplace=True)
df_h1.sort_index(inplace=True)
df_h1['ema50'] = df_h1['close'].ewm(span=50).mean()
df_h1['ema200'] = df_h1['close'].ewm(span=200).mean()

# Test Gold M1 1:1 with Trend Filter
dates = np.unique(df.index.date)
trades_unfiltered = []
trades_trend_filtered = []

spread = 0.40
multiplier = 100.0 * 0.02 # 0.02 lot

for d in dates:
    day_df = df[df.index.date == d]
    if len(day_df) < 20:
        continue
        
    asian_start = day_df.index[0]
    if asian_start.hour > 3:
        continue
        
    ref_candles = day_df[(day_df.index >= asian_start) & (day_df.index < asian_start + timedelta(minutes=1))]
    if len(ref_candles) < 1:
        continue
        
    ref_high = ref_candles['high'].max()
    ref_low = ref_candles['low'].min()
    ref_size = ref_high - ref_low
    if ref_size <= 0:
        continue
        
    # Get H1 trend at asian_start
    h1_slice = df_h1[df_h1.index <= asian_start]
    h1_trend = "NEUTRAL"
    if len(h1_slice) >= 10:
        last_h1 = h1_slice.iloc[-1]
        if last_h1['close'] > last_h1['ema50']:
            h1_trend = "BULLISH"
        elif last_h1['close'] < last_h1['ema50']:
            h1_trend = "BEARISH"
            
    post_candles = day_df[(day_df.index >= asian_start + timedelta(minutes=1)) & (day_df.index <= asian_start + timedelta(hours=10))]
    if len(post_candles) == 0:
        continue
        
    broken_out_bull = False
    broken_out_bear = False
    in_trade = False
    trade_dir = None
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    risk_dist = ref_size
    retest_tol = 0.20
    
    for t, row in post_candles.iterrows():
        c_high = row['high']
        c_low = row['low']
        
        if not in_trade:
            if not broken_out_bull and not broken_out_bear:
                if c_high > ref_high + retest_tol:
                    broken_out_bull = True
                elif c_low < ref_low - retest_tol:
                    broken_out_bear = True
            elif broken_out_bull:
                if c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol and c_low > ref_low:
                    in_trade = True
                    trade_dir = "BUY"
                    entry_price = ref_high + spread
                    sl_price = ref_low
                    tp_price = entry_price + (risk_dist * 1.0)
                    continue
                elif c_low <= ref_low:
                    break
            elif broken_out_bear:
                if c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol and c_high < ref_high:
                    in_trade = True
                    trade_dir = "SELL"
                    entry_price = ref_low - spread
                    sl_price = ref_high
                    tp_price = entry_price - (risk_dist * 1.0)
                    continue
                elif c_high >= ref_high:
                    break
        else:
            if trade_dir == "BUY":
                if c_low <= sl_price:
                    t_record = {"date": str(d), "dir": "BUY", "result": "LOSS", "pnl": -(entry_price - sl_price) * multiplier, "h1_trend": h1_trend}
                    trades_unfiltered.append(t_record)
                    if h1_trend == "BULLISH":
                        trades_trend_filtered.append(t_record)
                    break
                elif c_high >= tp_price:
                    t_record = {"date": str(d), "dir": "BUY", "result": "WIN", "pnl": (tp_price - entry_price) * multiplier, "h1_trend": h1_trend}
                    trades_unfiltered.append(t_record)
                    if h1_trend == "BULLISH":
                        trades_trend_filtered.append(t_record)
                    break
            elif trade_dir == "SELL":
                if c_high >= sl_price:
                    t_record = {"date": str(d), "dir": "SELL", "result": "LOSS", "pnl": -(sl_price - entry_price) * multiplier, "h1_trend": h1_trend}
                    trades_unfiltered.append(t_record)
                    if h1_trend == "BEARISH":
                        trades_trend_filtered.append(t_record)
                    break
                elif c_low <= tp_price:
                    t_record = {"date": str(d), "dir": "SELL", "result": "WIN", "pnl": (entry_price - tp_price) * multiplier, "h1_trend": h1_trend}
                    trades_unfiltered.append(t_record)
                    if h1_trend == "BEARISH":
                        trades_trend_filtered.append(t_record)
                    break

print("=== GOLD M1 1:1 R:R COMPARISON (30-DAY BACKTEST) ===")
# Unfiltered
n_un = len(trades_unfiltered)
w_un = len([t for t in trades_unfiltered if t['result'] == 'WIN'])
l_un = len([t for t in trades_unfiltered if t['result'] == 'LOSS'])
pnl_un = sum(t['pnl'] for t in trades_unfiltered)
gw_un = sum(t['pnl'] for t in trades_unfiltered if t['pnl'] > 0)
gl_un = abs(sum(t['pnl'] for t in trades_unfiltered if t['pnl'] < 0))
pf_un = gw_un / gl_un if gl_un > 0 else 99.0
print(f"UNFILTERED: {n_un} Trades | {w_un}W / {l_un}L ({w_un/n_un*100:.1f}%) | Net PnL: ${pnl_un:+.2f} | PF: {pf_un:.2f}")

# Trend Filtered
n_tf = len(trades_trend_filtered)
if n_tf > 0:
    w_tf = len([t for t in trades_trend_filtered if t['result'] == 'WIN'])
    l_tf = len([t for t in trades_trend_filtered if t['result'] == 'LOSS'])
    pnl_tf = sum(t['pnl'] for t in trades_trend_filtered)
    gw_tf = sum(t['pnl'] for t in trades_trend_filtered if t['pnl'] > 0)
    gl_tf = abs(sum(t['pnl'] for t in trades_trend_filtered if t['pnl'] < 0))
    pf_tf = gw_tf / gl_tf if gl_tf > 0 else 99.0
    print(f"H1 TREND FILTERED: {n_tf} Trades | {w_tf}W / {l_tf}L ({w_tf/n_tf*100:.1f}%) | Net PnL: ${pnl_tf:+.2f} | PF: {pf_tf:.2f}")
