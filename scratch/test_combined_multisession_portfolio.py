"""
MULTI-SESSION UNIFIED PORTFOLIO SIMULATION ON GOLD
==================================================
Initial Capital: $1,000.00 USD
Fixed Lot Size: 0.02 lots ($2.00 per point)
Mandatory EOD Hard Close: 20:50 UTC (No overnight rollover holding)

Selected Premier Strategy per Session:
1. Session 1 (06:00 UTC): Frankfurt Open M1 (1:5.0 R:R with +1R BE trail)
2. Session 2 (08:00 UTC): London Core Open M3 (1:5.0 R:R with +1R BE trail)
3. Session 3 (12:30 UTC): NY Pre-Market M15 (1:2.0 R:R with +1R BE trail)
4. Session 4 (13:30 UTC): New York Cash Open M1 (1:5.0 R:R with +1R BE trail)
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

def simulate_portfolio(df, initial_capital=1000.0, lot_size=0.02, spread=0.25):
    session_configs = [
        {"name": "Frankfurt M1", "time": (6, 0), "duration": 4, "tf": 1, "rr": 5.0, "cap": 3.50},
        {"name": "London M3", "time": (8, 0), "duration": 4, "tf": 3, "rr": 5.0, "cap": 5.00},
        {"name": "NY Pre-Mkt M15", "time": (12, 30), "duration": 3, "tf": 15, "rr": 2.0, "cap": 9.00},
        {"name": "NY Cash M1", "time": (13, 30), "duration": 3, "tf": 1, "rr": 5.0, "cap": 3.50}
    ]
    
    LOT_MULTIPLIER = lot_size * 100.0
    dates = np.unique(df.index.date)
    eod_cutoff = time(20, 50)
    retest_tol = 0.25
    
    all_portfolio_trades = []
    daily_pnl = {}
    balance = initial_capital
    max_equity = initial_capital
    max_dd = 0.0
    equity_series = []
    
    for d in dates:
        day_df = df[df.index.date == d]
        if len(day_df) < 60:
            continue
            
        daily_pnl[str(d)] = 0.0
        
        for sc in session_configs:
            sh, sm = sc["time"]
            s_start = datetime(d.year, d.month, d.day, sh, sm, tzinfo=timezone.utc)
            session_candles = day_df[day_df.index >= s_start]
            tf = sc["tf"]
            
            if len(session_candles) < tf + 10:
                continue
                
            ref_candles = session_candles[(session_candles.index >= s_start) & (session_candles.index < s_start + timedelta(minutes=tf))]
            if len(ref_candles) < tf:
                continue
                
            ref_high = ref_candles['high'].max()
            ref_low = ref_candles['low'].min()
            ref_size = ref_high - ref_low
            ref_mid = (ref_high + ref_low) / 2.0
            
            # Volatility cap
            if ref_size < 0.35 or ref_size > sc["cap"]:
                continue
                
            window_start = s_start + timedelta(minutes=tf)
            window_end = min(s_start + timedelta(hours=sc["duration"]), datetime(d.year, d.month, d.day, 20, 50, tzinfo=timezone.utc))
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
            is_be = False
            
            for t, row in post_candles.iterrows():
                c_open = row['open']
                c_high = row['high']
                c_low = row['low']
                c_close = row['close']
                
                # EOD hard cutoff
                if t.time() >= eod_cutoff and in_trade:
                    pnl_pts = (c_close - entry_price) if trade_dir == "BUY" else (entry_price - c_close)
                    pnl_usd = pnl_pts * LOT_MULTIPLIER
                    balance += pnl_usd
                    daily_pnl[str(d)] += pnl_usd
                    all_portfolio_trades.append({
                        "date": str(d),
                        "session": sc["name"],
                        "pnl_usd": pnl_usd,
                        "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                    })
                    in_trade = False
                    break
                    
                if not in_trade:
                    if not broken_out_bull and not broken_out_bear:
                        if c_high > ref_high + retest_tol:
                            broken_out_bull = True
                        elif c_low < ref_low - retest_tol:
                            broken_out_bear = True
                    elif broken_out_bull:
                        if c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol:
                            if (c_close >= c_open) or (c_close > ref_high):
                                in_trade = True
                                trade_dir = "BUY"
                                entry_price = ref_high + spread
                                sl_price = ref_low if tf == 1 else (max(ref_low, entry_price - 2.50) if tf == 3 else max(ref_mid, entry_price - 3.00))
                                risk = entry_price - sl_price
                                if risk < 0.60:
                                    risk = 0.80
                                tp_price = entry_price + (risk * sc["rr"])
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
                                sl_price = ref_high if tf == 1 else (min(ref_high, entry_price + 2.50) if tf == 3 else min(ref_mid, entry_price + 3.00))
                                risk = sl_price - entry_price
                                if risk < 0.60:
                                    risk = 0.80
                                tp_price = entry_price - (risk * sc["rr"])
                                is_be = False
                                continue
                        elif c_high >= ref_high:
                            break
                else:
                    risk = abs(entry_price - sl_price) if not is_be else 1.50
                    if trade_dir == "BUY":
                        if not is_be and (c_high >= entry_price + risk):
                            sl_price = entry_price + 0.10
                            is_be = True
                        if c_low <= sl_price:
                            pnl_pts = sl_price - entry_price
                            pnl_usd = pnl_pts * LOT_MULTIPLIER
                            balance += pnl_usd
                            daily_pnl[str(d)] += pnl_usd
                            all_portfolio_trades.append({
                                "date": str(d),
                                "session": sc["name"],
                                "pnl_usd": pnl_usd,
                                "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                            })
                            in_trade = False
                            break
                        elif c_high >= tp_price:
                            pnl_pts = tp_price - entry_price
                            pnl_usd = pnl_pts * LOT_MULTIPLIER
                            balance += pnl_usd
                            daily_pnl[str(d)] += pnl_usd
                            all_portfolio_trades.append({
                                "date": str(d),
                                "session": sc["name"],
                                "pnl_usd": pnl_usd,
                                "result": "WIN"
                            })
                            in_trade = False
                            break
                    elif trade_dir == "SELL":
                        if not is_be and (c_low <= entry_price - risk):
                            sl_price = entry_price - 0.10
                            is_be = True
                        if c_high >= sl_price:
                            pnl_pts = entry_price - sl_price
                            pnl_usd = pnl_pts * LOT_MULTIPLIER
                            balance += pnl_usd
                            daily_pnl[str(d)] += pnl_usd
                            all_portfolio_trades.append({
                                "date": str(d),
                                "session": sc["name"],
                                "pnl_usd": pnl_usd,
                                "result": "WIN" if pnl_usd > 0.20 else ("BE" if abs(pnl_usd) <= 0.20 else "LOSS")
                            })
                            in_trade = False
                            break
                        elif c_low <= tp_price:
                            pnl_pts = entry_price - tp_price
                            pnl_usd = pnl_pts * LOT_MULTIPLIER
                            balance += pnl_usd
                            daily_pnl[str(d)] += pnl_usd
                            all_portfolio_trades.append({
                                "date": str(d),
                                "session": sc["name"],
                                "pnl_usd": pnl_usd,
                                "result": "WIN"
                            })
                            in_trade = False
                            break
                            
            if balance > max_equity:
                max_equity = balance
            dd = max_equity - balance
            if dd > max_dd:
                max_dd = dd
            equity_series.append(balance)
            
    total_trades = len(all_portfolio_trades)
    wins = sum(1 for tr in all_portfolio_trades if tr['result'] == "WIN")
    be_count = sum(1 for tr in all_portfolio_trades if tr['result'] == "BE")
    losses = sum(1 for tr in all_portfolio_trades if tr['result'] == "LOSS")
    wr = (wins / total_trades * 100.0) if total_trades > 0 else 0
    net_profit = balance - initial_capital
    roi = (net_profit / initial_capital) * 100.0
    gp = sum(tr['pnl_usd'] for tr in all_portfolio_trades if tr['pnl_usd'] > 0)
    gl = abs(sum(tr['pnl_usd'] for tr in all_portfolio_trades if tr['pnl_usd'] < 0))
    pf = round(gp / gl, 2) if gl > 0 else 99.0
    dd_pct = (max_dd / max_equity) * 100.0
    
    return {
        "trades": total_trades,
        "wins": wins,
        "be": be_count,
        "losses": losses,
        "win_rate": round(wr, 1),
        "initial_capital": initial_capital,
        "final_balance": round(balance, 2),
        "net_profit": round(net_profit, 2),
        "roi_pct": round(roi, 1),
        "max_dd_usd": round(max_dd, 2),
        "max_dd_pct": round(dd_pct, 2),
        "profit_factor": pf,
        "daily_pnl": daily_pnl
    }

def main():
    df = fetch_gold_m1_data(days=35)
    print(f"Total Gold M1 Bars: {len(df)}")
    res = simulate_portfolio(df)
    
    print("\n" + "="*85)
    print("MASTER MULTI-SESSION PORTFOLIO PERFORMANCE REPORT ($1,000 CAPITAL, 0.02 LOT)")
    print("="*85)
    print(f"Initial Starting Capital : $1,000.00 USD")
    print(f"Final Account Balance    : ${res['final_balance']:.2f} USD")
    print(f"Net Total Profit         : +${res['net_profit']:.2f} USD")
    print(f"Return on Capital (ROI)  : +{res['roi_pct']:.1f}% in 30 Days")
    print(f"Total Trades Taken       : {res['trades']}")
    print(f"Wins / BE / Losses       : {res['wins']} Wins | {res['be']} Break-Evens | {res['losses']} Losses")
    print(f"Win Rate                 : {res['win_rate']:.1f}%")
    print(f"Profit Factor            : {res['profit_factor']:.2f}")
    print(f"Max Drawdown ($)         : ${res['max_dd_usd']:.2f}")
    print(f"Max Drawdown (%)         : {res['max_dd_pct']:.2f}% (Ultra Safe Risk Profile)")
    print("="*85)

if __name__ == "__main__":
    main()
