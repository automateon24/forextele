import os
import glob
import pandas as pd
import numpy as np
import math
from concurrent.futures import ProcessPoolExecutor, as_completed

def norm_cdf(x):
    try:
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
    except:
        return 0.5 if x > 0 else -0.5

def norm_pdf(x):
    try:
        return math.exp(-0.5 * x**2) / math.sqrt(2.0 * math.pi)
    except:
        return 0.0

def calculate_greeks(S, K, T, sigma, option_type, r=0.07):
    T = max(T, 1e-6)
    sigma = max(sigma, 1e-4)
    S = max(S, 1e-4)
    K = max(K, 1e-4)
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        delta = norm_cdf(d1) if option_type == 'CE' else norm_cdf(d1) - 1.0
        gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
        vega = S * norm_pdf(d1) * math.sqrt(T)
        term1 = -(S * norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
        term2 = r * K * math.exp(-r * T)
        theta = (term1 - term2 * norm_cdf(d2)) if option_type == 'CE' else (term1 + term2 * norm_cdf(-d2))
        return delta, gamma, vega, theta / 365.0
    except:
        return 0.0, 0.0, 0.0, 0.0

def get_numeric_strike(spot, strike_str, atm_step):
    atm = round(spot / atm_step) * atm_step
    if strike_str == 'ATM':
        return atm
    elif strike_str.startswith('ATM+'):
        offset = int(strike_str.replace('ATM+', ''))
        return atm + offset * atm_step
    elif strike_str.startswith('ATM-'):
        offset = int(strike_str.replace('ATM-', ''))
        return atm - offset * atm_step
    else:
        try:
            return float(strike_str)
        except:
            return atm

def process_file(fpath):
    ta, tb, tc = [], [], []
    try:
        df = pd.read_parquet(fpath)
        if df.empty:
            return ta, tb, tc
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # Expiry day only
        expiry_date = df['date'].max()
        df_exp = df[df['date'] == expiry_date].copy().sort_values('timestamp').reset_index(drop=True)
        if len(df_exp) < 30:
            return ta, tb, tc
            
        # Check if there are any cheap rows in the trading window
        df_exp['hour'] = df_exp['timestamp'].dt.hour
        df_exp['minute'] = df_exp['timestamp'].dt.minute
        df_exp['hhmm'] = df_exp['hour'] * 100 + df_exp['minute']
        
        window_df = df_exp[(df_exp['hhmm'] >= 1445) & (df_exp['hhmm'] <= 1520)]
        if window_df.empty or window_df['close'].min() > 25.0 or window_df['close'].max() < 2.0:
            return ta, tb, tc
            
        # Determine index
        atm_steps = {'NIFTY': 50, 'BANKNIFTY': 100, 'FINNIFTY': 50, 'SENSEX': 100}
        idx_name = 'UNKNOWN'
        for k in atm_steps.keys():
            if k in fpath:
                idx_name = k
                break
        if idx_name == 'UNKNOWN':
            return ta, tb, tc
            
        atm_step = atm_steps[idx_name]
        
        # Calculate Indicators
        df_exp['minutes_left'] = (15 - df_exp['hour']) * 60 + (30 - df_exp['minute'])
        df_exp.loc[df_exp['minutes_left'] <= 0, 'minutes_left'] = 1.0
        df_exp['T_years'] = df_exp['minutes_left'] / (365 * 24 * 60)
        
        df_exp['sigma'] = df_exp['iv'] / 100.0
        df_exp['spot_change_3m'] = df_exp['spot'].pct_change(3) * 100
        
        if 'oi' in df_exp.columns:
            df_exp['oi_change_5m'] = df_exp['oi'].pct_change(5) * 100
        else:
            df_exp['oi_change_5m'] = 0.0
            
        df_exp['vol_ma5'] = df_exp['volume'].rolling(5).mean()
        df_exp['vol_spike'] = df_exp['volume'] / df_exp['vol_ma5'].replace(0, 1)
        df_exp['price_high5'] = df_exp['close'].rolling(5).max()
        
        # Greeks
        deltas, gammas = [], []
        opt_type = 'CE' if 'CALL' in fpath else 'PE'
        strike_str = 'ATM'
        for offset_str in ['ATM+1', 'ATM+2', 'ATM+3', 'ATM-1', 'ATM-2', 'ATM-3']:
            if offset_str in fpath:
                strike_str = offset_str
                break
                
        for k, r in df_exp.iterrows():
            K = get_numeric_strike(r['spot'], strike_str, atm_step)
            d, g, _, _ = calculate_greeks(r['spot'], K, r['T_years'], r['sigma'], opt_type)
            deltas.append(d)
            gammas.append(g)
            
        df_exp['delta'] = deltas
        df_exp['gamma'] = gammas
        
        def simulate_trade(entry_idx, entry_price):
            target = entry_price * 5.0
            stop_loss = entry_price * 0.5
            for j in range(entry_idx + 1, len(df_exp)):
                high = df_exp.loc[j, 'high']
                low = df_exp.loc[j, 'low']
                if low <= stop_loss:
                    return stop_loss - entry_price
                if high >= target:
                    return target - entry_price
            return df_exp.iloc[-1]['close'] - entry_price

        blocked_until_a = 0
        blocked_until_b = 0
        blocked_until_c = 0
        
        for i in range(5, len(df_exp)):
            r = df_exp.iloc[i]
            hhmm = r['hhmm']
            if hhmm < 1445 or hhmm > 1520:
                continue
                
            price = r['close']
            if not (2.0 <= price <= 25.0):
                continue
                
            # Rule A: Spot Velocity + Volume Spike
            spot_cond = (opt_type == 'CE' and r['spot_change_3m'] >= 0.05) or (opt_type == 'PE' and r['spot_change_3m'] <= -0.05)
            if spot_cond and r['vol_spike'] >= 2.5 and hhmm > blocked_until_a:
                pnl = simulate_trade(i, price)
                ta.append(pnl / price)
                blocked_until_a = hhmm + 20
                
            # Rule B: OI Unwinding + Price Breakout
            oi_cond = r['oi_change_5m'] <= -5.0
            price_cond = price >= df_exp.loc[i-1, 'price_high5']
            if oi_cond and price_cond and hhmm > blocked_until_b:
                pnl = simulate_trade(i, price)
                tb.append(pnl / price)
                blocked_until_b = hhmm + 20
                
            # Rule C: Gamma Threshold + Spot Momentum
            gamma_cond = r['gamma'] >= 0.003
            spot_cond_c = (opt_type == 'CE' and r['spot_change_3m'] >= 0.04) or (opt_type == 'PE' and r['spot_change_3m'] <= -0.04)
            if gamma_cond and spot_cond_c and hhmm > blocked_until_c:
                pnl = simulate_trade(i, price)
                tc.append(pnl / price)
                blocked_until_c = hhmm + 20
                
    except Exception as e:
        pass
    return ta, tb, tc

def main():
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    files = glob.glob(os.path.join(raw_dir, '*.parquet'))
    print(f"Starting parallel scan of {len(files)} parquets...")
    
    trades_a, trades_b, trades_c = [], [], []
    
    with ProcessPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        
        completed = 0
        for future in as_completed(futures):
            ta, tb, tc = future.result()
            trades_a.extend(ta)
            trades_b.extend(tb)
            trades_c.extend(tc)
            completed += 1
            if completed % 1000 == 0:
                print(f"Processed {completed}/{len(files)} files...")
                
    print("\n" + "="*80)
    print("EXPIRY DAY PREDICTIVE TRIGGERS BACKTEST RESULTS:")
    print("="*80)
    
    for name, trades in [("RULE A (Spot Velocity + Vol Spike)", trades_a),
                         ("RULE B (OI Unwinding + Price Breakout)", trades_b),
                         ("RULE C (Greeks Gamma + Spot Momentum)", trades_c)]:
        print(f"\n{name}:")
        if not trades:
            print("  No trades triggered.")
            continue
        trades_np = np.array(trades)
        wins = trades_np[trades_np > 0]
        hits_5x = trades_np[trades_np >= 4.0] # 5x target is +400%
        
        win_rate = 100 * len(wins) / len(trades)
        hit_5x_rate = 100 * len(hits_5x) / len(trades)
        avg_ret = trades_np.mean() * 100
        
        print(f"  Total Trades Triggered: {len(trades)}")
        print(f"  Win Rate (End Green)  : {win_rate:.1f}%")
        print(f"  5x Target Hit Rate    : {hit_5x_rate:.1f}% (Multi-Bagger Success Rate)")
        print(f"  Average Trade Return  : {avg_ret:+.1f}%")

if __name__ == '__main__':
    main()
