import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime

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

def calculate_indicators(df, swing_len=8):
    df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
    df['last_sh'] = df['high'].where(df['swing_high']).ffill()
    df['last_sl'] = df['low'].where(df['swing_low']).ffill()
    
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['ATR'] = df['tr'].rolling(window=14).mean()

    df['choch_bull'] = (df['close'] > df['last_sh'].shift(1)) & (df['close'].shift(1) <= df['last_sh'].shift(2))
    df['choch_bear'] = (df['close'] < df['last_sl'].shift(1)) & (df['close'].shift(1) >= df['last_sl'].shift(2))
    
    return df

def is_in_session(symbol, dt):
    hour = dt.hour
    if symbol in ["EURUSD", "GBPUSD", "GOLD"]: return 7 <= hour <= 18
    elif symbol in ["USDJPY", "AUDUSD"]: return hour >= 22 or hour <= 8
    elif symbol in ["USDCAD", "BTCUSD", "ETHUSD"]: return 12 <= hour <= 20
    return True

def backtest_optimizer(df, h1_trend_map, symbol, use_tsl):
    trades = []
    rr = 2.5 
    
    for i in range(50, len(df) - 10):
        row = df.iloc[i]
        if not is_in_session(symbol, row['time']): continue
            
        date_hour = row['time'].strftime('%Y-%m-%d %H')
        macro_trend = h1_trend_map.get(date_hour, 'UNKNOWN')
        
        signal = None
        sl = 0
        tp = 0
        
        # Strategy 1: SMC Trend Continuation (41 Strategy Logic)
        if row['choch_bull'] and macro_trend == 'BULLISH':
            signal = "BUY"
            sl = df.iloc[i]['last_sl'] - (row['ATR'] * 0.5)
        elif row['choch_bear'] and macro_trend == 'BEARISH':
            signal = "SELL"
            sl = df.iloc[i]['last_sh'] + (row['ATR'] * 0.5)
            
        if signal:
            entry = row['close']
            risk = abs(entry - sl)
            if risk <= 0: continue
            
            if signal == "BUY": tp = entry + (risk * rr)
            else: tp = entry - (risk * rr)
                
            outcome = "PENDING"
            tsl = sl
            breakeven_triggered = False
            
            for j in range(1, 60):
                if i+j >= len(df): break
                fut = df.iloc[i+j]
                
                if signal == "BUY":
                    if use_tsl and not breakeven_triggered and fut['high'] >= entry + risk:
                        # Move to Break-even + offset for swap/commission
                        tsl = entry + (row['ATR'] * 0.1)
                        breakeven_triggered = True
                        
                    if fut['low'] <= tsl: 
                        outcome = "BREAKEVEN" if breakeven_triggered else "LOSS"
                        break
                    if fut['high'] >= tp: 
                        outcome = "WIN"
                        break
                else:
                    if use_tsl and not breakeven_triggered and fut['low'] <= entry - risk:
                        # Move to Break-even - offset for swap/commission
                        tsl = entry - (row['ATR'] * 0.1)
                        breakeven_triggered = True
                        
                    if fut['high'] >= tsl: 
                        outcome = "BREAKEVEN" if breakeven_triggered else "LOSS"
                        break
                    if fut['low'] <= tp: 
                        outcome = "WIN"
                        break
            
            if outcome != "PENDING": trades.append(outcome)
                
    wins = trades.count("WIN")
    losses = trades.count("LOSS")
    be = trades.count("BREAKEVEN")
    # PnL Calculation in terms of R
    pnl = (wins * rr) - losses
    return len(trades), pnl

def main():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    symbols = ["EURUSD", "GBPUSD", "GOLD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "ETHUSD"]
    bars = 8000 # ~1 Month of M5 data
    
    results = []
    
    for sym in symbols:
        h1_trend_map = get_h1_trend(sym)
        df = load_data(sym, mt5.TIMEFRAME_M5, bars)
        if df is None or h1_trend_map is None: continue
        
        df = calculate_indicators(df, swing_len=8)
        
        # Enforce No TSL
        total_no, pnl_no = backtest_optimizer(df, h1_trend_map, sym, use_tsl=False)
        
        results.append({
            "Symbol": sym,
            "1 Month SMC Trades": total_no,
            "PnL (NO TSL) [R]": f"{pnl_no:.1f}R",
            "Win Rate Approx": f"{((pnl_no + total_no) / (total_no * 3.5) * 100) if total_no > 0 else 0:.1f}%"
        })
        
    res_df = pd.DataFrame(results)
    print("=== PURE 41 STRATEGY (SMC ONLY) | NO TSL | 1 MONTH BACKTEST ===")
    print(res_df.to_string(index=False))
    mt5.shutdown()

if __name__ == "__main__":
    main()
