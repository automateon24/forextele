import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from collections import Counter

def load_data(symbol, timeframe, bars=8000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def get_h1_trend(symbol):
    h1 = load_data(symbol, mt5.TIMEFRAME_H1, 800)
    if h1 is None: return None
    h1['EMA_50'] = h1['close'].ewm(span=50, adjust=False).mean()
    h1['date_hour'] = h1['time'].dt.strftime('%Y-%m-%d %H')
    h1['macro_trend'] = np.where(h1['close'] > h1['EMA_50'], 'BULLISH', 'BEARISH')
    return dict(zip(h1['date_hour'], h1['macro_trend']))

def analyze_gold_failures():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    df = load_data("GOLD", mt5.TIMEFRAME_M5, 8000)
    h1_map = get_h1_trend("GOLD")
    
    if df is None or h1_map is None: return
    
    swing_len = 8
    df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
    df['last_sh'] = df['high'].where(df['swing_high']).ffill()
    df['last_sl'] = df['low'].where(df['swing_low']).ffill()
    
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    df['STD_20'] = df['close'].rolling(window=20).std()
    df['Upper_BB'] = df['SMA_20'] + (df['STD_20'] * 2)
    df['Lower_BB'] = df['SMA_20'] - (df['STD_20'] * 2)
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['ATR'] = df['tr'].rolling(window=14).mean()
    df['ATR_MA_50'] = df['ATR'].rolling(window=50).mean()
    
    rr = 2.5
    failure_hours = []
    failure_days = []
    success_hours = []
    
    for i in range(50, len(df) - 10):
        row = df.iloc[i]
        hour = row['time'].hour
        day = row['time'].strftime('%A')
        
        # Original Kill Zone for Gold was 7-18
        if not (7 <= hour <= 18): continue
            
        date_hour = row['time'].strftime('%Y-%m-%d %H')
        h1_trend = h1_map.get(date_hour, 'UNKNOWN')
        
        raw_signal = None
        if row['RSI'] < 30 and row['close'] < row['Lower_BB']: raw_signal = "BUY"
        elif row['RSI'] > 70 and row['close'] > row['Upper_BB']: raw_signal = "SELL"
        elif row['EMA_9'] > row['EMA_21'] and df.iloc[i-1]['EMA_9'] <= df.iloc[i-1]['EMA_21']: raw_signal = "BUY"
        elif row['EMA_9'] < row['EMA_21'] and df.iloc[i-1]['EMA_9'] >= df.iloc[i-1]['EMA_21']: raw_signal = "SELL"
        
        if not raw_signal: continue
            
        smc_approved = False
        if raw_signal == "BUY" and h1_trend == 'BULLISH' and row['close'] > df.iloc[i]['last_sl']: smc_approved = True
        elif raw_signal == "SELL" and h1_trend == 'BEARISH' and row['close'] < df.iloc[i]['last_sh']: smc_approved = True
            
        if not smc_approved: continue
        if row['ATR'] < row['ATR_MA_50']: continue
            
        entry = row['close']
        sl = df.iloc[i]['last_sl'] - (row['ATR'] * 0.2) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR'] * 0.2)
        risk_dist = abs(entry - sl)
        if risk_dist <= 0: continue
        tp = entry + (risk_dist * rr) if raw_signal == "BUY" else entry - (risk_dist * rr)
        
        outcome = "PENDING"
        for j in range(1, 60):
            if i+j >= len(df): break
            fut = df.iloc[i+j]
            
            if raw_signal == "BUY":
                if fut['low'] <= sl: outcome = "LOSS"; break
                if fut['high'] >= tp: outcome = "WIN"; break
            else:
                if fut['high'] >= sl: outcome = "LOSS"; break
                if fut['low'] <= tp: outcome = "WIN"; break
                
        if outcome == "LOSS":
            failure_hours.append(hour)
            failure_days.append(day)
        elif outcome == "WIN":
            success_hours.append(hour)
            
    print("=== GOLD FAILURE PATTERN ANALYSIS ===")
    print("\n[LOSING TRADES BY HOUR (GMT)]")
    for hr, count in sorted(Counter(failure_hours).items()):
        print(f"Hour {hr:02d}:00  => {count} Losses")
        
    print("\n[WINNING TRADES BY HOUR (GMT)]")
    for hr, count in sorted(Counter(success_hours).items()):
        print(f"Hour {hr:02d}:00  => {count} Wins")
        
    print("\n[LOSING TRADES BY DAY OF WEEK]")
    for d, count in sorted(Counter(failure_days).items(), key=lambda x: x[1], reverse=True):
        print(f"{d}: {count} Losses")
        
    mt5.shutdown()

if __name__ == "__main__":
    analyze_gold_failures()
