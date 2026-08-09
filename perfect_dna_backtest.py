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

def get_macro_trends(symbol):
    h1 = load_data(symbol, mt5.TIMEFRAME_H1, 800)
    h4 = load_data(symbol, mt5.TIMEFRAME_H4, 200)
    if h1 is None or h4 is None: return None, None
    
    h1['EMA_50'] = h1['close'].ewm(span=50, adjust=False).mean()
    h1['date_hour'] = h1['time'].dt.strftime('%Y-%m-%d %H')
    h1['macro_trend'] = np.where(h1['close'] > h1['EMA_50'], 'BULLISH', 'BEARISH')
    h1_map = dict(zip(h1['date_hour'], h1['macro_trend']))
    
    h4['EMA_50'] = h4['close'].ewm(span=50, adjust=False).mean()
    h4.set_index('time', inplace=True)
    h4 = h4.resample('1h').ffill().reset_index()
    h4['date_hour'] = h4['time'].dt.strftime('%Y-%m-%d %H')
    h4['h4_trend'] = np.where(h4['close'] > h4['EMA_50'], 'BULLISH', 'BEARISH')
    h4_map = dict(zip(h4['date_hour'], h4['h4_trend']))
    
    return h1_map, h4_map

def calculate_indicators(df, swing_len=8):
    df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
    df['last_sh'] = df['high'].where(df['swing_high']).ffill()
    df['last_sl'] = df['low'].where(df['swing_low']).ffill()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    df['STD_20'] = df['close'].rolling(window=20).std()
    df['Upper_BB'] = df['SMA_20'] + (df['STD_20'] * 2)
    df['Lower_BB'] = df['SMA_20'] - (df['STD_20'] * 2)
    
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['ATR'] = df['tr'].rolling(window=14).mean()
    df['ATR_MA_50'] = df['ATR'].rolling(window=50).mean()
    
    df['date'] = df['time'].dt.date
    df['PDH'] = df.groupby('date')['high'].transform('max').shift(1)
    df['PDL'] = df.groupby('date')['low'].transform('min').shift(1)
    df['sweep_high'] = (df['high'] > df['PDH']) & (df['close'] < df['PDH'])
    df['sweep_low'] = (df['low'] < df['PDL']) & (df['close'] > df['PDL'])
    
    # Candlestick Patterns
    df['body_size'] = abs(df['close'] - df['open'])
    df['is_bullish_engulfing'] = (df['close'] > df['open']) & (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(1))
    df['is_bearish_engulfing'] = (df['close'] < df['open']) & (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(1))
    
    return df

def is_in_session(symbol, dt):
    hour = dt.hour
    if symbol in ["EURUSD", "GBPUSD"]: return 7 <= hour <= 18
    elif symbol in ["GOLD"]: return 13 <= hour <= 20
    elif symbol in ["USDJPY", "AUDUSD"]: return hour >= 22 or hour <= 8
    elif symbol in ["USDCAD", "BTCUSD", "ETHUSD"]: return 12 <= hour <= 20
    return True

