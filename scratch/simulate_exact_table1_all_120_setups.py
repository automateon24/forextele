"""
EXACT SIMULATION OF ALL 120 SETUPS FROM TABLE 1 SIMULTANEOUSLY
=============================================================
Initial Capital: $1,000.00 USD
Lot Size: 0.02 lots per trade
Every single session (Asian, Frankfurt, London, NY Pre-Mkt, NY Cash, London Close)
Every timeframe (M1, M3, M5, M15)
Every R:R ratio (1:1.0, 1:1.5, 1:2.0, 1:3.0, 1:5.0)
Total Active Simultaneous Strategy Engines: 120 Engines!

Questions to verify:
1. Does it achieve the full +$1,969.64 USD profit (~200% ROI)?
2. What is the peak simultaneous open trades at any given minute?
3. What is the peak margin used?
4. What is the peak real floating drawdown?
5. Can the $1,000 capital support all 120 setups?
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

def simulate_all_120_setups(df, initial_capital=1000.0, lot_size=0.02, spread=0.25):
    LOT_MULTIPLIER = lot_size * 100.0 # $2.00 per point
    MARGIN_PER_TRADE = 8.60 # USD on 1:1000 leverage
    
    sessions = [
        {"name": "Asian Open", "time": (1, 0), "duration": 5},
        {"name": "Frankfurt Open", "time": (6, 0), "duration": 4},
        {"name": "London Core", "time": (8, 0), "duration": 4},
        {"name": "NY Pre-Mkt", "time": (12, 30), "duration": 3},
        {"name": "NY Cash", "time": (13, 30), "duration": 3},
        {"name": "London Close", "time": (15, 30), "duration": 3}
    ]
    
    timeframes = [1, 3, 5, 15]
    rr_ratios = [1.0, 1.5, 2.0, 3.0, 5.0]
    
    dates = np.unique(df.index.date)
    eod_cutoff = time(20, 50)
    retest_tol = 0.25
    
    balance = initial_capital
    peak_equity = initial_capital
    max_floating_dd_usd = 0.0
    max_floating_dd_pct = 0.0
    min_equity_reached = initial_capital
    peak_concurrent_trades = 0
    peak_margin_used = 0.0
    
    all_closed_trades = []
    
    for d in dates:
        day_df = df[df.index.date == d]
        if len(day_df) < 60:
            continue
            
        active_trades = []
        day_setups = []
        
        # Build all 120 setups for this day
        for s in sessions:
            sh, sm = s["time"]
            s_start = datetime(d.year, d.month, d.day, sh, sm, tzinfo=timezone.utc)
            session_candles = day_df[day_df.index >= s_start]
            
            for tf in timeframes:
                if len(session_candles) < tf + 10:
                    continue
                ref_candles = session_candles[(session_candles.index >= s_start) & (session_candles.index < s_start + timedelta(minutes=tf))]
                if len(ref_candles) < tf:
                    continue
                ref_h = ref_candles['high'].max()
                ref_l = ref_candles['low'].min()
                ref_sz = ref_h - ref_l
                ref_m = (ref_h + ref_l) / 2.0
                
                caps = {1: 3.50, 3: 5.00, 5: 6.50, 15: 9.00}
                if ref_sz < 0.35 or ref_sz > caps.get(tf, 8.00):
                    continue
                    
                w_start = s_start + timedelta(minutes=tf)
                w_end = min(s_start + timedelta(hours=s["duration"]), datetime(d.year, d.month, d.day, 20, 50, tzinfo=timezone.utc))
                
                # Each R:R is an independent trading setup!
                for rr in rr_ratios:
                    day_setups.append({
                        "session_name": s["name"],
                        "tf": tf,
                        "rr": rr,
                        "ref_h": ref_h,
                        "ref_l": ref_l,
                        "ref_m": ref_m,
                        "w_start": w_start,
                        "w_end": w_end,
                        "broken_bull": False,
                        "broken_bear": False,
                        "triggered": False
                    })
                    
        # Minute-by-minute order management
        for t, row in day_df.iterrows():
            c_open = row['open']
            c_high = row['high']
            c_low = row['low']
            c_close = row['close']
            
            remaining_trades = []
            for tr in active_trades:
                # EOD Force Close
                if t.time() >= eod_cutoff:
                    exit_p = c_close
                    pnl_pts = (exit_p - tr["entry"]) if tr["dir"] == "BUY" else (tr["entry"] - exit_p)
                    pnl_usd = pnl_pts * LOT_MULTIPLIER
                    balance += pnl_usd
                    all_closed_trades.append({
                        "pnl_usd": pnl_usd,
                        "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                    })
                    continue
                    
                closed = False
                if tr["dir"] == "BUY":
                    if not tr["is_be"] and (c_high >= tr["entry"] + tr["risk"]):
                        tr["sl"] = tr["entry"] + 0.10
                        tr["is_be"] = True
                        
                    if c_low <= tr["sl"]:
                        pnl_pts = tr["sl"] - tr["entry"]
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                        })
                        closed = True
                    elif c_high >= tr["tp"]:
                        pnl_pts = tr["tp"] - tr["entry"]
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "result": "WIN"
                        })
                        closed = True
                        
                elif tr["dir"] == "SELL":
                    if not tr["is_be"] and (c_low <= tr["entry"] - tr["risk"]):
                        tr["sl"] = tr["entry"] - 0.10
                        tr["is_be"] = True
                        
                    if c_high >= tr["sl"]:
                        pnl_pts = tr["entry"] - tr["sl"]
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                        })
                        closed = True
                    elif c_low <= tr["tp"]:
                        pnl_pts = tr["entry"] - tr["tp"]
                        pnl_usd = pnl_pts * LOT_MULTIPLIER
                        balance += pnl_usd
                        all_closed_trades.append({
                            "pnl_usd": pnl_usd,
                            "result": "WIN"
                        })
                        closed = True
                        
                if not closed:
                    remaining_trades.append(tr)
                    
            active_trades = remaining_trades
            
            # Check for new entries
            if t.time() < eod_cutoff:
                for st in day_setups:
                    if st["triggered"] or t < st["w_start"] or t > st["w_end"]:
                        continue
                    ref_h = st["ref_h"]
                    ref_l = st["ref_l"]
                    ref_m = st["ref_m"]
                    tf = st["tf"]
                    
                    if not st["broken_bull"] and not st["broken_bear"]:
                        if c_high > ref_h + retest_tol:
                            st["broken_bull"] = True
                        elif c_low < ref_l - retest_tol:
                            st["broken_bear"] = True
                    elif st["broken_bull"]:
                        if c_low <= ref_h + retest_tol and c_high >= ref_h - retest_tol:
                            if (c_close >= c_open) or (c_close > ref_h):
                                entry_p = ref_h + spread
                                sl_p = ref_l if tf == 1 else (max(ref_l, entry_p - 2.50) if tf == 3 else max(ref_m, entry_p - 3.00))
                                risk = entry_p - sl_p
                                if risk < 0.60:
                                    risk = 0.80
                                tp_p = entry_p + (risk * st["rr"])
                                active_trades.append({
                                    "session": st["session_name"],
                                    "tf": tf,
                                    "rr": st["rr"],
                                    "dir": "BUY",
                                    "entry": entry_p,
                                    "sl": sl_p,
                                    "tp": tp_p,
                                    "risk": risk,
                                    "is_be": False
                                })
                                st["triggered"] = True
                        elif c_low <= ref_l:
                            st["triggered"] = True
                    elif st["broken_bear"]:
                        if c_high >= ref_l - retest_tol and c_low <= ref_l + retest_tol:
                            if (c_close <= c_open) or (c_close < ref_l):
                                entry_p = ref_l - spread
                                sl_p = ref_h if tf == 1 else (min(ref_h, entry_p + 2.50) if tf == 3 else min(ref_m, entry_p + 3.00))
                                risk = sl_p - entry_p
                                if risk < 0.60:
                                    risk = 0.80
                                tp_p = entry_p - (risk * st["rr"])
                                active_trades.append({
                                    "session": st["session_name"],
                                    "tf": tf,
                                    "rr": st["rr"],
                                    "dir": "SELL",
                                    "entry": entry_p,
                                    "sl": sl_p,
                                    "tp": tp_p,
                                    "risk": risk,
                                    "is_be": False
                                })
                                st["triggered"] = True
                        elif c_high >= ref_h:
                            st["triggered"] = True
                            
            # Minute stats
            num_open = len(active_trades)
            if num_open > peak_concurrent_trades:
                peak_concurrent_trades = num_open
            cur_margin = num_open * MARGIN_PER_TRADE
            if cur_margin > peak_margin_used:
                peak_margin_used = cur_margin
                
            float_pnl = 0.0
            for tr in active_trades:
                pts = (c_close - tr["entry"]) if tr["dir"] == "BUY" else (tr["entry"] - c_close)
                float_pnl += pts * LOT_MULTIPLIER
                
            cur_equity = balance + float_pnl
            if cur_equity > peak_equity:
                peak_equity = cur_equity
            if cur_equity < min_equity_reached:
                min_equity_reached = cur_equity
                
            eq_dd = peak_equity - cur_equity
            eq_dd_pct = (eq_dd / peak_equity * 100.0) if peak_equity > 0 else 0.0
            if eq_dd > max_floating_dd_usd:
                max_floating_dd_usd = eq_dd
            if eq_dd_pct > max_floating_dd_pct:
                max_floating_dd_pct = eq_dd_pct
                
    total_trades = len(all_closed_trades)
    wins = sum(1 for tr in all_closed_trades if tr['result'] == "WIN")
    be_cnt = sum(1 for tr in all_closed_trades if tr['result'] == "BE")
    losses = sum(1 for tr in all_closed_trades if tr['result'] == "LOSS")
    wr = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
    net_profit = balance - initial_capital
    roi = (net_profit / initial_capital) * 100.0
    gp = sum(tr['pnl_usd'] for tr in all_closed_trades if tr['pnl_usd'] > 0)
    gl = abs(sum(tr['pnl_usd'] for tr in all_closed_trades if tr['pnl_usd'] < 0))
    pf = round(gp / gl, 2) if gl > 0 else 99.0
    lowest_margin_lvl = (min_equity_reached / peak_margin_used * 100.0) if peak_margin_used > 0 else 9999.0
    
    return {
        "initial_capital": initial_capital,
        "final_balance": round(balance, 2),
        "net_profit": round(net_profit, 2),
        "roi_pct": round(roi, 1),
        "total_trades": total_trades,
        "wins": wins,
        "be": be_cnt,
        "losses": losses,
        "win_rate": round(wr, 1),
        "profit_factor": pf,
        "peak_concurrent_trades": peak_concurrent_trades,
        "peak_margin_used": round(peak_margin_used, 2),
        "min_equity_reached": round(min_equity_reached, 2),
        "max_floating_dd_usd": round(max_floating_dd_usd, 2),
        "max_floating_dd_pct": round(max_floating_dd_pct, 2),
        "lowest_margin_level_pct": round(lowest_margin_lvl, 1)
    }

def main():
    print("Loading 35 days of M1 Gold data from MT5...")
    df = fetch_gold_m1_data(days=35)
    print(f"Total Gold M1 Bars: {len(df)}")
    
    print("\nSimulating EXACT TABLE 1: All 120 setups running concurrently...")
    r = simulate_all_120_setups(df)
    
    print("\n" + "="*85)
    print("EXACT TABLE 1 ALL-IN 120-SETUP SIMULATION REPORT ($1,000 CAPITAL, 0.02 LOTS)")
    print("="*85)
    print(f"Starting Capital           : ${r['initial_capital']:.2f} USD")
    print(f"Final Ending Balance       : ${r['final_balance']:.2f} USD")
    print(f"Net Total Profit           : +${r['net_profit']:.2f} USD")
    print(f"Return on Investment (ROI) : +{r['roi_pct']:.1f}% in 30 Days")
    print(f"Total Trades Taken         : {r['total_trades']}")
    print(f"Wins / BE / Losses         : {r['wins']} Wins | {r['be']} BE | {r['losses']} Losses")
    print(f"Win Rate                   : {r['win_rate']:.1f}%")
    print(f"Profit Factor              : {r['profit_factor']:.2f}")
    print(f"Peak Concurrent Open Trades: {r['peak_concurrent_trades']} simultaneous open positions")
    print(f"Peak Margin Utilized       : ${r['peak_margin_used']:.2f} USD (Only {r['peak_margin_used']/1000*100:.1f}% of capital!)")
    print(f"Lowest Equity Reached      : ${r['min_equity_reached']:.2f} USD")
    print(f"Max Floating Drawdown ($)  : -${r['max_floating_dd_usd']:.2f} USD")
    print(f"Max Floating Drawdown (%)  : {r['max_floating_dd_pct']:.2f}%")
    print(f"Lowest Margin Level (%)    : {r['lowest_margin_level_pct']:.1f}% (XM Stop-out is 20%)")
    print("="*85)

if __name__ == "__main__":
    main()
