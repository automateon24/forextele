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

def run_combined_simulation():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    symbols = ["EURUSD", "GBPUSD", "USDCAD", "BTCUSD", "ETHUSD", "GOLD", "AUDUSD", "USDJPY"]
    
    results = []
    total_profit = 0
    
    for sym in symbols:
        h1_map, h4_map = get_macro_trends(sym)
        df = load_data(sym, mt5.TIMEFRAME_M15 if sym in ["GOLD", "AUDUSD"] else mt5.TIMEFRAME_M5, 8000)
        if df is None: continue
            
        df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['STD_20'] = df['close'].rolling(window=20).std()
        df['Upper_BB'] = df['SMA_20'] + (df['STD_20'] * 2)
        df['Lower_BB'] = df['SMA_20'] - (df['STD_20'] * 2)
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
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
        
        # FVG Detection
        active_bullish_fvgs = []
        active_bearish_fvgs = []
        
        trades = []
        golden_setups = 0
        cooldown = 0
        
        for i in range(50, len(df) - 10):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            prev2 = df.iloc[i-2]
            t = row['time']
            hour = t.hour
            
            # FVG Updating
            if sym in ["GOLD", "AUDUSD"]:
                if row['low'] > prev2['high'] and prev['close'] > prev['open']:
                    active_bullish_fvgs.append({'top': row['low'], 'bot': prev2['high'], 'mitigated': False, 'idx': i})
                if row['high'] < prev2['low'] and prev['close'] < prev['open']:
                    active_bearish_fvgs.append({'top': prev2['low'], 'bot': row['high'], 'mitigated': False, 'idx': i})
                active_bullish_fvgs = [f for f in active_bullish_fvgs if not f['mitigated'] and (i - f['idx']) < 50]
                active_bearish_fvgs = [f for f in active_bearish_fvgs if not f['mitigated'] and (i - f['idx']) < 50]
                
            if cooldown > 0:
                cooldown -= 1
                continue
                
            date_hour = t.strftime('%Y-%m-%d %H')
            h1_trend = h1_map.get(date_hour, 'UNKNOWN')
            h4_trend = h4_map.get(date_hour, 'UNKNOWN')
            macro_trend = h4_trend if sym in ["GOLD", "AUDUSD"] else h1_trend
            
            raw_signal = None
            sl, tp = 0, 0
            
            # --- 1. GOLD & AUDUSD (PURE SMC FVG) ---
            if sym in ["GOLD", "AUDUSD"]:
                fvg_zone = None
                if macro_trend == 'BULLISH':
                    for fvg in active_bullish_fvgs:
                        if row['low'] <= fvg['top'] and row['close'] > fvg['bot']:
                            raw_signal = "BUY"
                            fvg_zone = fvg
                            fvg['mitigated'] = True
                            break
                elif macro_trend == 'BEARISH':
                    for fvg in active_bearish_fvgs:
                        if row['high'] >= fvg['bot'] and row['close'] < fvg['top']:
                            raw_signal = "SELL"
                            fvg_zone = fvg
                            fvg['mitigated'] = True
                            break
                
                if raw_signal:
                    entry = row['close']
                    sl = fvg_zone['bot'] - (row['ATR'] * 0.5) if raw_signal == "BUY" else fvg_zone['top'] + (row['ATR'] * 0.5)
                    risk_dist = abs(entry - sl)
                    if risk_dist <= 0: continue
                    tp = entry + (risk_dist * 3.0) if raw_signal == "BUY" else entry - (risk_dist * 3.0)
                    
            # --- 2. USDJPY (NY VOLATILITY BREAKOUT - FROM MATRIX) ---
            elif sym == "USDJPY":
                if 13 <= hour <= 20: # NY Session ONLY
                    if row['close'] > df.iloc[i]['last_sh'] and prev['close'] <= prev['last_sh']: raw_signal = "BUY"
                    elif row['close'] < df.iloc[i]['last_sl'] and prev['close'] >= prev['last_sl']: raw_signal = "SELL"
                    
                if raw_signal:
                    if raw_signal == "BUY" and macro_trend != 'BULLISH': raw_signal = None
                    if raw_signal == "SELL" and macro_trend != 'BEARISH': raw_signal = None
                    if row['ATR'] < row['ATR_MA']: raw_signal = None
                    
                    if raw_signal:
                        entry = row['close']
                        sl = df.iloc[i]['last_sl'] - (row['ATR'] * 0.2) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR'] * 0.2)
                        risk_dist = abs(entry - sl)
                        tp = entry + (risk_dist * 2.5) if raw_signal == "BUY" else entry - (risk_dist * 2.5)
                        
            # --- 3. FOREX/CRYPTO (45-STRATEGY SWARM) ---
            else:
                if row['RSI'] < 30 and row['close'] < row['Lower_BB']: raw_signal = "BUY"
                elif row['RSI'] > 70 and row['close'] > row['Upper_BB']: raw_signal = "SELL"
                elif row['EMA_9'] > row['EMA_21'] and prev['EMA_9'] <= prev['EMA_21']: raw_signal = "BUY"
                elif row['EMA_9'] < row['EMA_21'] and prev['EMA_9'] >= prev['EMA_21']: raw_signal = "SELL"
                
                if raw_signal:
                    if raw_signal == "BUY" and macro_trend != 'BULLISH': raw_signal = None
                    if raw_signal == "SELL" and macro_trend != 'BEARISH': raw_signal = None
                    if row['close'] <= df.iloc[i]['last_sl'] and raw_signal == "BUY": raw_signal = None
                    if row['close'] >= df.iloc[i]['last_sh'] and raw_signal == "SELL": raw_signal = None
                    if row['ATR'] < row['ATR_MA']: raw_signal = None
                        
                    if raw_signal:
                        entry = row['close']
                        sl = df.iloc[i]['last_sl'] - (row['ATR'] * 0.2) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR'] * 0.2)
                        risk_dist = abs(entry - sl)
                        tp = entry + (risk_dist * 2.5) if raw_signal == "BUY" else entry - (risk_dist * 2.5)
                        
            if not raw_signal: continue
                
            is_golden = (h1_trend == h4_trend) and (sym not in ["GOLD", "AUDUSD", "USDJPY"])
            dollar_risk = 3000 * (0.025 if is_golden else 0.01)
            if sym in ["GOLD", "AUDUSD"]: dollar_risk = 30 # Standard 1% for FVG
            if sym == "USDJPY": dollar_risk = 30
            
            outcome = "PENDING"
            profit = 0
            
            for j in range(1, 60):
                if i+j >= len(df): break
                fut = df.iloc[i+j]
                if raw_signal == "BUY":
                    if fut['low'] <= sl: outcome = "LOSS"; profit -= dollar_risk; break
                    if fut['high'] >= tp: 
                        rr_mult = 3.0 if sym in ["GOLD", "AUDUSD"] else 2.5
                        outcome = "WIN"; profit += (dollar_risk * rr_mult); break
                else:
                    if fut['high'] >= sl: outcome = "LOSS"; profit -= dollar_risk; break
                    if fut['low'] <= tp: 
                        rr_mult = 3.0 if sym in ["GOLD", "AUDUSD"] else 2.5
                        outcome = "WIN"; profit += (dollar_risk * rr_mult); break
                        
            if outcome != "PENDING":
                trades.append(profit)
                if profit > 0: golden_setups += 1
                cooldown = 10
                
        net_profit = sum(trades)
        total_profit += net_profit
        
        status = "🔒 Locked: Standard Swarm"
        if sym in ["GOLD", "AUDUSD"]: status = "🚀 Locked: FVG SMC"
        if sym == "USDJPY": status = "🔧 Locked: NY Volatility Matrix"
            
        results.append({
            "Symbol": sym,
            "Total Trades": len(trades),
            "Wins/Golden": golden_setups,
            "Net Profit": f"${net_profit:.2f}",
            "Engine Architecture": status
        })
        
    res_df = pd.DataFrame(results)
    print("=== ULTIMATE COMBINED PORTFOLIO ARCHITECTURE (FINAL) ===")
    print(res_df.to_string(index=False))
    print(f"\n[PORTFOLIO] Total Realized Net Profit (30 Days): ${total_profit:.2f}")
    mt5.shutdown()

if __name__ == "__main__":
    run_combined_simulation()
