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

SESSIONS = [
    {"name": "Asian Open", "code": "ASIA", "hour": 1, "minute": 0, "cap": 6.0, "rr_by_tf": {1: 1.5, 3: 2.0, 5: 2.0, 15: 2.0}},
    {"name": "Frankfurt Open", "code": "FRA", "hour": 6, "minute": 0, "cap": 9.0, "rr_by_tf": {1: 5.0, 3: 5.0, 5: 3.0, 15: 3.0}},
    {"name": "London Core", "code": "LON", "hour": 8, "minute": 0, "cap": 9.0, "rr_by_tf": {1: 3.0, 3: 5.0, 5: 3.0, 15: 3.0}},
    {"name": "NY Pre-Market", "code": "NYP", "hour": 12, "minute": 30, "cap": 11.0, "rr_by_tf": {1: 3.0, 3: 3.0, 5: 3.0, 15: 5.0}},
    {"name": "NY Cash Open", "code": "NYC", "hour": 13, "minute": 30, "cap": 12.0, "rr_by_tf": {1: 5.0, 3: 3.0, 5: 3.0, 15: 3.0}},
    {"name": "London Close", "code": "LNC", "hour": 15, "minute": 30, "cap": 9.0, "rr_by_tf": {1: 3.0, 3: 3.0, 5: 3.0, 15: 5.0}},
]

TIMEFRAMES = [1, 3, 5, 15]

def fetch_m1_data(days=30):
    if not mt5.initialize():
        print("Failed to initialize MT5")
        return None
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_date, now)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    return df

def resample_bars(df_m1, tf):
    if tf == 1:
        return df_m1
    rule = f"{tf}min"
    res = df_m1.resample(rule, label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    }).dropna()
    return res

def run_simulation(dfs_by_tf, unique_dates, mode="rejection_confirmed"):
    results = []
    
    for d in unique_dates:
        if d.weekday() >= 5:
            continue
            
        for sess in SESSIONS:
            s_hour = sess["hour"]
            s_min = sess["minute"]
            cap = sess["cap"]
            
            s_start = datetime(d.year, d.month, d.day, s_hour, s_min, tzinfo=timezone.utc)
            eod_time = datetime(d.year, d.month, d.day, 20, 50, tzinfo=timezone.utc)
            
            for tf in TIMEFRAMES:
                df_tf = dfs_by_tf[tf]
                target_rr = sess["rr_by_tf"].get(tf, 3.0)
                retest_tol = 0.50
                
                candle_end = s_start + timedelta(minutes=tf)
                open_candle_rows = df_tf[(df_tf.index >= s_start) & (df_tf.index < candle_end)]
                if len(open_candle_rows) == 0:
                    continue
                open_bar = open_candle_rows.iloc[0]
                ref_high = open_bar['high']
                ref_low = open_bar['low']
                ref_range = ref_high - ref_low
                ref_mid = (ref_high + ref_low) / 2.0
                
                if ref_range < 0.60 or ref_range > cap:
                    continue
                    
                post_bars = df_tf[(df_tf.index >= candle_end) & (df_tf.index <= eod_time)]
                if len(post_bars) == 0:
                    continue
                    
                broken_bull = False
                broken_bear = False
                in_trade = False
                limit_pending = False
                limit_dir = None
                limit_price = 0.0
                trade_dir = None
                entry_price = 0.0
                sl_price = 0.0
                tp_price = 0.0
                trade_pnl = 0.0
                trade_outcome = None
                
                for t, row in post_bars.iterrows():
                    c_open, c_high, c_low, c_close = row['open'], row['high'], row['low'], row['close']
                    
                    # 1. Manage active trade
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
                        
                    # 2. Breakout detection
                    if not broken_bull and not broken_bear:
                        if c_high > ref_high + retest_tol:
                            broken_bull = True
                            if mode == "blind_limit":
                                limit_pending = True
                                limit_dir = "BUY"
                                limit_price = ref_high + SPREAD
                                sl_ref = ref_low if tf == 1 else (max(ref_low, limit_price - 2.50) if tf == 3 else max(ref_mid, limit_price - 3.00))
                                risk = max(limit_price - sl_ref, 0.80)
                                sl_price = limit_price - risk
                                tp_price = limit_price + (risk * target_rr)
                        elif c_low < ref_low - retest_tol:
                            broken_bear = True
                            if mode == "blind_limit":
                                limit_pending = True
                                limit_dir = "SELL"
                                limit_price = ref_low - SPREAD
                                sl_ref = ref_high if tf == 1 else (min(ref_high, limit_price + 2.50) if tf == 3 else min(ref_mid, limit_price + 3.00))
                                risk = max(sl_ref - limit_price, 0.80)
                                sl_price = limit_price + risk
                                tp_price = limit_price - (risk * target_rr)
                        continue
                        
                    # 3. Retest handling
                    if mode == "rejection_confirmed":
                        if broken_bull:
                            is_touch = (c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol)
                            is_rejection = (c_close >= c_open) or (c_close > ref_high)
                            if is_touch and is_rejection:
                                in_trade = True
                                trade_dir = "BUY"
                                entry_price = ref_high + SPREAD
                                sl_ref = ref_low if tf == 1 else (max(ref_low, entry_price - 2.50) if tf == 3 else max(ref_mid, entry_price - 3.00))
                                risk = max(entry_price - sl_ref, 0.80)
                                sl_price = entry_price - risk
                                tp_price = entry_price + (risk * target_rr)
                                continue
                            elif c_low <= ref_low:
                                break  # Invalidated
                        elif broken_bear:
                            is_touch = (c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol)
                            is_rejection = (c_close <= c_open) or (c_close < ref_low)
                            if is_touch and is_rejection:
                                in_trade = True
                                trade_dir = "SELL"
                                entry_price = ref_low - SPREAD
                                sl_ref = ref_high if tf == 1 else (min(ref_high, entry_price + 2.50) if tf == 3 else min(ref_mid, entry_price + 3.00))
                                risk = max(sl_ref - entry_price, 0.80)
                                sl_price = entry_price + risk
                                tp_price = entry_price - (risk * target_rr)
                                continue
                            elif c_high >= ref_high:
                                break  # Invalidated
                                
                    elif mode == "blind_limit":
                        if limit_pending:
                            if limit_dir == "BUY":
                                if c_low <= limit_price:
                                    in_trade = True
                                    trade_dir = "BUY"
                                    entry_price = limit_price
                                    limit_pending = False
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
                                elif c_low <= ref_low:
                                    # Price dumped through the bottom of the range without filling properly or blew past
                                    pass
                            elif limit_dir == "SELL":
                                if c_high >= limit_price:
                                    in_trade = True
                                    trade_dir = "SELL"
                                    entry_price = limit_price
                                    limit_pending = False
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
                
                # If still in trade at EOD
                if in_trade:
                    last_c = post_bars.iloc[-1]['close']
                    trade_pnl = (last_c - entry_price) * LOT_MULTIPLIER if trade_dir == "BUY" else (entry_price - last_c) * LOT_MULTIPLIER
                    trade_outcome = "WIN" if trade_pnl > 0.20 else "LOSS"
                    
                if trade_outcome is not None:
                    results.append({
                        "date": str(d),
                        "session": sess["name"],
                        "tf": tf,
                        "dir": trade_dir,
                        "pnl": trade_pnl,
                        "outcome": trade_outcome
                    })
                    
    return pd.DataFrame(results)

