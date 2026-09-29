"""
ALL-SESSION COMPREHENSIVE BACKTEST ON GOLD (XAUUSD)
===================================================
Initial Capital: $1,000.00 USD
Fixed Lot Size: 0.02 lots ($1 move in Gold = $2.00)
Timeframes: M1, M3, M5, M15
R:R Ratios: 1:1, 1:1.5, 1:2, 1:3, 1:5

Sessions Tested (UTC):
1. Asian Open (Tokyo): 00:00 UTC (03:00 MT5 Server)
2. Frankfurt Open (Europe Early): 06:00 UTC (09:00 MT5 Server)
3. London Core Open: 08:00 UTC (11:00 MT5 Server)
4. New York Pre-Market / US Macro: 12:30 UTC (15:30 MT5 Server)
5. New York Cash Open (Wall Street): 13:30 UTC (16:30 MT5 Server)
6. London Close / US PM: 15:30 UTC (18:30 MT5 Server)

Mandatory Rule:
All trades must close intraday before 20:50 UTC (23:50 MT5 Server),
prior to the daily 21:00-22:00 UTC market rollover pause.
"""
import sys
from pathlib import Path
BASE_DIR = Path(r"C:\anlyzeforex\forextele")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta, time
import json

def fetch_gold_m1_data(days=35):
    if not mt5.initialize():
        print("MT5 initialization failed")
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

