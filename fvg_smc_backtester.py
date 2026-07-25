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
    h4 = load_data(symbol, mt5.TIMEFRAME_H4, 500)
    if h4 is None: return None
    
    h4['EMA_50'] = h4['close'].ewm(span=50, adjust=False).mean()
    h4.set_index('time', inplace=True)
    h4 = h4.resample('1h').ffill().reset_index()
    h4['date_hour'] = h4['time'].dt.strftime('%Y-%m-%d %H')
    h4['macro_trend'] = np.where(h4['close'] > h4['EMA_50'], 'BULLISH', 'BEARISH')
    h4_map = dict(zip(h4['date_hour'], h4['macro_trend']))
    return h4_map

def find_fvg_trades():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    symbols = ["USDJPY", "AUDUSD", "GOLD"]
    
    results = []
    
    for sym in symbols:
        h4_map = get_macro_trends(sym)
        # We look for FVGs on the M15 chart as it provides the best intraday structural setups
        df = load_data(sym, mt5.TIMEFRAME_M15, 8000)
        if df is None or h4_map is None: continue
            
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['ATR'] = df['tr'].rolling(window=14).mean()
        
        # FVG Detection Logic
        df['bullish_fvg_top'] = np.nan
        df['bullish_fvg_bot'] = np.nan
        df['bearish_fvg_top'] = np.nan
        df['bearish_fvg_bot'] = np.nan
        
        # Array to store active FVGs
        active_bullish_fvgs = []
        active_bearish_fvgs = []
        
        trades = []
        golden_setups = 0
        cooldown = 0
        
        for i in range(50, len(df) - 10):
            row = df.iloc[i]
            prev1 = df.iloc[i-1]
            prev2 = df.iloc[i-2]
            
            # 1. IDENTIFY NEW FVGs
            # Bullish FVG: Low of current candle is higher than High of candle i-2
            if row['low'] > prev2['high'] and prev1['close'] > prev1['open']:
                active_bullish_fvgs.append({
                    'top': row['low'],
                    'bot': prev2['high'],
                    'mitigated': False,
                    'created_idx': i
                })
                
            # Bearish FVG: High of current candle is lower than Low of candle i-2
            if row['high'] < prev2['low'] and prev1['close'] < prev1['open']:
                active_bearish_fvgs.append({
                    'top': prev2['low'],
                    'bot': row['high'],
                    'mitigated': False,
                    'created_idx': i
                })
                
            # Keep only recent FVGs (last 50 candles) to avoid trading stale structure
            active_bullish_fvgs = [f for f in active_bullish_fvgs if not f['mitigated'] and (i - f['created_idx']) < 50]
            active_bearish_fvgs = [f for f in active_bearish_fvgs if not f['mitigated'] and (i - f['created_idx']) < 50]
            
            if cooldown > 0:
                cooldown -= 1
                continue
                
            t = row['time']
            date_hour = t.strftime('%Y-%m-%d %H')
            macro_trend = h4_map.get(date_hour, 'UNKNOWN')
            
            raw_signal = None
            fvg_zone = None
            
            # 2. TRADE EXECUTION: Price taps into an active FVG in the direction of the trend
            if macro_trend == 'BULLISH':
                for fvg in active_bullish_fvgs:
                    # If price dips into the FVG zone
                    if row['low'] <= fvg['top'] and row['close'] > fvg['bot']:
                        raw_signal = "BUY"
                        fvg_zone = fvg
                        fvg['mitigated'] = True # Mark as mitigated so we don't trade it again
                        break
                        
            elif macro_trend == 'BEARISH':
                for fvg in active_bearish_fvgs:
                    # If price spikes into the FVG zone
                    if row['high'] >= fvg['bot'] and row['close'] < fvg['top']:
                        raw_signal = "SELL"
                        fvg_zone = fvg
                        fvg['mitigated'] = True
                        break
                        
            if not raw_signal: continue
                
            entry = row['close']
            
            # Tight Stop-Loss just outside the FVG zone
            if raw_signal == "BUY":
                sl = fvg_zone['bot'] - (row['ATR'] * 0.5)
            else:
                sl = fvg_zone['top'] + (row['ATR'] * 0.5)
                
            risk_dist = abs(entry - sl)
            if risk_dist <= 0: continue
            
            # High 3.0 R:R because FVGs offer extreme precision
            tp = entry + (risk_dist * 3.0) if raw_signal == "BUY" else entry - (risk_dist * 3.0)
            
            dollar_risk = 30 # Base 1% risk
            outcome = "PENDING"
            profit = 0
            
            for j in range(1, 60):
                if i+j >= len(df): break
                fut = df.iloc[i+j]
                if raw_signal == "BUY":
                    if fut['low'] <= sl: outcome = "LOSS"; profit -= dollar_risk; break
                    if fut['high'] >= tp: outcome = "WIN"; profit += (dollar_risk * 3.0); break
                else:
                    if fut['high'] >= sl: outcome = "LOSS"; profit -= dollar_risk; break
                    if fut['low'] <= tp: outcome = "WIN"; profit += (dollar_risk * 3.0); break
                        
            if outcome != "PENDING":
                trades.append(profit)
                if profit > 0: golden_setups += 1
                cooldown = 10 # Wait before taking another trade
                
        net_profit = sum(trades)
        results.append({
            "Symbol": sym,
            "Total FVG Setups": len(trades),
            "Winning Trades": golden_setups,
            "Net Profit": f"${net_profit:.2f}"
        })
        
    res_df = pd.DataFrame(results)
    print("=== PURE SMC (FAIR VALUE GAP) MODULE RESULTS ===")
    print(res_df.to_string(index=False))
    mt5.shutdown()

if __name__ == "__main__":
    find_fvg_trades()
