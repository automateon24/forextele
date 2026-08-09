import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json

def load_data(symbol, timeframe, bars=5000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def optimize_stubborn_pairs():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    symbols = ["USDJPY", "AUDUSD"]
    timeframes = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
    rr_ratios = [1.5, 2.5, 3.5]
    sl_multipliers = [0.5, 1.0, 2.0]
    
    results = []
    
    for sym in symbols:
        for tf_name, tf_val in timeframes.items():
            df = load_data(sym, tf_val, 8000)
            if df is None: continue
                
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
            
            for rr in rr_ratios:
                for sl_mult in sl_multipliers:
                    trades = []
                    cooldown = 0
                    
                    for i in range(50, len(df) - 10):
                        if cooldown > 0:
                            cooldown -= 1
                            continue
                            
                        row = df.iloc[i]
                        prev = df.iloc[i-1]
                        
                        raw_signal = None
                        strat = ""
                        
                        # Test all 3 base logics simultaneously
                        if row['RSI'] < 30 and row['close'] < row['Lower_BB']: raw_signal, strat = "BUY", "MEAN_REV"
                        elif row['RSI'] > 70 and row['close'] > row['Upper_BB']: raw_signal, strat = "SELL", "MEAN_REV"
                        elif row['EMA_9'] > row['EMA_21'] and prev['EMA_9'] <= prev['EMA_21']: raw_signal, strat = "BUY", "MOM_CROSS"
                        elif row['EMA_9'] < row['EMA_21'] and prev['EMA_9'] >= prev['EMA_21']: raw_signal, strat = "SELL", "MOM_CROSS"
                        elif row['close'] > df.iloc[i]['last_sh'] and prev['close'] <= prev['last_sh']: raw_signal, strat = "BUY", "BREAKOUT"
                        elif row['close'] < df.iloc[i]['last_sl'] and prev['close'] >= prev['last_sl']: raw_signal, strat = "SELL", "BREAKOUT"
                        
                        if not raw_signal: continue
                            
                        if raw_signal == "BUY" and row['macro_trend'] != 'BULLISH': continue
                        if raw_signal == "SELL" and row['macro_trend'] != 'BEARISH': continue
                            
                        entry = row['close']
                        sl = df.iloc[i]['last_sl'] - (row['ATR'] * sl_mult) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR'] * sl_mult)
                        risk_dist = abs(entry - sl)
                        if risk_dist <= 0: continue
                        tp = entry + (risk_dist * rr) if raw_signal == "BUY" else entry - (risk_dist * rr)
                        
                        dollar_risk = 30
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
                            cooldown = 10
                            
                    net_profit = sum(trades)
                    if net_profit > 200: # Only care about significant breakthroughs
                        results.append({
                            "Symbol": sym,
                            "TF": tf_name,
                            "RR": rr,
                            "SL_ATR": sl_mult,
                            "Trades": len(trades),
                            "Net Profit": f"${net_profit:.2f}"
                        })
                        
    res_df = pd.DataFrame(results).sort_values(by="Net Profit", ascending=False)
    print("=== PARAMETER OPTIMIZATION (USDJPY & AUDUSD) ===")
    if len(res_df) > 0:
        print(res_df.to_string(index=False))
    else:
        print("No configurations generated >$200 profit. Deeper structural DNA change required.")
    mt5.shutdown()

if __name__ == "__main__":
    optimize_stubborn_pairs()
