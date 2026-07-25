import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

def load_data(symbol, timeframe, bars=2000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def calculate_smc(df, swing_len=5):
    # Calculate Swing Highs and Lows
    df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
    
    # Forward fill to track the last known swing high/low levels
    df['last_sh'] = df['high'].where(df['swing_high']).ffill()
    df['last_sl'] = df['low'].where(df['swing_low']).ffill()
    
    # Calculate ATR for dynamic risk management
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['ATR'] = df['tr'].rolling(window=14).mean()

    # Detect Liquidity Sweeps (Price pierces SH/SL but closes inside)
    # Bearish Sweep (Sweeps High, Closes below)
    df['sweep_high'] = (df['high'] > df['last_sh'].shift(1)) & (df['close'] < df['last_sh'].shift(1))
    # Bullish Sweep (Sweeps Low, Closes above)
    df['sweep_low'] = (df['low'] < df['last_sl'].shift(1)) & (df['close'] > df['last_sl'].shift(1))
    
    # Detect Break of Structure (BOS) / Change of Character (CHOCH)
    # Bullish CHOCH/BOS: Close above last swing high
    df['choch_bull'] = (df['close'] > df['last_sh'].shift(1)) & (df['close'].shift(1) <= df['last_sh'].shift(2))
    # Bearish CHOCH/BOS: Close below last swing low
    df['choch_bear'] = (df['close'] < df['last_sl'].shift(1)) & (df['close'].shift(1) >= df['last_sl'].shift(2))
    
    return df

def backtest_smc(df):
    trades = []
    # 1:2 Risk Reward
    rr = 2.0 
    
    for i in range(50, len(df) - 10):
        row = df.iloc[i]
        signal = None
        sl = 0
        tp = 0
        
        # Strategy A: Liquidity Sweep Reversal
        if row['sweep_low']:
            signal = "BUY"
            entry = row['close']
            sl = row['low'] - (row['ATR'] * 0.5) # Stop just below the sweep wick
            risk = entry - sl
            tp = entry + (risk * rr)
            
        elif row['sweep_high']:
            signal = "SELL"
            entry = row['close']
            sl = row['high'] + (row['ATR'] * 0.5)
            risk = sl - entry
            tp = entry - (risk * rr)
            
        # Strategy B: CHOCH / Momentum Continuation
        elif row['choch_bull']:
            signal = "BUY"
            entry = row['close']
            sl = df.iloc[i]['last_sl'] - (row['ATR'] * 0.2)
            risk = entry - sl
            if risk > 0:
                tp = entry + (risk * rr)
            else:
                signal = None
                
        elif row['choch_bear']:
            signal = "SELL"
            entry = row['close']
            sl = df.iloc[i]['last_sh'] + (row['ATR'] * 0.2)
            risk = sl - entry
            if risk > 0:
                tp = entry - (risk * rr)
            else:
                signal = None
        
        # Fast Forward execution
        if signal:
            outcome = "PENDING"
            for j in range(1, 40): # Check next 40 candles
                if i+j >= len(df): break
                fut = df.iloc[i+j]
                
                if signal == "BUY":
                    if fut['low'] <= sl: 
                        outcome = "LOSS"
                        break
                    if fut['high'] >= tp: 
                        outcome = "WIN"
                        break
                else:
                    if fut['high'] >= sl: 
                        outcome = "LOSS"
                        break
                    if fut['low'] <= tp: 
                        outcome = "WIN"
                        break
            
            if outcome != "PENDING":
                trades.append(outcome)
                
    wins = trades.count("WIN")
    losses = trades.count("LOSS")
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    
    return total, win_rate

def main():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    symbols = ["EURUSD", "GBPUSD", "GOLD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "ETHUSD"]
    # 1 week of M5 data is approx 1440 bars
    bars = 2000
    
    results = []
    
    for sym in symbols:
        df = load_data(sym, mt5.TIMEFRAME_M5, bars)
        if df is None: continue
        
        df = calculate_smc(df, swing_len=5)
        total, win_rate = backtest_smc(df)
        
        results.append({
            "Symbol": sym,
            "Total Trades (1 Wk)": total,
            "Win Rate (1:2 RR)": f"{win_rate:.1f}%"
        })
        
    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    mt5.shutdown()

if __name__ == "__main__":
    main()
