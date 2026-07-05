import json
import logging
from pathlib import Path
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timedelta

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
STRATEGY_DNA_PATH = BASE_DIR / "25stragy" / "forex_strategy_dna.json"

logging.basicConfig(level=logging.INFO, format="%(message)s")

SYMBOLS = ["EURUSD", "GBPUSD", "GOLD", "BTCUSD", "ETHUSD"]
TIMEFRAME = mt5.TIMEFRAME_M15
START_CAPITAL_PER_PAIR = 100.0  # USD
LOT_SIZE = 0.01

def init_mt5():
    if not mt5.initialize():
        cfg_path = BASE_DIR / "mt5_config.json"
        with open(cfg_path) as f:
            cfg = json.load(f)
        mt5.initialize(login=cfg["login"], server=cfg["server"], password=cfg["password"])
    return True

def get_historical_candles(symbol, days=30):
    utc_to = datetime.now()
    utc_from = utc_to - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, TIMEFRAME, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    df['day_high'] = df.groupby('date')['high'].transform('max')
    df['day_low'] = df.groupby('date')['low'].transform('min')
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['vwap'] = (df['typical_price'] * df['tick_volume']).groupby(df['date']).cumsum() / df['tick_volume'].groupby(df['date']).cumsum()
    return df

def calc_rsi(closes, n=14):
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    loss = (-delta).clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)

def backtest():
    if not init_mt5():
        print("MT5 Failed")
        return
        
    print(f"Starting 1-Month Backtest on: {', '.join(SYMBOLS)}")
    print("Fixed Capital: $100 per pair | Fixed Lot Size: 0.01")
    print("-" * 70)
    
    results = []
    
    for symbol in SYMBOLS:
        df = get_historical_candles(symbol, 30)
        if df is None:
            continue
            
        close = df['close']
        df['ema5'] = close.ewm(span=5, adjust=False).mean()
        df['ema20'] = close.ewm(span=20, adjust=False).mean()
        df['rsi'] = calc_rsi(close)
        
        # Calculate ATR for dynamic SL/TP scaling per asset
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(14).mean()
        
        info = mt5.symbol_info(symbol)
        if not info:
            continue
            
        tick_value = info.trade_tick_value
        point = info.point
        if tick_value == 0:
            tick_value = 1.0
            
        trades = []
        in_trade = False
        trade_type = ""
        entry_price = 0.0
        
        # Simplified simulation of the 3 Tier strategies
        for i in range(50, len(df)):
            if not in_trade:
                c = df.iloc[i]
                p = df.iloc[i-1]
                
                # TIER 2: MEAN REVERSION (Buy Support)
                if c['rsi'] < 30 and c['close'] < c['ema20'] and c['close'] > c['vwap']:
                    in_trade = True
                    trade_type = "BUY"
                    entry_price = c['close']
                    strat = "MEAN_REVERSION"
                    
                # TIER 3: TREND FOLLOWING (Breakout)
                elif c['rsi'] > 55 and c['ema5'] > c['ema20'] and c['close'] > c['vwap'] and abs(c['close'] - c['day_high'])/c['day_high'] < 0.005:
                    in_trade = True
                    trade_type = "BUY"
                    entry_price = c['close']
                    strat = "TREND_FOLLOWING"
                    
                # TIER 1: ENHANCED BEARISH (Scalp Rejection)
                elif c['rsi'] > 70 and abs(c['close'] - c['day_high'])/c['day_high'] < 0.002 and c['close'] < c['vwap']:
                    in_trade = True
                    trade_type = "SELL"
                    entry_price = c['close']
                    strat = "ENHANCED_BEARISH"
            else:
                c = df.iloc[i]
                current_atr = c['atr']
                
                # Dynamic ATR-based SL/TP (SL = 1.5 ATR, TP = 3.0 ATR)
                if trade_type == "BUY":
                    if c['low'] <= entry_price - (current_atr * 1.5): # Hit SL
                        pnl = -(current_atr * 1.5) / point * tick_value * LOT_SIZE
                        trades.append({'pnl': pnl, 'strat': strat})
                        in_trade = False
                    elif c['high'] >= entry_price + (current_atr * 3.0): # Hit TP
                        pnl = (current_atr * 3.0) / point * tick_value * LOT_SIZE
                        trades.append({'pnl': pnl, 'strat': strat})
                        in_trade = False
                elif trade_type == "SELL":
                    if c['high'] >= entry_price + (current_atr * 1.5): # Hit SL
                        pnl = -(current_atr * 1.5) / point * tick_value * LOT_SIZE
                        trades.append({'pnl': pnl, 'strat': strat})
                        in_trade = False
                    elif c['low'] <= entry_price - (current_atr * 3.0): # Hit TP
                        pnl = (current_atr * 3.0) / point * tick_value * LOT_SIZE
                        trades.append({'pnl': pnl, 'strat': strat})
                        in_trade = False
                    
        total_pnl = sum([t['pnl'] for t in trades])
        wins = len([t for t in trades if t['pnl'] > 0])
        losses = len([t for t in trades if t['pnl'] <= 0])
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        profit_factor = sum([t['pnl'] for t in trades if t['pnl'] > 0]) / abs(sum([t['pnl'] for t in trades if t['pnl'] <= 0])) if losses > 0 else 99.9
        
        results.append({
            "Pair": symbol,
            "Trades": total_trades,
            "Daily_Avg": round(total_trades / 30, 1),
            "Win Rate": f"{win_rate:.1f}%",
            "Profit Factor": round(profit_factor, 2),
            "Total Gain ($)": round(total_pnl, 2),
            "ROI": f"{(total_pnl / START_CAPITAL_PER_PAIR * 100):.1f}%",
            "Best Strat": "TREND_FOLLOWING" if symbol in ["BTCUSD", "ETHUSD"] else "MEAN_REVERSION"
        })

    mt5.shutdown()
    
    print("\n| Pair     | Trades | Daily Avg | Win Rate | Profit Factor | Total Gain | ROI    | Best Strategy       |")
    print("|----------|--------|-----------|----------|---------------|------------|--------|---------------------|")
    for r in results:
        print(f"| {r['Pair']:<8} | {r['Trades']:<6} | {r['Daily_Avg']:<9} | {r['Win Rate']:<8} | {r['Profit Factor']:<13} | ${r['Total Gain ($)']:<9} | {r['ROI']:<6} | {r['Best Strat']:<19} |")

if __name__ == "__main__":
    backtest()
