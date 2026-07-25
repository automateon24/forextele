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

def calculate_swarm_indicators(df, swing_len=8):
    # 1. SMC Structure (The Guide)
    df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
    df['last_sh'] = df['high'].where(df['swing_high']).ffill()
    df['last_sl'] = df['low'].where(df['swing_low']).ffill()
    
    # 2. Base Strategies (Representing the 45 DNA)
    # Strategy 1: RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Strategy 2: Bollinger Bands
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    df['STD_20'] = df['close'].rolling(window=20).std()
    df['Upper_BB'] = df['SMA_20'] + (df['STD_20'] * 2)
    df['Lower_BB'] = df['SMA_20'] - (df['STD_20'] * 2)
    
    # Strategy 3: Moving Average Crossover (Fast Momentum)
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    # Risk Management
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['ATR'] = df['tr'].rolling(window=14).mean()
    df['ATR_MA_50'] = df['ATR'].rolling(window=50).mean() # Volatility Filter to avoid chop
    
    return df

def is_in_session(symbol, dt):
    hour = dt.hour
    if symbol in ["EURUSD", "GBPUSD", "GOLD"]: return 7 <= hour <= 18
    elif symbol in ["USDJPY", "AUDUSD"]: return hour >= 22 or hour <= 8
    elif symbol in ["USDCAD", "BTCUSD", "ETHUSD"]: return 12 <= hour <= 20
    return True

def backtest_guided_swarm(df, h1_trend_map, symbol, starting_capital=3000):
    trades = []
    capital = starting_capital
    risk_per_trade_pct = 0.01 # 1% Risk
    rr = 2.5 
    
    for i in range(50, len(df) - 10):
        row = df.iloc[i]
        
        # 1. TIME ZONE FILTER
        if not is_in_session(symbol, row['time']): continue
            
        date_hour = row['time'].strftime('%Y-%m-%d %H')
        macro_trend = h1_trend_map.get(date_hour, 'UNKNOWN')
        
        raw_signal = None
        
        # 2. THE 45 STRATEGIES (Generating Raw Signals)
        # Strat A: Mean Reversion
        if row['RSI'] < 30 and row['close'] < row['Lower_BB']: raw_signal = "BUY"
        elif row['RSI'] > 70 and row['close'] > row['Upper_BB']: raw_signal = "SELL"
        # Strat B: EMA Momentum
        elif row['EMA_9'] > row['EMA_21'] and df.iloc[i-1]['EMA_9'] <= df.iloc[i-1]['EMA_21']: raw_signal = "BUY"
        elif row['EMA_9'] < row['EMA_21'] and df.iloc[i-1]['EMA_9'] >= df.iloc[i-1]['EMA_21']: raw_signal = "SELL"
        
        if not raw_signal: continue
            
        # 3. SMC GUIDANCE (The Veto)
        # We only take the strategy signal IF it aligns with SMC Structure
        smc_approved = False
        if raw_signal == "BUY" and macro_trend == 'BULLISH' and row['close'] > df.iloc[i]['last_sl']:
            smc_approved = True
        elif raw_signal == "SELL" and macro_trend == 'BEARISH' and row['close'] < df.iloc[i]['last_sh']:
            smc_approved = True
            
        if not smc_approved: continue
            
        # 3.5 VOLATILITY FILTER (Kill the Failing Patterns)
        # If current ATR is below the 50-period average ATR, the market is compressing.
        # Breakouts and CHOCHs here are likely fake-outs.
        if row['ATR'] < row['ATR_MA_50']:
            continue
            
        # 4. EXECUTION
        entry = row['close']
        sl = df.iloc[i]['last_sl'] - (row['ATR'] * 0.2) if raw_signal == "BUY" else df.iloc[i]['last_sh'] + (row['ATR'] * 0.2)
        risk_dist = abs(entry - sl)
        if risk_dist <= 0: continue
        
        tp = entry + (risk_dist * rr) if raw_signal == "BUY" else entry - (risk_dist * rr)
        
        # Calculate $ Risk
        dollar_risk = capital * risk_per_trade_pct
        
        outcome = "PENDING"
        for j in range(1, 60):
            if i+j >= len(df): break
            fut = df.iloc[i+j]
            
            if raw_signal == "BUY":
                if fut['low'] <= sl: 
                    outcome = "LOSS"
                    capital -= dollar_risk
                    break
                if fut['high'] >= tp: 
                    outcome = "WIN"
                    capital += (dollar_risk * rr)
                    break
            else:
                if fut['high'] >= sl: 
                    outcome = "LOSS"
                    capital -= dollar_risk
                    break
                if fut['low'] <= tp: 
                    outcome = "WIN"
                    capital += (dollar_risk * rr)
                    break
                    
        if outcome != "PENDING":
            trades.append(outcome)
            
    wins = trades.count("WIN")
    losses = trades.count("LOSS")
    total = len(trades)
    win_rate = (wins / total * 100) if total > 0 else 0
    net_profit = capital - starting_capital
    
    return total, win_rate, net_profit, capital

