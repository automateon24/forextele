import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json

def load_data(symbol, timeframe, bars=8000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def find_golden_combos():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    symbols = ["GOLD", "USDJPY", "AUDUSD"]
    timezones = {
        "ASIAN": (22, 8),
        "LONDON": (8, 13),
        "NY": (13, 20)
    }
    
    strategies = ["MEAN_REVERSION", "MOMENTUM_CROSS", "VOLATILITY_BREAKOUT"]
    
    final_results = []
    
    for sym in symbols:
        df = load_data(sym, mt5.TIMEFRAME_M5, 8000)
        if df is None: continue
            
        # Indicators
        df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['macro_trend'] = np.where(df['close'] > df['EMA_50'], 'BULLISH', 'BEARISH')
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['STD_20'] = df['close'].rolling(window=20).std()
        df['Upper_BB'] = df['SMA_20'] + (df['STD_20'] * 2)
        df['Lower_BB'] = df['SMA_20'] - (df['STD_20'] * 2)
        
        swing_len = 8
        df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
        df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
        df['last_sh'] = df['high'].where(df['swing_high']).ffill()
        df['last_sl'] = df['low'].where(df['swing_low']).ffill()
        
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['ATR'] = df['tr'].rolling(window=14).mean()
        df['ATR_MA'] = df['ATR'].rolling(window=50).mean()
        
        for tz_name, (tz_start, tz_end) in timezones.items():
            for strat in strategies:
                trades = []
                cooldown = 0
                
                for i in range(50, len(df) - 10):
                    if cooldown > 0:
                        cooldown -= 1
                        continue
                        
                    row = df.iloc[i]
                    prev = df.iloc[i-1]
                    hour = row['time'].hour
                    
                    # Timezone Check (Handling Asian crossover midnight)
                    in_tz = False
                    if tz_start > tz_end:
                        in_tz = (hour >= tz_start or hour <= tz_end)
                    else:
                        in_tz = (tz_start <= hour <= tz_end)
                        
                    if not in_tz: continue
                        
                    raw_signal = None
                    
                    if strat == "MEAN_REVERSION":
                        if row['RSI'] < 30 and row['close'] < row['Lower_BB']: raw_signal = "BUY"
                        elif row['RSI'] > 70 and row['close'] > row['Upper_BB']: raw_signal = "SELL"
                    
                    elif strat == "MOMENTUM_CROSS":
                        if row['EMA_9'] > row['EMA_21'] and prev['EMA_9'] <= prev['EMA_21']: raw_signal = "BUY"
                        elif row['EMA_9'] < row['EMA_21'] and prev['EMA_9'] >= prev['EMA_21']: raw_signal = "SELL"
                        
                    elif strat == "VOLATILITY_BREAKOUT":
                        if row['close'] > df.iloc[i]['last_sh'] and prev['close'] <= prev['last_sh']: raw_signal = "BUY"
                        elif row['close'] < df.iloc[i]['last_sl'] and prev['close'] >= prev['last_sl']: raw_signal = "SELL"
                        
                    if not raw_signal: continue
                        
                    # Basic SMC Alignment Filter
                    if raw_signal == "BUY" and row['macro_trend'] != 'BULLISH': continue
                    if raw_signal == "SELL" and row['macro_trend'] != 'BEARISH': continue
                    if row['ATR'] < row['ATR_MA']: continue # Avoid Chop
                        
                    sl_multiplier = 0.5 if sym == "GOLD" else 0.2
                    entry = row['close']
                    sl = df.iloc[i]['last_sl'] - (row['ATR'] * sl_multiplier) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR'] * sl_multiplier)
                    risk_dist = abs(entry - sl)
                    if risk_dist <= 0: continue
                    tp = entry + (risk_dist * 2.5) if raw_signal == "BUY" else entry - (risk_dist * 2.5)
                    
                    dollar_risk = 30
                    outcome = "PENDING"
                    profit = 0
                    
                    for j in range(1, 40):
                        if i+j >= len(df): break
                        fut = df.iloc[i+j]
                        if raw_signal == "BUY":
                            if fut['low'] <= sl: outcome = "LOSS"; profit -= dollar_risk; break
                            if fut['high'] >= tp: outcome = "WIN"; profit += (dollar_risk * 2.5); break
                        else:
                            if fut['high'] >= sl: outcome = "LOSS"; profit -= dollar_risk; break
                            if fut['low'] <= tp: outcome = "WIN"; profit += (dollar_risk * 2.5); break
                                
                    if outcome != "PENDING":
                        trades.append(profit)
                        cooldown = 10
                        
                net_profit = sum(trades)
                if net_profit > 0: # ONLY SAVE PROFITABLE COMBINATIONS
                    final_results.append({
                        "Symbol": sym,
                        "TimeZone": tz_name,
                        "Strategy": strat,
                        "Trades": len(trades),
                        "Net Profit": f"${net_profit:.2f}"
                    })
                    
    res_df = pd.DataFrame(final_results).sort_values(by="Net Profit", ascending=False)
    print("=== THE GOLDEN MATRIX: PROFITABLE COMBINATIONS DISCOVERED ===")
    print(res_df.to_string(index=False))
    mt5.shutdown()

if __name__ == "__main__":
    find_golden_combos()