def simulate_session_strategy(
    df,
    session_name,
    session_start_time, # (hour, minute) UTC
    session_max_duration_hours,
    tf_minutes,
    rr_ratio,
    model_type="optimized", # "baseline" or "optimized"
    initial_capital=1000.0,
    lot_size=0.02,
    spread=0.25
):
    """
    Simulates the Breakout & Retest strategy for a specific session.
    """
    trades = []
    equity_curve = [initial_capital]
    balance = initial_capital
    max_equity = initial_capital
    max_drawdown = 0.0
    
    LOT_MULTIPLIER = lot_size * 100.0 # 0.02 lot * 100 = $2.00 per point
    dates = np.unique(df.index.date)
    
    # EOD cutoff time: 20:50 UTC
    eod_cutoff_time = time(20, 50)
    
    retest_tol = 0.25
    
    for d in dates:
        day_df = df[df.index.date == d]
        if len(day_df) < 60:
            continue
            
        # Target session start datetime
        sh, sm = session_start_time
        s_start = datetime(d.year, d.month, d.day, sh, sm, tzinfo=timezone.utc)
        
        # Check if s_start is in day_df
        session_candles = day_df[day_df.index >= s_start]
        if len(session_candles) < tf_minutes + 15:
            continue
            
        # Ref candle: s_start to s_start + tf_minutes
        ref_candles = session_candles[(session_candles.index >= s_start) & (session_candles.index < s_start + timedelta(minutes=tf_minutes))]
        if len(ref_candles) < tf_minutes:
            continue
            
        ref_high = ref_candles['high'].max()
        ref_low = ref_candles['low'].min()
        ref_size = ref_high - ref_low
        ref_mid = (ref_high + ref_low) / 2.0
        
        # Volatility filter for optimized model
        if model_type == "optimized":
            # Cap maximum range based on timeframe to filter out exhausted news spikes
            max_caps = {1: 3.50, 3: 5.00, 5: 6.50, 15: 9.00}
            if ref_size < 0.35 or ref_size > max_caps.get(tf_minutes, 8.00):
                continue
        else:
            if ref_size < 0.20:
                continue
                
        # Session trading window: from end of opening candle up to session_max_duration or 20:50 UTC
        window_start = s_start + timedelta(minutes=tf_minutes)
        window_end = min(s_start + timedelta(hours=session_max_duration_hours), datetime(d.year, d.month, d.day, 20, 50, tzinfo=timezone.utc))
        
        post_candles = session_candles[(session_candles.index >= window_start) & (session_candles.index <= window_end)]
        if len(post_candles) == 0:
            continue
            
        broken_out_bull = False
        broken_out_bear = False
        in_trade = False
        trade_dir = None
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        entry_time = None
        is_be_activated = False
        
        for t, row in post_candles.iterrows():
            c_open = row['open']
            c_high = row['high']
            c_low = row['low']
            c_close = row['close']
            
            # EOD force close at 20:50 UTC
            if t.time() >= eod_cutoff_time and in_trade:
                exit_price = c_close
                pnl_pts = (exit_price - entry_price) if trade_dir == "BUY" else (entry_price - exit_price)
                pnl_usd = pnl_pts * LOT_MULTIPLIER
                balance += pnl_usd
                trades.append({
                    "date": str(d),
                    "dir": trade_dir,
                    "entry": entry_price,
                    "exit": exit_price,
                    "pnl_pts": pnl_pts,
                    "pnl_usd": pnl_usd,
                    "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS"),
                    "exit_reason": "EOD_CLOSE"
                })
                in_trade = False
                break
                
            if not in_trade:
                # ── BREAKOUT DETECTION ──
                if not broken_out_bull and not broken_out_bear:
                    if c_high > ref_high + retest_tol:
                        broken_out_bull = True
                    elif c_low < ref_low - retest_tol:
                        broken_out_bear = True
                        
                elif broken_out_bull:
                    # Retest check
                    if c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol:
                        rejection_ok = True
                        if model_type == "optimized":
                            # Buyer response: Green candle or close above level
                            rejection_ok = (c_close >= c_open) or (c_close > ref_high)
                            
                        if rejection_ok:
                            in_trade = True
                            trade_dir = "BUY"
                            entry_price = ref_high + spread
                            entry_time = t
                            
                            if model_type == "optimized":
                                if tf_minutes == 1:
                                    sl_price = ref_low
                                elif tf_minutes == 3:
                                    sl_price = max(ref_low, entry_price - 2.50)
                                else: # M5 and M15
                                    sl_price = max(ref_mid, entry_price - 3.00)
                            else:
                                sl_price = ref_low
                                
                            risk = entry_price - sl_price
                            if risk < 0.60:
                                risk = 0.80
                            tp_price = entry_price + (risk * rr_ratio)
                            is_be_activated = False
                            continue
                    elif c_low <= ref_low:
                        # Setup invalidated
                        break
                        
                elif broken_out_bear:
                    if c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol:
                        rejection_ok = True
                        if model_type == "optimized":
                            rejection_ok = (c_close <= c_open) or (c_close < ref_low)
                            
                        if rejection_ok:
                            in_trade = True
                            trade_dir = "SELL"
                            entry_price = ref_low - spread
                            entry_time = t
                            
                            if model_type == "optimized":
                                if tf_minutes == 1:
                                    sl_price = ref_high
                                elif tf_minutes == 3:
                                    sl_price = min(ref_high, entry_price + 2.50)
                                else:
                                    sl_price = min(ref_mid, entry_price + 3.00)
                            else:
                                sl_price = ref_high
                                
                            risk = sl_price - entry_price
                            if risk < 0.60:
                                risk = 0.80
                            tp_price = entry_price - (risk * rr_ratio)
                            is_be_activated = False
                            continue
                    elif c_high >= ref_high:
                        break
                        
            else:
                # ── IN TRADE ──
                risk = abs(entry_price - sl_price) if not is_be_activated else 1.50
                
                if trade_dir == "BUY":
                    # Break-even trail at +1.0 R in optimized model
                    if model_type == "optimized" and not is_be_activated and (c_high >= entry_price + risk):
                        sl_price = entry_price + 0.10
                        is_be_activated = True
                        
                    if c_low <= sl_price:
                        pnl_pts = sl_price - entry_price
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        trades.append({
                            "date": str(d),
                            "dir": trade_dir,
                            "entry": entry_price,
                            "exit": sl_price,
                            "pnl_pts": pnl_pts,
                            "pnl_usd": pnl_usd,
                            "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS"),
                            "exit_reason": "SL_HIT" if not is_be_activated else "BE_HIT"
                        })
                        in_trade = False
                        break
                    elif c_high >= tp_price:
                        pnl_pts = tp_price - entry_price
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        trades.append({
                            "date": str(d),
                            "dir": trade_dir,
                            "entry": entry_price,
                            "exit": tp_price,
                            "pnl_pts": pnl_pts,
                            "pnl_usd": pnl_usd,
                            "result": "WIN",
                            "exit_reason": "TP_HIT"
                        })
                        in_trade = False
                        break
                        
                elif trade_dir == "SELL":
                    if model_type == "optimized" and not is_be_activated and (c_low <= entry_price - risk):
                        sl_price = entry_price - 0.10
                        is_be_activated = True
                        
                    if c_high >= sl_price:
                        pnl_pts = entry_price - sl_price
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        trades.append({
                            "date": str(d),
                            "dir": trade_dir,
                            "entry": entry_price,
                            "exit": sl_price,
                            "pnl_pts": pnl_pts,
                            "pnl_usd": pnl_usd,
                            "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS"),
                            "exit_reason": "SL_HIT" if not is_be_activated else "BE_HIT"
                        })
                        in_trade = False
                        break
                    elif c_low <= tp_price:
                        pnl_pts = entry_price - tp_price
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        trades.append({
                            "date": str(d),
                            "dir": trade_dir,
                            "entry": entry_price,
                            "exit": tp_price,
                            "pnl_pts": pnl_pts,
                            "pnl_usd": pnl_usd,
                            "result": "WIN",
                            "exit_reason": "TP_HIT"
                        })
                        in_trade = False
                        break
                        
        # Track drawdown
        equity_curve.append(balance)
        if balance > max_equity:
            max_equity = balance
        dd = max_equity - balance
        if dd > max_drawdown:
            max_drawdown = dd
            
    # Calculate performance metrics
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "session": session_name,
            "tf": f"M{tf_minutes}",
            "rr": f"1:{rr_ratio}",
            "model": model_type,
            "trades": 0,
            "wins": 0,
            "be": 0,
            "losses": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "final_balance": initial_capital,
            "roi_pct": 0.0,
            "max_dd_usd": 0.0,
            "max_dd_pct": 0.0,
            "pf": 0.0
        }
        
    wins = sum(1 for tr in trades if tr['result'] == "WIN")
    be_count = sum(1 for tr in trades if tr['result'] == "BE")
    losses = sum(1 for tr in trades if tr['result'] == "LOSS")
    win_rate = (wins / total_trades) * 100.0
    
    net_pnl = balance - initial_capital
    roi_pct = (net_pnl / initial_capital) * 100.0
    max_dd_pct = (max_drawdown / max_equity) * 100.0 if max_equity > 0 else 0.0
    
    gp = sum(tr['pnl_usd'] for tr in trades if tr['pnl_usd'] > 0)
    gl = abs(sum(tr['pnl_usd'] for tr in trades if tr['pnl_usd'] < 0))
    pf = round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else 0.0)
    
    return {
        "session": session_name,
        "tf": f"M{tf_minutes}",
        "rr": f"1:{rr_ratio}",
        "model": model_type,
        "trades": total_trades,
        "wins": wins,
        "be": be_count,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "net_pnl": round(net_pnl, 2),
        "final_balance": round(balance, 2),
        "roi_pct": round(roi_pct, 2),
        "max_dd_usd": round(max_drawdown, 2),
        "max_dd_pct": round(max_dd_pct, 2),
        "pf": pf
    }