def main():
    print("Fetching 30 days of Gold M1 data from MT5...")
    df_m1 = fetch_m1_data(30)
    if df_m1 is None:
        print("Error fetching data.")
        return
        
    print(f"Data fetched: {len(df_m1)} M1 bars from {df_m1.index[0]} to {df_m1.index[-1]}")
    
    print("Precomputing resampled timeframes (M3, M5, M15)...")
    dfs_by_tf = {
        1: df_m1,
        3: resample_bars(df_m1, 3),
        5: resample_bars(df_m1, 5),
        15: resample_bars(df_m1, 15)
    }
    unique_dates = sorted(list(set(df_m1.index.date)))
    print(f"Total trading days: {len(unique_dates)}")
    
    print("\n[1] Running Current Model: Confirmed Retest with Rejection Candle...")
    res_rejection = run_simulation(dfs_by_tf, unique_dates, mode="rejection_confirmed")
    
    print("[2] Running Proposed Model: Blind Limit Orders placed immediately on Breakout...")
    res_limit = run_simulation(dfs_by_tf, unique_dates, mode="blind_limit")
    
    def calc_stats(df, name):
        if len(df) == 0:
            return f"{name}: No trades."
        total_trades = len(df)
        wins = len(df[df['outcome'] == 'WIN'])
        losses = len(df[df['outcome'] == 'LOSS'])
        win_rate = (wins / total_trades) * 100
        net_profit = df['pnl'].sum()
        gross_profit = df[df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 99.0
        
        cum = df['pnl'].cumsum()
        peak = cum.cummax()
        dd = peak - cum
        max_dd = dd.max()
        
        return {
            "name": name,
            "trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "net_profit": net_profit,
            "profit_factor": profit_factor,
            "max_dd": max_dd
        }
        
    s_rej = calc_stats(res_rejection, "A: Confirmed Rejection (Current)")
    s_lim = calc_stats(res_limit, "B: Blind Limit Orders (Proposed)")
    
    print("\n" + "="*80)
    print("📊 HEAD-TO-HEAD COMPARISON: CONFIRMED REJECTION vs BLIND LIMIT ORDERS (30 DAYS)")
    print("="*80)
    print(f"{'METRIC':<25} | {'CONFIRMED REJECTION (Current)':<30} | {'BLIND LIMIT ORDERS (Proposed)':<30}")
    print("-" * 80)
    print(f"{'Total Trades':<25} | {str(s_rej['trades']):<30} | {str(s_lim['trades']):<30}")
    wl_rej = f"{s_rej['wins']}W / {s_rej['losses']}L"
    wl_lim = f"{s_lim['wins']}W / {s_lim['losses']}L"
    print(f"{'Wins / Losses':<25} | {wl_rej:<30} | {wl_lim:<30}")
    wr_rej = f"{s_rej['win_rate']:.1f}%"
    wr_lim = f"{s_lim['win_rate']:.1f}%"
    print(f"{'Win Rate':<25} | {wr_rej:<30} | {wr_lim:<30}")
    np_rej = f"+${s_rej['net_profit']:.2f}"
    np_lim = f"+${s_lim['net_profit']:.2f}"
    print(f"{'Net Profit ($)':<25} | {np_rej:<30} | {np_lim:<30}")
    pf_rej = f"{s_rej['profit_factor']:.2f}"
    pf_lim = f"{s_lim['profit_factor']:.2f}"
    print(f"{'Profit Factor':<25} | {pf_rej:<30} | {pf_lim:<30}")
    dd_rej = f"-${s_rej['max_dd']:.2f}"
    dd_lim = f"-${s_lim['max_dd']:.2f}"
    print(f"{'Max Drawdown ($)':<25} | {dd_rej:<30} | {dd_lim:<30}")
    print("="*80)

if __name__ == "__main__":
    main()
