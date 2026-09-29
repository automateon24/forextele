"""
TEST THE VOLATILITY CONTRACTION + BREAK-EVEN PROTECTED STRATEGY FOR GOLD ACROSS ALL TIMEFRAMES
=============================================================================================
Rules:
1. Opening Candle Range Cap (Volatility Contraction):
   - M1: Range <= $3.00
   - M3: Range <= $4.00
   - M5: Range <= $5.50
   - M15: Range <= $7.50
   (Skip days where the opening candle is an overextended exhaustion bar)
2. Retest Confirmation:
   - Green close at retest for BUY, Red close at retest for SELL (or rejection wick)
3. Dynamic Trade Management:
   - Once price hits +1.0 R in profit, Stop Loss is trailed to BREAK-EVEN (Entry + spread).
4. Targets tested: 1:1, 1:1.5, 1:2, 1:3, 1:5
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

def simulate_volatility_filtered(df, tf_minutes, max_range_cap, rr_ratio, use_be=True, spread=0.25):
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
        
        # ── RULE 1: VOLATILITY CONTRACTION FILTER ──
        if ref_size < 0.40 or ref_size > max_range_cap:
            # Overextended candle -> SKIP
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
        entry_time = None
        is_be_activated = False
        retest_tol = 0.25
        
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
                    # Retest check
                    if c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol:
                        # Rejection confirmation: buyer response
                        if (c_close >= c_open) or (c_close > ref_high):
                            in_trade = True
                            trade_dir = "BUY"
                            entry_price = ref_high + spread
                            sl_price = ref_low # Base SL
                            risk = entry_price - sl_price
                            tp_price = entry_price + (risk * rr_ratio)
                            entry_time = t
                            is_be_activated = False
                            continue
                    elif c_low <= ref_low:
                        break
                        
                elif broken_out_bear:
                    if c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol:
                        if (c_close <= c_open) or (c_close < ref_low):
                            in_trade = True
                            trade_dir = "SELL"
                            entry_price = ref_low - spread
                            sl_price = ref_high
                            risk = sl_price - entry_price
                            tp_price = entry_price - (risk * rr_ratio)
                            entry_time = t
                            is_be_activated = False
                            continue
                    elif c_high >= ref_high:
                        break
                        
            else:
                # ── IN TRADE ──
                risk = abs(entry_price - sl_price) if not is_be_activated else (ref_size)
                
                if trade_dir == "BUY":
                    # Check Break-Even trigger at +1.0 R
                    if use_be and not is_be_activated and (c_high >= entry_price + risk):
                        sl_price = entry_price + 0.10 # Move to BE + buffer
                        is_be_activated = True
                        
                    if c_low <= sl_price:
                        pnl_pts = sl_price - entry_price
                        trades.append({
                            "result": "WIN" if pnl_pts > 0 else ("BE" if abs(pnl_pts) < 0.20 else "LOSS"),
                            "pnl_pts": pnl_pts,
                            "entry": entry_price,
                            "exit": sl_price
                        })
                        in_trade = False
                        break
                    elif c_high >= tp_price:
                        trades.append({
                            "result": "WIN",
                            "pnl_pts": tp_price - entry_price,
                            "entry": entry_price,
                            "exit": tp_price
                        })
                        in_trade = False
                        break
                        
                elif trade_dir == "SELL":
                    if use_be and not is_be_activated and (c_low <= entry_price - risk):
                        sl_price = entry_price - 0.10
                        is_be_activated = True
                        
                    if c_high >= sl_price:
                        pnl_pts = entry_price - sl_price
                        trades.append({
                            "result": "WIN" if pnl_pts > 0 else ("BE" if abs(pnl_pts) < 0.20 else "LOSS"),
                            "pnl_pts": pnl_pts,
                            "entry": entry_price,
                            "exit": sl_price
                        })
                        in_trade = False
                        break
                    elif c_low <= tp_price:
                        trades.append({
                            "result": "WIN",
                            "pnl_pts": entry_price - tp_price,
                            "entry": entry_price,
                            "exit": tp_price
                        })
                        in_trade = False
                        break
                        
    total = len(trades)
    if total == 0:
        return {"trades": 0, "wins": 0, "losses": 0, "be": 0, "win_rate": 0, "net_pnl": 0, "pf": 0}
        
    wins = sum(1 for tr in trades if tr['result'] == "WIN")
    be_trades = sum(1 for tr in trades if tr['result'] == "BE")
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
        "be": be_trades,
        "losses": losses,
        "win_rate": wr,
        "net_pnl": round(net_pnl, 2),
        "pf": pf
    }

def main():
    df = fetch_gold_data(days=35)
    print(f"Total Gold M1 Bars: {len(df)}")
    
    tf_configs = {
        "M1": {"cap": 3.0},
        "M3": {"cap": 4.5},
        "M5": {"cap": 5.5},
        "M15": {"cap": 7.5}
    }
    
    rr_targets = [1.0, 1.5, 2.0, 3.0, 5.0]
    
    print("\n" + "="*95)
    print("AI OPTIMIZED VOLATILITY CONTRACTION + REJECTION + BE RESULTS ON GOLD (0.02 LOT)")
    print("="*95)
    header = f"{'TF':<6} | {'R:R':<6} | {'Trades':<8} | {'Wins':<6} | {'BE':<5} | {'Loss':<6} | {'WinRate%':<10} | {'Net PnL ($)':<14} | {'PF':<6}"
    print(header)
    print("-" * 95)
    
    for tf_str, cfg in tf_configs.items():
        tf_num = int(tf_str.replace("M", ""))
        for rr in rr_targets:
            res = simulate_volatility_filtered(df, tf_minutes=tf_num, max_range_cap=cfg['cap'], rr_ratio=rr, use_be=True)
            print(f"{tf_str:<6} | 1:{rr:<4} | {res['trades']:<8} | {res['wins']:<6} | {res['be']:<5} | {res['losses']:<6} | {res['win_rate']:<10.1f} | ${res['net_pnl']:<+13.2f} | {res['pf']:<6.2f}")
        print("-" * 95)

if __name__ == "__main__":
    main()