def main():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    symbols = ["EURUSD", "GBPUSD", "GOLD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSD", "ETHUSD"]
    bars = 8000 # ~1 Month of M5 data
    
    results = []
    
    # Shared Capital Pool
    shared_capital = 3000.0
    risk_dollars = shared_capital * 0.01 # Fixed $30 risk per trade to simulate shared pool sizing
    
    portfolio_net_profit = 0
    total_portfolio_trades = 0
    
    for sym in symbols:
        h1_trend_map = get_h1_trend(sym)
        df = load_data(sym, mt5.TIMEFRAME_M5, bars)
        if df is None or h1_trend_map is None: continue
        
        df = calculate_swarm_indicators(df, swing_len=8)
        
        # We pass risk_dollars instead of capital to simulate flat risk across the shared pool
        trades = []
        pair_profit = 0
        rr = 2.5
        
        for i in range(50, len(df) - 10):
            row = df.iloc[i]
            if not is_in_session(sym, row['time']): continue
            date_hour = row['time'].strftime('%Y-%m-%d %H')
            macro_trend = h1_trend_map.get(date_hour, 'UNKNOWN')
            
            raw_signal = None
            if row['RSI'] < 30 and row['close'] < row['Lower_BB']: raw_signal = "BUY"
            elif row['RSI'] > 70 and row['close'] > row['Upper_BB']: raw_signal = "SELL"
            elif row['EMA_9'] > row['EMA_21'] and df.iloc[i-1]['EMA_9'] <= df.iloc[i-1]['EMA_21']: raw_signal = "BUY"
            elif row['EMA_9'] < row['EMA_21'] and df.iloc[i-1]['EMA_9'] >= df.iloc[i-1]['EMA_21']: raw_signal = "SELL"
            
            if not raw_signal: continue
                
            smc_approved = False
            if raw_signal == "BUY" and macro_trend == 'BULLISH' and row['close'] > df.iloc[i]['last_sl']: smc_approved = True
            elif raw_signal == "SELL" and macro_trend == 'BEARISH' and row['close'] < df.iloc[i]['last_sh']: smc_approved = True
                
            if not smc_approved: continue
            if row['ATR'] < row['ATR_MA_50']: continue # Avoid failing chop patterns
                
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
                    if fut['low'] <= sl: outcome = "LOSS"; pair_profit -= risk_dollars; break
                    if fut['high'] >= tp: outcome = "WIN"; pair_profit += (risk_dollars * rr); break
                else:
                    if fut['high'] >= sl: outcome = "LOSS"; pair_profit -= risk_dollars; break
                    if fut['low'] <= tp: outcome = "WIN"; pair_profit += (risk_dollars * rr); break
                        
            if outcome != "PENDING": trades.append(outcome)
                
        wins = trades.count("WIN")
        total = len(trades)
        win_rate = (wins / total * 100) if total > 0 else 0
        
        portfolio_net_profit += pair_profit
        total_portfolio_trades += total
        
        results.append({
            "Symbol": sym,
            "Trades (Filtered)": total,
            "Win Rate (1:2.5)": f"{win_rate:.1f}%",
            "Net Profit (Shared)": f"${pair_profit:.2f}"
        })
        
    res_df = pd.DataFrame(results)
    print("=== FINAL SWARM | SHARED $3000 CAPITAL | VOLATILITY FILTER ===")
    print(res_df.to_string(index=False))
    print(f"\n[PORTFOLIO] Total Trades: {total_portfolio_trades}")
    print(f"[PORTFOLIO] Total Net Profit (1 Month): ${portfolio_net_profit:.2f}")
    print(f"[PORTFOLIO] End Shared Balance: ${shared_capital + portfolio_net_profit:.2f} (Starting: $3000.00)")
    mt5.shutdown()

if __name__ == "__main__":
    main()