def run_simulation(symbol, df, h1_map, h4_map):
    trades = []
    golden_count = 0
    base_risk = 0.01 
    rr = 2.5 
    
    cooldown = 0
    
    for i in range(50, len(df) - 10):
        if cooldown > 0:
            cooldown -= 1
            continue
            
        row = df.iloc[i]
        prev = df.iloc[i-1]
        t = row['time']
        hour = t.hour
        
        if not is_in_session(symbol, t): continue
        if symbol == "GOLD" and t.weekday() == 4: continue # Friday Veto
            
        date_hour = t.strftime('%Y-%m-%d %H')
        h1_trend = h1_map.get(date_hour, 'UNKNOWN')
        h4_trend = h4_map.get(date_hour, 'UNKNOWN')
        macro_trend = h4_trend if symbol == "GOLD" else h1_trend
        
        raw_signal = None
        
        # PERFECTED DNA LOGIC
        if symbol == "GOLD":
            # Liquidity Sweep + Engulfing Confirmation (High Probability)
            if prev['sweep_low'] and row['is_bullish_engulfing'] and macro_trend == 'BULLISH': 
                raw_signal = "BUY"
            elif prev['sweep_high'] and row['is_bearish_engulfing'] and macro_trend == 'BEARISH': 
                raw_signal = "SELL"
                
        elif symbol == "USDJPY":
            # 50-EMA Pullback + Engulfing Confirmation (Stops the chop over-trading)
            if macro_trend == 'BULLISH' and prev['low'] < prev['EMA_50'] and row['is_bullish_engulfing'] and row['close'] > row['EMA_50']:
                raw_signal = "BUY"
            elif macro_trend == 'BEARISH' and prev['high'] > prev['EMA_50'] and row['is_bearish_engulfing'] and row['close'] < row['EMA_50']:
                raw_signal = "SELL"
                
        elif symbol == "AUDUSD":
            # Asian Range Mean Reversion (Tight Range Trading)
            if row['RSI'] < 30 and row['close'] < row['Lower_BB'] and row['is_bullish_engulfing']:
                raw_signal = "BUY"
            elif row['RSI'] > 70 and row['close'] > row['Upper_BB'] and row['is_bearish_engulfing']:
                raw_signal = "SELL"
                
        else:
            # Baseline Standard Swarm
            if row['RSI'] < 30 and row['close'] < row['Lower_BB']: raw_signal = "BUY"
            elif row['RSI'] > 70 and row['close'] > row['Upper_BB']: raw_signal = "SELL"
            elif row['EMA_9'] > row['EMA_21'] and prev['EMA_9'] <= prev['EMA_21']: raw_signal = "BUY"
            elif row['EMA_9'] < row['EMA_21'] and prev['EMA_9'] >= prev['EMA_21']: raw_signal = "SELL"
            
        if not raw_signal: continue
            
        smc_approved = False
        if raw_signal == "BUY" and macro_trend == 'BULLISH' and row['close'] > df.iloc[i]['last_sl']: smc_approved = True
        elif raw_signal == "SELL" and macro_trend == 'BEARISH' and row['close'] < df.iloc[i]['last_sh']: smc_approved = True
                
        if not smc_approved: continue
        if row['ATR'] < row['ATR_MA_50']: continue
            
        sl_multiplier = 1.5 if (symbol == "GOLD" and 13 <= hour <= 16) else 0.2
            
        entry = row['close']
        sl = df.iloc[i]['last_sl'] - (row['ATR'] * sl_multiplier) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR'] * sl_multiplier)
        risk_dist = abs(entry - sl)
        if risk_dist <= 0: continue
        tp = entry + (risk_dist * rr) if raw_signal == "BUY" else entry - (risk_dist * rr)
        
        is_golden = (h1_trend == h4_trend)
        dollar_risk = 3000 * (base_risk * 2.5 if is_golden else base_risk)
        
        outcome = "PENDING"
        profit = 0
        
        for j in range(1, 60):
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
            if is_golden: golden_count += 1
            cooldown = 15 # Wait 15 candles after a trade completes before taking another (stops over-trading)
            
    return len(trades), golden_count, sum(trades)

def main():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    symbols = ["EURUSD", "GBPUSD", "GOLD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "ETHUSD"]
    
    results = []
    total_profit = 0
    for sym in symbols:
        h1_map, h4_map = get_macro_trends(sym)
        tf = mt5.TIMEFRAME_M15 if sym == "GOLD" else mt5.TIMEFRAME_M5
        df = load_data(sym, tf, 8000)
        if df is None or h1_map is None: continue
        
        df = calculate_indicators(df, swing_len=8)
        total_trades, golden, profit = run_simulation(sym, df, h1_map, h4_map)
        total_profit += profit
        
        results.append({
            "Symbol": sym,
            "Total Trades": total_trades,
            "Golden Setups": golden,
            "Net Profit": f"${profit:.2f}"
        })
        
    res_df = pd.DataFrame(results)
    print("=== PERFECTED DNA MODULE BACKTEST ===")
    print(res_df.to_string(index=False))
    print(f"\n[PORTFOLIO] Total Net Profit (1 Month): ${total_profit:.2f}")
    mt5.shutdown()

if __name__ == "__main__":
    main()
