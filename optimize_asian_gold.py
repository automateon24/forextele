import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime

def load_data(symbol, timeframe, bars=5000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def optimize_special_pairs():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    pairs = {
        "GOLD": {"tf": mt5.TIMEFRAME_M15, "rr": 3.0, "risk_multiplier": 2.5}, # High risk, high reward
        "USDJPY": {"tf": mt5.TIMEFRAME_M5, "rr": 2.5, "risk_multiplier": 1.5},
        "AUDUSD": {"tf": mt5.TIMEFRAME_M5, "rr": 2.0, "risk_multiplier": 1.0}
    }
    
    results = []
    
    for sym, config in pairs.items():
        df = load_data(sym, config["tf"], 8000)
        if df is None: continue
            
        # Common Indicators
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['macro_trend'] = np.where(df['EMA_50'] > df['EMA_200'], 'BULLISH', 'BEARISH')
        
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['ATR'] = df['tr'].rolling(window=14).mean()
        
        # SMC Swing Points
        swing_len = 5
        df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
        df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
        df['last_sh'] = df['high'].where(df['swing_high']).ffill()
        df['last_sl'] = df['low'].where(df['swing_low']).ffill()
        
        # For Gold: Daily High/Low for Liquidity Sweeps
        df['date'] = df['time'].dt.date
        df['PDH'] = df.groupby('date')['high'].transform('max').shift(1)
        df['PDL'] = df.groupby('date')['low'].transform('min').shift(1)
        df['sweep_high'] = (df['high'] > df['PDH']) & (df['close'] < df['PDH'])
        df['sweep_low'] = (df['low'] < df['PDL']) & (df['close'] > df['PDL'])
        
        # Mean Reversion
        df['typ'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typ']).rolling(window=50).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        trades = []
        base_risk = 30 # $30 equals 1% of 3000
        golden_count = 0
        
        for i in range(50, len(df) - 10):
            row = df.iloc[i]
            hour = row['time'].hour
            
            raw_signal = None
            strategy = ""
            
            # --- 1. GOLD DNA ---
            if sym == "GOLD":
                if not (13 <= hour <= 20): continue # NY Session
                
                # Liquidity Sweep Strategy (Highest Win Rate for Gold)
                if row['sweep_low'] and row['macro_trend'] == 'BULLISH':
                    raw_signal, strategy = "BUY", "LIQUIDITY_SWEEP"
                elif row['sweep_high'] and row['macro_trend'] == 'BEARISH':
                    raw_signal, strategy = "SELL", "LIQUIDITY_SWEEP"
                    
                # VWAP Mean Reversion Strategy (Chop Phase)
                elif row['RSI'] < 25 and row['close'] < row['vwap'] - row['ATR']:
                    raw_signal, strategy = "BUY", "VWAP_REVERSION"
                elif row['RSI'] > 75 and row['close'] > row['vwap'] + row['ATR']:
                    raw_signal, strategy = "SELL", "VWAP_REVERSION"
                    
            # --- 2. USDJPY DNA ---
            elif sym == "USDJPY":
                if hour >= 22 or hour <= 10: # Asian/London carry trade
                    # EMA Trend Pullback (USDJPY respects trends)
                    if row['macro_trend'] == 'BULLISH' and row['low'] < row['EMA_50'] and row['close'] > row['EMA_50']:
                        raw_signal, strategy = "BUY", "TREND_PULLBACK"
                    elif row['macro_trend'] == 'BEARISH' and row['high'] > row['EMA_50'] and row['close'] < row['EMA_50']:
                        raw_signal, strategy = "SELL", "TREND_PULLBACK"
                        
            # --- 3. AUDUSD DNA ---
            elif sym == "AUDUSD":
                if 22 <= hour <= 8: # Asian Session only
                    # SMC CHOCH Breakout (Cleanest during Asian session)
                    if row['close'] > df.iloc[i]['last_sh'] and df.iloc[i-1]['close'] <= df.iloc[i-1]['last_sh'] and row['macro_trend'] == 'BULLISH':
                        raw_signal, strategy = "BUY", "SMC_BREAKOUT"
                    elif row['close'] < df.iloc[i]['last_sl'] and df.iloc[i-1]['close'] >= df.iloc[i-1]['last_sl'] and row['macro_trend'] == 'BEARISH':
                        raw_signal, strategy = "SELL", "SMC_BREAKOUT"
                        
            if not raw_signal: continue
                
            entry = row['close']
            sl = df.iloc[i]['last_sl'] - (row['ATR']*0.5) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR']*0.5)
            risk_dist = abs(entry - sl)
            if risk_dist <= 0: continue
            
            rr = config["rr"]
            tp = entry + (risk_dist * rr) if raw_signal == "BUY" else entry - (risk_dist * rr)
            
            dollar_risk = base_risk * config["risk_multiplier"]
            
            outcome = "PENDING"
            profit = 0
            
            for j in range(1, 40):
                if i+j >= len(df): break
                fut = df.iloc[i+j]
                
                if raw_signal == "BUY":
                    if fut['low'] <= sl: outcome = "LOSS"; profit -= dollar_risk; break
                    if fut['high'] >= tp: outcome = "WIN"; profit += (dollar_risk * rr); break
                else:
                    if fut['high'] >= sl: outcome = "LOSS"; profit -= dollar_risk; break
                    if fut['low'] <= tp: outcome = "WIN"; profit += (dollar_risk * rr); break
                        
            if outcome != "PENDING":
                trades.append(profit)
                if profit > 0: golden_count += 1
                
        results.append({
            "Symbol": sym,
            "Total High-Prob Trades": len(trades),
            "Wins": golden_count,
            "Net Profit": f"${sum(trades):.2f}"
        })
        
    res_df = pd.DataFrame(results)
    print("=== GOLD, USDJPY, AUDUSD (DNA OPTIMIZED MODULE) ===")
    print(res_df.to_string(index=False))
    mt5.shutdown()

if __name__ == "__main__":
    optimize_special_pairs()
