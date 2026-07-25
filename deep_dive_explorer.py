import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime

def load_data(symbol, timeframe, bars):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['body'] = abs(df['close'] - df['open'])
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['ATR'] = df['tr'].rolling(14).mean()
    df['ATR_MA_50'] = df['ATR'].rolling(50).mean()
    return df

def get_macro_trend_map(df):
    # Calculate Macro trend dynamically using 200 EMA & 50 EMA on the loaded bars
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['trend'] = np.where(df['EMA_50'] > df['EMA_200'], 'BULLISH', 'BEARISH')
    return df['trend'].tolist()

def calculate_swarm_indicators(df, swing_len=6):
    df['is_sh'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['is_sl'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()
    df['sh_level'] = np.where(df['is_sh'], df['high'], np.nan)
    df['sl_level'] = np.where(df['is_sl'], df['low'], np.nan)
    df['last_sh'] = pd.Series(df['sh_level']).ffill()
    df['last_sl'] = pd.Series(df['sl_level']).ffill()
    
    # FVG
    df['bull_fvg_cand'] = (df['low'] > df['high'].shift(2)) & (df['close'] > df['open']) & (df['body'] >= df['ATR'] * 0.8)
    df['bull_fvg_top'] = np.where(df['bull_fvg_cand'], df['low'], np.nan)
    df['active_bull_fvg'] = pd.Series(df['bull_fvg_top']).ffill()
    
    df['bear_fvg_cand'] = (df['high'] < df['low'].shift(2)) & (df['close'] < df['open']) & (df['body'] >= df['ATR'] * 0.8)
    df['bear_fvg_bot'] = np.where(df['bear_fvg_cand'], df['high'], np.nan)
    df['active_bear_fvg'] = pd.Series(df['bear_fvg_bot']).ffill()
    
    # Order Blocks
    df['impulse_up'] = (df['close'] > df['open']) & (df['body'] >= df['ATR'] * 1.0)
    df['bull_ob_cand'] = (df['close'].shift(1) < df['open'].shift(1)) & df['impulse_up']
    df['bull_ob_level'] = np.where(df['bull_ob_cand'], df['low'].shift(1), np.nan)
    df['active_bull_ob'] = pd.Series(df['bull_ob_level']).ffill()
    
    df['impulse_down'] = (df['close'] < df['open']) & (df['body'] >= df['ATR'] * 1.0)
    df['bear_ob_cand'] = (df['close'].shift(1) > df['open'].shift(1)) & df['impulse_down']
    df['bear_ob_level'] = np.where(df['bear_ob_cand'], df['high'].shift(1), np.nan)
    df['active_bear_ob'] = pd.Series(df['bear_ob_level']).ffill()
    
    # 40 Strategy Base Indicators
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    df['STD_20'] = df['close'].rolling(window=20).std()
    df['Upper_BB'] = df['SMA_20'] + (df['STD_20'] * 2)
    df['Lower_BB'] = df['SMA_20'] - (df['STD_20'] * 2)
    
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    df['swing_eq'] = (df['last_sh'] + df['last_sl']) / 2.0
    df['in_discount'] = df['close'] <= df['swing_eq']
    df['in_premium'] = df['close'] >= df['swing_eq']
    
    df['bull_sweep'] = (df['low'] < df['last_sl']) & (df['close'] > df['last_sl']) & (df['close'] > df['open'])
    df['bear_sweep'] = (df['high'] > df['last_sh']) & (df['close'] < df['last_sh']) & (df['close'] < df['open'])
    
    return df

def is_in_session(symbol, dt):
    hour = dt.hour
    if any(s in symbol for s in ["EUR", "GBP", "CHF"]): 
        return 7 <= hour <= 17
    elif any(s in symbol for s in ["GOLD", "XAU", "SILVER", "XAG"]):
        return 7 <= hour <= 20
    elif any(s in symbol for s in ["JPY"]): 
        return (hour >= 23 or hour <= 8) or (12 <= hour <= 17)
    elif any(s in symbol for s in ["AUD", "NZD"]): 
        return hour >= 21 or hour <= 7
    elif any(s in symbol for s in ["CAD"]): 
        return 13 <= hour <= 20
    elif any(s in symbol for s in ["BTC", "ETH", "CRYPTO"]): 
        return 11 <= hour <= 22
    return True

def simulate_strategy_option_a(df, symbol, tf_name, starting_capital=1500.0):
    trades = []
    capital = starting_capital
    risk_per_trade_pct = 0.02 # Institutional 2% risk per trade
    
    sym_info = mt5.symbol_info(symbol)
    if not sym_info: return 0, 0, 0.0, capital, 0.0
    
    # Adaptive Risk-Reward ratio depending on timeframe and asset vol
    if tf_name in ["M30", "H1"]:
        rr = 1.5  # Higher timeframes travel further effortlessly
    elif any(s in symbol for s in ["GOLD", "XAU", "SILVER", "XAG", "GBPJPY"]):
        rr = 1.0  # High impulsive scalar dollar volatility
    elif any(s in symbol for s in ["BTC", "ETH"]):
        rr = 1.3  # Crypto expansion target
    else:
        rr = 1.15 # Currency pair fee clearing target
        
    atr_sl_mult = 3.0 # Impenetrable 3.0 ATR institutional stop buffer
    
    typical_active_spreads = {
        "EURUSD": 8, "GBPUSD": 12, "GOLD": 25, "XAUUSD": 25, "SILVER": 20, "XAGUSD": 20,
        "USDJPY": 12, "AUDUSD": 10, "USDCAD": 15, "USDCHF": 14, "GBPJPY": 20, "EURJPY": 16,
        "BTCUSD": 3500, "ETHUSD": 200, "AUDCAD": 18
    }
    spread_points = typical_active_spreads.get(symbol, sym_info.spread)
    point = sym_info.point
    tick_val = sym_info.trade_tick_value
    tick_size = sym_info.trade_tick_size
    spread_val = spread_points * point
    
    swap_long = sym_info.swap_long if getattr(sym_info, 'swap_long', None) is not None else -2.5
    swap_short = sym_info.swap_short if getattr(sym_info, 'swap_short', None) is not None else -2.5
    commission_per_lot = 7.00
    
    macro_trends = get_macro_trend_map(df)
    
    max_capital = capital
    max_drawdown = 0.0
    
    for i in range(50, len(df) - 10):
        row = df.iloc[i]
        if not is_in_session(symbol, row['time']): continue
        macro_trend = macro_trends[i]
        
        raw_signal = None
        
        # Enable all 3 strategy families except simple mean reversion on short Crypto M5
        if not (any(s in symbol for s in ["BTC", "ETH"]) and tf_name == "M5"):
            if row['RSI'] < 35 and row['close'] <= row['Lower_BB']: raw_signal = "BUY"
            elif row['RSI'] > 65 and row['close'] >= row['Upper_BB']: raw_signal = "SELL"
            
        if not raw_signal:
            if row['EMA_9'] > row['EMA_21'] and df.iloc[i-1]['EMA_9'] <= df.iloc[i-1]['EMA_21']: raw_signal = "BUY"
            elif row['EMA_9'] < row['EMA_21'] and df.iloc[i-1]['EMA_9'] >= df.iloc[i-1]['EMA_21']: raw_signal = "SELL"
            
        if not raw_signal:
            if row['close'] > df.iloc[i-1]['last_sh'] and row['body'] > row['ATR']: raw_signal = "BUY"
            elif row['close'] < df.iloc[i-1]['last_sl'] and row['body'] > row['ATR']: raw_signal = "SELL"
            
        if not raw_signal: continue
        
        atr = row['ATR']
        if not atr or np.isnan(atr) or atr == 0: continue
        
        ai_score = 20.0 # Base algorithmic signal from 40 Strategy array
        
        if raw_signal == "BUY":
            if macro_trend == 'BULLISH': ai_score += 15.0
            if row.get('in_discount', False): ai_score += 15.0
            ob_support = not np.isnan(row['active_bull_ob']) and abs(row['low'] - row['active_bull_ob']) <= (atr * 3.5)
            fvg_support = not np.isnan(row['active_bull_fvg']) and row['low'] <= (row['active_bull_fvg'] + atr) and row['low'] >= (row['active_bull_fvg'] - atr * 3.5)
            if ob_support or fvg_support: ai_score += 30.0
            if row.get('bull_sweep', False) or df.iloc[i-1].get('bull_sweep', False): ai_score += 20.0
            if row['ATR'] >= row['ATR_MA_50'] * 0.85: ai_score += 10.0
            if row['close'] <= row['last_sl']: ai_score -= 30.0
        else:
            if macro_trend == 'BEARISH': ai_score += 15.0
            if row.get('in_premium', False): ai_score += 15.0
            ob_resist = not np.isnan(row['active_bear_ob']) and abs(row['high'] - row['active_bear_ob']) <= (atr * 3.5)
            fvg_resist = not np.isnan(row['active_bear_fvg']) and row['high'] >= (row['active_bear_fvg'] - atr) and row['high'] <= (row['active_bear_fvg'] + atr * 3.5)
            if ob_resist or fvg_resist: ai_score += 30.0
            if row.get('bear_sweep', False) or df.iloc[i-1].get('bear_sweep', False): ai_score += 20.0
            if row['ATR'] >= row['ATR_MA_50'] * 0.85: ai_score += 10.0
            if row['close'] >= row['last_sh']: ai_score -= 30.0

        # Mandatory SMC Zone and 75% AI Confluence Veto (Option A Logic)
        has_smc_zone = (raw_signal == "BUY" and (not np.isnan(row['active_bull_ob']) or not np.isnan(row['active_bull_fvg'])) and (abs(row['low'] - row['active_bull_ob']) <= (atr * 3.5) or (row['low'] <= (row['active_bull_fvg'] + atr) and row['low'] >= (row['active_bull_fvg'] - atr * 3.5)))) or (raw_signal == "SELL" and (not np.isnan(row['active_bear_ob']) or not np.isnan(row['active_bear_fvg'])) and (abs(row['high'] - row['active_bear_ob']) <= (atr * 3.5) or (row['high'] >= (row['active_bear_fvg'] - atr) and row['high'] <= (row['active_bear_fvg'] + atr * 3.5))))
        if not has_smc_zone or ai_score < 75.0:
            continue
            
        chart_close = row['close']
        if raw_signal == "BUY":
            entry = chart_close + spread_val
            sl = df.iloc[i]['last_sl'] - (row['ATR'] * atr_sl_mult)
            risk_dist = chart_close - sl
            if risk_dist <= 0: continue
            tp = entry + (risk_dist * rr)
        else:
            entry = chart_close
            sl = df.iloc[i]['last_sh'] + (row['ATR'] * atr_sl_mult)
            risk_dist = sl - chart_close
            if risk_dist <= 0: continue
            tp = entry - (risk_dist * rr)
            
        if spread_val > (risk_dist * 0.15): continue
        
        dollar_risk = capital * risk_per_trade_pct
        risk_dist_points = risk_dist / point
        if risk_dist_points <= 0: continue
        point_value = (tick_val / tick_size) * point
        if point_value == 0: point_value = 1.0
        
        lots = max(0.01, round(dollar_risk / (risk_dist_points * point_value), 2))
        
        outcome = "PENDING"
        profit_usd = 0.0
        
        for j in range(1, 60):
            if i+j >= len(df): break
            fut = df.iloc[i+j]
            if raw_signal == "BUY":
                if fut['low'] <= sl:
                    outcome = "LOSS"
                    profit_usd = ((sl - entry) / point) * point_value * lots
                    break
                elif fut['high'] >= tp:
                    outcome = "WIN"
                    profit_usd = ((tp - entry) / point) * point_value * lots
                    break
            else:
                ask_high = fut['high'] + spread_val
                ask_low = fut['low'] + spread_val
                if ask_high >= sl:
                    outcome = "LOSS"
                    profit_usd = ((entry - sl) / point) * point_value * lots
                    break
                elif ask_low <= tp:
                    outcome = "WIN"
                    profit_usd = ((entry - tp) / point) * point_value * lots
                    break
                    
        if outcome != "PENDING":
            profit_usd -= (commission_per_lot * lots)
            if fut['time'].day != row['time'].day:
                swap_rate = swap_long if raw_signal == "BUY" else swap_short
                swap_usd = (swap_rate * point_value * lots) if swap_rate != 0 else (lots * -2.50)
                profit_usd += swap_usd
            capital += profit_usd
            trades.append("WIN" if profit_usd > 0 else "LOSS")
            if capital > max_capital: max_capital = capital
            drawdown = max_capital - capital
            if drawdown > max_drawdown: max_drawdown = drawdown
            
    total = len(trades)
    win_rate = (trades.count("WIN") / total * 100) if total > 0 else 0
    net_profit = capital - starting_capital
    return total, win_rate, net_profit, capital, max_drawdown

def main():
    mt5.initialize(login=int(json.load(open('mt5_config.json'))['login']), server=json.load(open('mt5_config.json'))['server'], password=json.load(open('mt5_config.json'))['password'])
    
    target_symbols = [
        "GOLD", "XAUUSD", "SILVER", "XAGUSD", "BTCUSD", "ETHUSD", 
        "EURUSD", "GBPUSD", "USDCAD", "USDJPY", "AUDUSD", "USDCHF", 
        "GBPJPY", "EURJPY", "AUDCAD"
    ]
    
    # Filter to only symbols existing and available on the user's MT5 server!
    available_symbols = []
    for s in target_symbols:
        if mt5.symbol_info(s) is not None:
            if s not in available_symbols and not (s == "XAUUSD" and "GOLD" in available_symbols) and not (s == "XAGUSD" and "SILVER" in available_symbols):
                available_symbols.append(s)
                
    timeframes = [
        ("M5", mt5.TIMEFRAME_M5, 7500),
        ("M15", mt5.TIMEFRAME_M15, 2500),
        ("M30", mt5.TIMEFRAME_M30, 1250),
        ("H1", mt5.TIMEFRAME_H1, 625)
    ]
    
    print(f"--- DEEP DIVE EXPLORATION: Testing {len(available_symbols)} Symbols across M5, M15, M30, and H1 Timeframes ---")
    print("Strategy Option A Engine: 75% AI Confluence Veto + Mandatory Order Block/FVG + 3.0 ATR Stop Buffer.\n")
    
    results = []
    
    for sym in available_symbols:
        for tf_name, tf_code, bar_count in timeframes:
            df = load_data(sym, tf_code, bar_count)
            if df is None or len(df) < 200: continue
            df = calculate_swarm_indicators(df, swing_len=6)
            total, win_rate, net_profit, end_cap, max_dd = simulate_strategy_option_a(df, sym, tf_name, 1500.0)
            
            if total > 0:
                results.append({
                    "Symbol": sym,
                    "Timeframe": tf_name,
                    "Trades": total,
                    "Win Rate": f"{win_rate:.1f}%",
                    "Net Profit ($)": round(net_profit, 2),
                    "Monthly ROI (%)": f"{(net_profit / 1500.0 * 100):.1f}%",
                    "Daily Avg Profit ($)": f"${(net_profit / 22.0):.2f}",
                    "Max Drawdown ($)": f"${round(max_dd, 2)}"
                })
                
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        # Sort by highest Net Profit ($) to reveal all hidden superstar winners!
        results_df = results_df.sort_values(by="Net Profit ($)", ascending=False)
        print("--- TOP PERFORMING COMBINATIONS ACROSS ALL SYMBOLS & TIMEFRAMES ---")
        print(results_df.to_string(index=False))
    else:
        print("No trades triggered.")

if __name__ == "__main__":
    main()
