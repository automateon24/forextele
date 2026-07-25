import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime

def load_data(symbol, timeframe, bars=2000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def get_h1_trend(symbol):
    # Load H1 data to find macro trend
    h1 = load_data(symbol, mt5.TIMEFRAME_H1, 300)
    if h1 is None: return None
    
    # Calculate macro EMA
    h1['EMA_50'] = h1['close'].ewm(span=50, adjust=False).mean()
    
    # Map H1 trend back to M5 timeframe
    # We create a dictionary mapping the date-hour to the trend state
    h1['date_hour'] = h1['time'].dt.strftime('%Y-%m-%d %H')
    h1['macro_trend'] = np.where(h1['close'] > h1['EMA_50'], 'BULLISH', 'BEARISH')
    
    return dict(zip(h1['date_hour'], h1['macro_trend']))

def calculate_indicators(df, swing_len=8):
    # SMC: Swing Highs and Lows
    df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
    
    df['last_sh'] = df['high'].where(df['swing_high']).ffill()
    df['last_sl'] = df['low'].where(df['swing_low']).ffill()
    
    # ATR
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['ATR'] = df['tr'].rolling(window=14).mean()

    # SMC: Detect Break of Structure (BOS) / Change of Character (CHOCH)
    df['choch_bull'] = (df['close'] > df['last_sh'].shift(1)) & (df['close'].shift(1) <= df['last_sh'].shift(2))
    df['choch_bear'] = (df['close'] < df['last_sl'].shift(1)) & (df['close'].shift(1) >= df['last_sl'].shift(2))
    
    # VWAP (Simplified Intraday using cumulative typical price)
    df['date'] = df['time'].dt.date
    df['typ'] = (df['high'] + df['low'] + df['close']) / 3
    df['vol'] = 1 # Proxy for volume if missing
    df['vwap'] = (df['typ'] * df['vol']).groupby(df['date']).cumsum() / df['vol'].groupby(df['date']).cumsum()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

def is_in_session(symbol, dt):
    hour = dt.hour
    
    if symbol in ["EURUSD", "GBPUSD"]:
        # London + NY overlap (07:00 to 18:00)
        return 7 <= hour <= 18
    elif symbol in ["GOLD"]:
        # London + NY overlap (07:00 to 18:00)
        return 7 <= hour <= 18
    elif symbol in ["USDJPY", "AUDUSD"]:
        # Asian Session + Early London (22:00 to 08:00)
        return hour >= 22 or hour <= 8
    elif symbol in ["USDCAD"]:
        # NY Session (12:00 to 20:00)
        return 12 <= hour <= 20
    elif symbol in ["BTCUSD", "ETHUSD"]:
        # Crypto volume peaks during NY Session (12:00 to 20:00)
        return 12 <= hour <= 20
    return True

def backtest_mtfa_smc(df, h1_trend_map, symbol):
    trades = []
    # Institutional Risk/Reward (1:2.5)
    rr = 2.5 
    
    for i in range(50, len(df) - 10):
        row = df.iloc[i]
        
        # 1. TIMING ZONE FILTER (Kill Zones)
        if not is_in_session(symbol, row['time']):
            continue
            
        date_hour = row['time'].strftime('%Y-%m-%d %H')
        macro_trend = h1_trend_map.get(date_hour, 'UNKNOWN')
        
        signal = None
        sl = 0
        tp = 0
        
        # Strategy 1: MTFA Aligned CHOCH
        if row['choch_bull'] and macro_trend == 'BULLISH':
            signal = "BUY"
            sl = df.iloc[i]['last_sl'] - (row['ATR'] * 0.5)
        elif row['choch_bear'] and macro_trend == 'BEARISH':
            signal = "SELL"
            sl = df.iloc[i]['last_sh'] + (row['ATR'] * 0.5)
            
        # Strategy 2: VWAP Mean Reversion (Extreme Oversold/Overbought against trend)
        elif row['RSI'] < 25 and row['close'] < row['vwap'] - row['ATR']*2 and macro_trend == 'BULLISH':
            signal = "BUY"
            sl = row['low'] - row['ATR']
        elif row['RSI'] > 75 and row['close'] > row['vwap'] + row['ATR']*2 and macro_trend == 'BEARISH':
            signal = "SELL"
            sl = row['high'] + row['ATR']
            
        if signal:
            entry = row['close']
            risk = abs(entry - sl)
            if risk <= 0: continue
            
            if signal == "BUY":
                tp = entry + (risk * rr)
            else:
                tp = entry - (risk * rr)
                
            outcome = "PENDING"
            # Trailing Stop Loss Mechanics
            tsl = sl
            breakeven_triggered = False
            
            for j in range(1, 60):
                if i+j >= len(df): break
                fut = df.iloc[i+j]
                
                if signal == "BUY":
                    # Check Trailing Stop logic first
                    if not breakeven_triggered and fut['high'] >= entry + risk:
                        tsl = entry # Move to Breakeven when 1R in profit
                        breakeven_triggered = True
                        
                    if fut['low'] <= tsl: 
                        outcome = "BREAKEVEN" if breakeven_triggered else "LOSS"
                        break
                    if fut['high'] >= tp: 
                        outcome = "WIN"
                        break
                else:
                    if not breakeven_triggered and fut['low'] <= entry - risk:
                        tsl = entry # Move to Breakeven when 1R in profit
                        breakeven_triggered = True
                        
                    if fut['high'] >= tsl: 
                        outcome = "BREAKEVEN" if breakeven_triggered else "LOSS"
                        break
                    if fut['low'] <= tp: 
                        outcome = "WIN"
                        break
            
            if outcome != "PENDING":
                trades.append(outcome)
                
    wins = trades.count("WIN")
    losses = trades.count("LOSS")
    be = trades.count("BREAKEVEN")
    total_completed = wins + losses # Ignore breakevens for win rate calculation
    win_rate = (wins / total_completed * 100) if total_completed > 0 else 0
    total = len(trades)
    
    return total, win_rate, be

def main():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    symbols = ["EURUSD", "GBPUSD", "GOLD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "ETHUSD"]
    # 2 weeks of M5 data ~ 4000 bars
    bars = 4000 
    
    results = []
    
    for sym in symbols:
        h1_trend_map = get_h1_trend(sym)
        if not h1_trend_map: continue
        
        df = load_data(sym, mt5.TIMEFRAME_M5, bars)
        if df is None: continue
        
        df = calculate_indicators(df, swing_len=8)
        total, win_rate, be = backtest_mtfa_smc(df, h1_trend_map, sym)
        
        results.append({
            "Symbol": sym,
            "Total Trades": total,
            "Breakevens": be,
            "Win Rate (1:2.5 RR)": f"{win_rate:.1f}%"
        })
        
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    mt5.shutdown()

if __name__ == "__main__":
    main()