def main():
    print("Loading 35 days of M1 Gold data from MT5...")
    df = fetch_gold_m1_data(days=35)
    print(f"Total Gold M1 Bars: {len(df)}")
    
    sessions = [
        {"name": "Asian Open (Tokyo)", "time": (1, 0), "duration": 5},
        {"name": "Frankfurt Open (Europe)", "time": (6, 0), "duration": 5},
        {"name": "London Core Open", "time": (8, 0), "duration": 5},
        {"name": "NY Pre-Market / US Data", "time": (12, 30), "duration": 4},
        {"name": "New York Cash Open", "time": (13, 30), "duration": 4},
        {"name": "London Close / US PM", "time": (15, 30), "duration": 4}
    ]
    
    timeframes = [1, 3, 5, 15]
    rr_targets = [1.0, 1.5, 2.0, 3.0, 5.0]
    
    all_results = []
    
    print("\nRunning Multi-Session Simulation...")
    for s in sessions:
        for tf in timeframes:
            for rr in rr_targets:
                # Test optimized adaptive architecture
                res_opt = simulate_session_strategy(
                    df,
                    session_name=s["name"],
                    session_start_time=s["time"],
                    session_max_duration_hours=s["duration"],
                    tf_minutes=tf,
                    rr_ratio=rr,
                    model_type="optimized"
                )
                all_results.append(res_opt)
                
    out_file = BASE_DIR / "scratch" / "all_sessions_gold_results.json"
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)
        
    print(f"Complete! Results saved to {out_file}")
    
    # Identify top performers across all sessions
    sorted_res = sorted(all_results, key=lambda x: x['net_pnl'], reverse=True)
    
    print("\n" + "="*115)
    print("TOP 15 BEST PERFORMING SESSION & TIMEFRAME COMBINATIONS ON GOLD ($1,000 CAPITAL, 0.02 LOT)")
    print("="*115)
    header = f"{'Rank':<4} | {'Session':<24} | {'TF':<5} | {'R:R':<6} | {'Trades':<6} | {'WinRate%':<9} | {'Net PnL ($)':<14} | {'Final Equity':<14} | {'Max DD%':<8} | {'PF':<5}"
    print(header)
    print("-" * 115)
    for i, r in enumerate(sorted_res[:15]):
        print(f"{i+1:<4} | {r['session']:<24} | {r['tf']:<5} | {r['rr']:<6} | {r['trades']:<6} | {r['win_rate']:<9.1f} | ${r['net_pnl']:<+13.2f} | ${r['final_balance']:<13.2f} | {r['max_dd_pct']:<7.1f}% | {r['pf']:<5.2f}")

    # Summary by session
    print("\n" + "="*80)
    print("SESSION PROFITABILITY COMPARISON (AVERAGE ACROSS ALL TIMEFRAMES & TARGETS)")
    print("="*80)
    session_totals = {}
    for r in all_results:
        s_name = r['session']
        if s_name not in session_totals:
            session_totals[s_name] = {"net_pnl": 0.0, "trades": 0, "wins": 0, "count": 0}
        session_totals[s_name]["net_pnl"] += r['net_pnl']
        session_totals[s_name]["trades"] += r['trades']
        session_totals[s_name]["wins"] += r['wins']
        session_totals[s_name]["count"] += 1
        
    for s_name, data in sorted(session_totals.items(), key=lambda x: x[1]['net_pnl'], reverse=True):
        avg_pnl = data['net_pnl'] / data['count']
        wr = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0
        print(f"{s_name:<26} | Total Net: ${data['net_pnl']:<+10.2f} | Avg Setup Net: ${avg_pnl:<+7.2f} | Avg WR: {wr:.1f}%")

if __name__ == "__main__":
    main()
