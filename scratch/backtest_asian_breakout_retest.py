"""
ASIAN OPEN 1, 3, 5, 15-MINUTE BREAKOUT & RETEST BACKTESTING ENGINE
==================================================================
Assets: GOLD (XAUUSD) & BTCUSD
Timeframes: 1m, 3m, 5m, 15m
Target R:R: 1:1, 1:2, 1:3, 1:4, 1:5
Data: 1 Month of Historical M1 Bars from MT5
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
from collections import defaultdict
import json

def fetch_data(symbol: str, days: int = 31) -> pd.DataFrame:
    if not mt5.initialize():
        print("MT5 initialization failed")
        return pd.DataFrame()
        
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, from_date, now)
    if rates is None or len(rates) == 0:
        print(f"No rates for {symbol}")
        return pd.DataFrame()
        
    df = pd.DataFrame(rates)
    df['time_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time_utc', inplace=True)
    df.sort_index(inplace=True)
    return df

def simulate_strategy(df: pd.DataFrame, symbol: str, tf_minutes: int, rr_ratio: float, spread_points: float = 0.0):
    """
    Simulates the Asian Open Breakout & Retest on M1 data.
    - Asian Open = 00:00 UTC
    - Initial Candle = 00:00 to 00:00+tf_minutes
    - Once broken out, enters on Retest of High (for BUY) or Low (for SELL)
    - SL = opposite end of initial candle
    - TP = Entry +/- rr_ratio * Risk
    """
    trades = []
    
    # Group by calendar date (UTC)
    dates = np.unique(df.index.date)
    
    for d in dates:
        day_df = df[df.index.date == d]
        if len(day_df) < tf_minutes + 10:
            continue
            
        # The session open is the first trading candle of the day
        # For BTCUSD this is 00:00 UTC; for GOLD it is 01:00 UTC (Tokyo Asian Market Open)
        asian_start = day_df.index[0]
        if asian_start.hour > 3:
            continue
            
        ref_candles = day_df[(day_df.index >= asian_start) & (day_df.index < asian_start + timedelta(minutes=tf_minutes))]
        
        if len(ref_candles) < tf_minutes:
            continue
            
        ref_high = ref_candles['high'].max()
        ref_low = ref_candles['low'].min()
        ref_size = ref_high - ref_low
        
        # Filter out flat candles / holidays
        if ref_size <= 0:
            continue
            
        # Subsequent candles to scan for breakout and retest (during Asian session)
        session_end = asian_start + timedelta(hours=10)
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
        risk_dist = ref_size
        
        # Retest tolerance (0.1% of candle or 0.15 pts on Gold, $10 on BTC)
        retest_tol = 0.20 if symbol == "GOLD" else 15.0
        
        for t, row in post_candles.iterrows():
            c_high = row['high']
            c_low = row['low']
            c_close = row['close']
            
            if not in_trade:
                # ── Check Bullish Breakout & Retest ──
                if not broken_out_bull and not broken_out_bear:
                    if c_high > ref_high + retest_tol:
                        broken_out_bull = True
                    elif c_low < ref_low - retest_tol:
                        broken_out_bear = True
                        
                elif broken_out_bull:
                    # Look for retest of ref_high
                    # Retest means price dips back down to touch or come within retest_tol of ref_high, but stays above ref_low (SL)
                    if c_low <= ref_high + retest_tol and c_high >= ref_high - retest_tol and c_low > ref_low:
                        in_trade = True
                        trade_dir = "BUY"
                        entry_price = ref_high + spread_points
                        sl_price = ref_low
                        tp_price = entry_price + (risk_dist * rr_ratio)
                        entry_time = t
                        continue
                    elif c_low <= ref_low:
                        # Failed before retest, setup invalidated
                        break
                        
                elif broken_out_bear:
                    # Look for retest of ref_low
                    if c_high >= ref_low - retest_tol and c_low <= ref_low + retest_tol and c_high < ref_high:
                        in_trade = True
                        trade_dir = "SELL"
                        entry_price = ref_low - spread_points
                        sl_price = ref_high
                        tp_price = entry_price - (risk_dist * rr_ratio)
                        entry_time = t
                        continue
                    elif c_high >= ref_high:
                        # Failed before retest, setup invalidated
                        break
                        
            else:
                # ── In Trade: Monitor for TP or SL hit ──
                if trade_dir == "BUY":
                    # Check SL first (conservative)
                    if c_low <= sl_price:
                        trades.append({
                            "date": str(d),
                            "symbol": symbol,
                            "tf": f"M{tf_minutes}",
                            "rr": f"1:{rr_ratio}",
                            "dir": "BUY",
                            "entry": entry_price,
                            "exit": sl_price,
                            "pnl_pts": -(entry_price - sl_price),
                            "result": "LOSS",
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break # One trade per session per day
                    elif c_high >= tp_price:
                        trades.append({
                            "date": str(d),
                            "symbol": symbol,
                            "tf": f"M{tf_minutes}",
                            "rr": f"1:{rr_ratio}",
                            "dir": "BUY",
                            "entry": entry_price,
                            "exit": tp_price,
                            "pnl_pts": tp_price - entry_price,
                            "result": "WIN",
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break
                elif trade_dir == "SELL":
                    if c_high >= sl_price:
                        trades.append({
                            "date": str(d),
                            "symbol": symbol,
                            "tf": f"M{tf_minutes}",
                            "rr": f"1:{rr_ratio}",
                            "dir": "SELL",
                            "entry": entry_price,
                            "exit": sl_price,
                            "pnl_pts": -(sl_price - entry_price),
                            "result": "LOSS",
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break
                    elif c_low <= tp_price:
                        trades.append({
                            "date": str(d),
                            "symbol": symbol,
                            "tf": f"M{tf_minutes}",
                            "rr": f"1:{rr_ratio}",
                            "dir": "SELL",
                            "entry": entry_price,
                            "exit": tp_price,
                            "pnl_pts": entry_price - tp_price,
                            "result": "WIN",
                            "entry_time": str(entry_time),
                            "exit_time": str(t)
                        })
                        in_trade = False
                        break
                        
        # If trade was still open at end of session, close at market close of session
        if in_trade:
            last_bar = post_candles.iloc[-1]
            exit_price = last_bar['close']
            pnl_pts = (exit_price - entry_price) if trade_dir == "BUY" else (entry_price - exit_price)
            res = "WIN" if pnl_pts > 0 else "LOSS"
            trades.append({
                "date": str(d),
                "symbol": symbol,
                "tf": f"M{tf_minutes}",
                "rr": f"1:{rr_ratio}",
                "dir": trade_dir,
                "entry": entry_price,
                "exit": exit_price,
                "pnl_pts": pnl_pts,
                "result": res,
                "entry_time": str(entry_time),
                "exit_time": str(post_candles.index[-1])
            })
            
    return trades

def run_comprehensive_backtest():
    mt5.initialize()
    print("=" * 80)
    print("🚀 RUNNING 1-MONTH BACKTEST: ASIAN OPEN 1, 3, 5, 15-MIN BREAKOUT & RETEST")
    print("=" * 80)
    
    # Load 1 month M1 data
    df_gold = fetch_data("GOLD", days=32)
    df_btc = fetch_data("BTCUSD", days=32)
    mt5.shutdown()
    
    print(f"Loaded GOLD M1 Candles: {len(df_gold)}")
    print(f"Loaded BTCUSD M1 Candles: {len(df_btc)}")
    
    timeframes = [1, 3, 5, 15]
    rr_ratios = [1.0, 2.0, 3.0, 4.0, 5.0]
    
    all_summary = []
    detailed_results = {}
    
    # Standard lots: 0.02 lots
    # GOLD: 1 pt = $2.00 on 0.02 lot (100 oz per 1 lot)
    # BTCUSD: $1 move = $0.02 on 0.02 lot (1 BTC per 1 lot)
    lot_size = 0.02
    
    for symbol, df, spread, multiplier in [
        ("GOLD", df_gold, 0.40, 100.0 * lot_size),
        ("BTCUSD", df_btc, 35.0, 1.0 * lot_size)
    ]:
        if df.empty:
            continue
            
        print(f"\n=======================================================")
        print(f"📊 BACKTEST RESULTS FOR {symbol} (Last 30 Days)")
        print(f"=======================================================")
        print(f"{'TF':<5} | {'R:R':<5} | {'Trades':<7} | {'Wins':<5} | {'Losses':<6} | {'WinRate%':<9} | {'Net PnL ($)':<12} | {'Profit Factor':<13} | {'Expectancy ($)':<14}")
        print("-" * 85)
        
        for tf in timeframes:
            for rr in rr_ratios:
                trades = simulate_strategy(df, symbol, tf, rr, spread_points=spread)
                
                n_trades = len(trades)
                if n_trades == 0:
                    continue
                    
                wins = [t for t in trades if t["result"] == "WIN"]
                losses = [t for t in trades if t["result"] == "LOSS"]
                n_wins = len(wins)
                n_losses = len(losses)
                win_rate = (n_wins / n_trades) * 100.0 if n_trades > 0 else 0.0
                
                # Calculate PnL in USD on 0.02 lot
                pnl_dollars = sum(t["pnl_pts"] * multiplier for t in trades)
                gross_win = sum(t["pnl_pts"] * multiplier for t in wins if t["pnl_pts"] > 0)
                gross_loss = abs(sum(t["pnl_pts"] * multiplier for t in losses if t["pnl_pts"] < 0))
                pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
                expectancy = pnl_dollars / n_trades if n_trades > 0 else 0.0
                
                row = {
                    "symbol": symbol,
                    "tf": f"M{tf}",
                    "rr": f"1:{int(rr)}",
                    "trades": n_trades,
                    "wins": n_wins,
                    "losses": n_losses,
                    "win_rate": round(win_rate, 1),
                    "net_pnl": round(pnl_dollars, 2),
                    "profit_factor": round(pf, 2),
                    "expectancy": round(expectancy, 2)
                }
                all_summary.append(row)
                detailed_results[f"{symbol}_M{tf}_1:{int(rr)}"] = trades
                
                print(f"M{tf:<4} | 1:{int(rr):<3} | {n_trades:<7} | {n_wins:<5} | {n_losses:<6} | {win_rate:<8.1f}% | ${pnl_dollars:<+11.2f} | {pf:<13.2f} | ${expectancy:<+13.2f}")
                
    # Save results to json for report artifact
    out_file = BASE_DIR / "scratch" / "asian_breakout_retest_results.json"
    with open(out_file, "w") as f:
        json.dump({"summary": all_summary, "trades": detailed_results}, f, indent=2)
    print(f"\nSaved comprehensive backtest report data to {out_file}")

if __name__ == "__main__":
    run_comprehensive_backtest()
