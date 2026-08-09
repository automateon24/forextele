import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])

symbols = ["EURUSD", "GBPUSD", "GOLD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "ETHUSD"]
timeframes = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}

results = []

for tf_name, tf_val in timeframes.items():
    for symbol in symbols:
        rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, 10000)
        if rates is None or len(rates) == 0: continue
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Indicators
        df['EMA_5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))
        
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['ATR_14'] = df['tr'].rolling(window=14).mean()
        
        # Daily High/Low for Liquidity Sweep Defense
        df['date'] = df['time'].dt.date
        daily_high = df.groupby('date')['high'].transform('max').shift(1)
        daily_low = df.groupby('date')['low'].transform('min').shift(1)
        df['PDH'] = daily_high
        df['PDL'] = daily_low
        
        # Simulate Trades
        trades = []
        for i in range(20, len(df)):
            row = df.iloc[i]
            
            # Strategy 1: RSI Reversal
            signal = None
            if row['RSI_14'] < 30: signal = "BUY"
            elif row['RSI_14'] > 70: signal = "SELL"
            
            # Market Structure Veto
            if signal == "BUY" and abs(row['close'] - row['PDH']) / row['PDH'] < 0.0015:
                signal = None # Vetoed by Liquidity Sweep
            if signal == "SELL" and abs(row['close'] - row['PDL']) / row['PDL'] < 0.0015:
                signal = None # Vetoed by Liquidity Sweep
                
            if signal:
                # Forward simulate outcome (simplified 1 ATR SL, 1.5 ATR TP)
                entry = row['close']
                sl = entry - row['ATR_14'] if signal == "BUY" else entry + row['ATR_14']
                tp = entry + row['ATR_14']*1.5 if signal == "BUY" else entry - row['ATR_14']*1.5
                
                # Check next 10 candles for outcome
                outcome = "LOSS"
                for j in range(1, 10):
                    if i+j >= len(df): break
                    fut = df.iloc[i+j]
                    if signal == "BUY":
                        if fut['low'] <= sl: outcome = "LOSS"; break
                        if fut['high'] >= tp: outcome = "WIN"; break
                    else:
                        if fut['high'] >= sl: outcome = "LOSS"; break
                        if fut['low'] <= tp: outcome = "WIN"; break
                trades.append(outcome)
                
        wins = trades.count("WIN")
        losses = trades.count("LOSS")
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        
        results.append({
            "Timeframe": tf_name,
            "Symbol": symbol,
            "Total Trades": total,
            "Win Rate": f"{win_rate:.1f}%"
        })

res_df = pd.DataFrame(results)
print(res_df.to_markdown(index=False))
mt5.shutdown()
