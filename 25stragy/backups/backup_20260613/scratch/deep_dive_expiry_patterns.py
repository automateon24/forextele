import os
import glob
import pandas as pd
import numpy as np
import math
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Math helpers for Greeks
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
        
        # Theta
        term1 = -(S * norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
        term2 = r * K * math.exp(-r * T)
        if option_type == 'CE':
            theta = term1 - term2 * norm_cdf(d2)
        else:
            theta = term1 + term2 * norm_cdf(-d2)
            
        return delta, gamma, vega, theta / 365.0
    except Exception as e:
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

def analyze_spike_patterns():
    jumps_csv = r'C:\25stragy\scratch\expiry_jumps.csv'
    if not os.path.exists(jumps_csv):
        print("expiry_jumps.csv not found.")
        return
        
    df_jumps = pd.read_csv(jumps_csv)
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    
    print(f"Loaded {len(df_jumps)} jumps to analyze...")
    
    atm_steps = {'NIFTY': 50, 'BANKNIFTY': 100, 'FINNIFTY': 50, 'SENSEX': 100}
    records = []
    
    for idx, row in df_jumps.iterrows():
        fpath = os.path.join(raw_dir, row['file'])
        if not os.path.exists(fpath):
            continue
            
        # Determine index
        idx_name = 'UNKNOWN'
        for k in atm_steps.keys():
            if k in row['file']:
                idx_name = k
                break
        if idx_name == 'UNKNOWN':
            continue
            
        atm_step = atm_steps[idx_name]
        
        try:
            df = pd.read_parquet(fpath)
            if df.empty:
                continue
                
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            
            expiry_date = df['date'].max()
            df_exp = df[df['date'] == expiry_date].copy().sort_values('timestamp').reset_index(drop=True)
            
            low_time = pd.to_datetime(str(expiry_date) + ' ' + row['low_time'])
            
            low_idx_series = df_exp[df_exp['timestamp'] == low_time].index
            if len(low_idx_series) == 0:
                continue
            low_idx = low_idx_series[0]
            
            df_exp['hour'] = df_exp['timestamp'].dt.hour
            df_exp['minute'] = df_exp['timestamp'].dt.minute
            df_exp['minutes_left'] = (15 - df_exp['hour']) * 60 + (30 - df_exp['minute'])
            df_exp.loc[df_exp['minutes_left'] <= 0, 'minutes_left'] = 1.0
            df_exp['T_years'] = df_exp['minutes_left'] / (365 * 24 * 60)
            
            df_exp['sigma'] = df_exp['iv'] / 100.0
            df_exp['spot_change_3m'] = df_exp['spot'].pct_change(3) * 100
            df_exp['spot_change_5m'] = df_exp['spot'].pct_change(5) * 100
            
            if 'oi' in df_exp.columns:
                df_exp['oi_change_5m'] = df_exp['oi'].pct_change(5) * 100
            else:
                df_exp['oi_change_5m'] = 0.0
                
            df_exp['vol_ma5'] = df_exp['volume'].rolling(5).mean()
            df_exp['vol_spike'] = df_exp['volume'] / df_exp['vol_ma5'].replace(0, 1)
            
            deltas, gammas, vegas, thetas = [], [], [], []
            opt_type = row['option_type']
            strike_str = row['strike']
            
            for k, r in df_exp.iterrows():
                K = get_numeric_strike(r['spot'], strike_str, atm_step)
                d, g, v, th = calculate_greeks(r['spot'], K, r['T_years'], r['sigma'], opt_type)
                deltas.append(d)
                gammas.append(g)
                vegas.append(v)
                thetas.append(th)
                
            df_exp['delta'] = deltas
            df_exp['gamma'] = gammas
            df_exp['vega'] = vegas
            df_exp['theta'] = thetas
            
            offsets = {'T-10': -10, 'T-5': -5, 'T-0': 0, 'T+5': 5, 'T+15': 15}
            event_data = {
                'file': row['file'],
                'multiplier': row['multiplier'],
                'option_type': opt_type,
            }
            
            for name, offset in offsets.items():
                target_idx = low_idx + offset
                if 0 <= target_idx < len(df_exp):
                    r_target = df_exp.iloc[target_idx]
                    event_data[f'{name}_price'] = r_target['close']
                    event_data[f'{name}_delta'] = r_target['delta']
                    event_data[f'{name}_gamma'] = r_target['gamma']
                    event_data[f'{name}_theta'] = r_target['theta']
                    event_data[f'{name}_iv'] = r_target['iv']
                    event_data[f'{name}_spot_chg_3m'] = r_target['spot_change_3m']
                    event_data[f'{name}_oi_chg_5m'] = r_target['oi_change_5m']
                    event_data[f'{name}_vol_spike'] = r_target['vol_spike']
                else:
                    event_data[f'{name}_price'] = np.nan
                    event_data[f'{name}_delta'] = np.nan
                    event_data[f'{name}_gamma'] = np.nan
                    event_data[f'{name}_theta'] = np.nan
                    event_data[f'{name}_iv'] = np.nan
                    event_data[f'{name}_spot_chg_3m'] = np.nan
                    event_data[f'{name}_oi_chg_5m'] = np.nan
                    event_data[f'{name}_vol_spike'] = np.nan
                    
            records.append(event_data)
        except Exception as e:
            pass
            
    df_patterns = pd.DataFrame(records)
    df_10x = df_patterns[df_patterns['multiplier'] >= 10.0]
    
    print("\n" + "="*80)
    print("AVERAGE METRICS FOR 10x+ MONSTER SPIKES AT T-0 (ENTRY MOMENT):")
    print("="*80)
    print(f"  Low Price              : {df_10x['T-0_price'].mean():.2f}")
    print(f"  Delta                  : {df_10x['T-0_delta'].mean():.4f}")
    print(f"  Gamma                  : {df_10x['T-0_gamma'].mean():.6f}")
    print(f"  Theta (Daily Decay)    : {df_10x['T-0_theta'].mean():.2f}")
    print(f"  Implied Volatility (IV): {df_10x['T-0_iv'].mean():.1f}%")
    print(f"  3-Min Spot Velocity    : {df_10x['T-0_spot_chg_3m'].mean():.4f}%")
    print(f"  5-Min OI Change        : {df_10x['T-0_oi_chg_5m'].mean():.2f}%")
    print(f"  Volume Spike Factor    : {df_10x['T-0_vol_spike'].mean():.2f}x")

    print("\n" + "="*80)
    print("TIMELINE PROFILE OF A 10x+ MONSTER JUMP:")
    print("="*80)
    stages = ['T-10', 'T-5', 'T-0', 'T+5', 'T+15']
    for s in stages:
        p = df_10x[f'{s}_price'].mean()
        d = df_10x[f'{s}_delta'].mean()
        g = df_10x[f'{s}_gamma'].mean()
        o = df_10x[f'{s}_oi_chg_5m'].mean()
        v = df_10x[f'{s}_vol_spike'].mean()
        s_chg = df_10x[f'{s}_spot_chg_3m'].mean()
        print(f"  {s:<5} | Price: {p:>6.2f} | Delta: {d:>7.4f} | Gamma: {g:>8.6f} | 3m Spot Chg: {s_chg:>+7.4f}% | 5m OI Chg: {o:>+6.1f}% | Vol Spike: {v:>5.1f}x")

def test_predictive_rules():
    print("\n" + "="*80)
    print("BACKTESTING PREDICTIVE TRIGGER RULES ON EXPIRY DAYS")
    print("="*80)
    
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    # Select a subset of ATM and ATM+-1 parquets across NIFTY and SENSEX to verify
    files = glob.glob(os.path.join(raw_dir, '*_ATM_*_1min_MONTH_1.parquet')) + \
            glob.glob(os.path.join(raw_dir, '*_ATM+1_*_1min_MONTH_1.parquet')) + \
            glob.glob(os.path.join(raw_dir, '*_ATM-1_*_1min_MONTH_1.parquet'))
            
    atm_steps = {'NIFTY': 50, 'BANKNIFTY': 100, 'FINNIFTY': 50, 'SENSEX': 100}
    
    # Let's parallelize the rule evaluation
    trades_rule_a = []
    trades_rule_b = []
    trades_rule_c = []
    
    def process_file_rules(fpath):
        ta, tb, tc = [], [], []
        try:
            df = pd.read_parquet(fpath)
            if df.empty: return ta, tb, tc
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            
            # Use expiry day
            expiry_date = df['date'].max()
            df_exp = df[df['date'] == expiry_date].copy().sort_values('timestamp').reset_index(drop=True)
            if len(df_exp) < 20: return ta, tb, tc
            
            idx_name = 'UNKNOWN'
            for k in atm_steps.keys():
                if k in fpath: idx_name = k; break
            if idx_name == 'UNKNOWN': return ta, tb, tc
            
            atm_step = atm_steps[idx_name]
            
            # Indicators
            df_exp['hour'] = df_exp['timestamp'].dt.hour
            df_exp['minute'] = df_exp['timestamp'].dt.minute
            df_exp['hhmm'] = df_exp['hour'] * 100 + df_exp['minute']
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
            
            # Max 5-period price high
            df_exp['price_high5'] = df_exp['close'].rolling(5).max()
            
            # Greeks
            deltas, gammas = [], []
            opt_type = 'CE' if 'CALL' in fpath else 'PE'
            strike_str = 'ATM'
            if 'ATM+1' in fpath: strike_str = 'ATM+1'
            elif 'ATM-1' in fpath: strike_str = 'ATM-1'
            
            for k, r in df_exp.iterrows():
                K = get_numeric_strike(r['spot'], strike_str, atm_step)
                d, g, _, _ = calculate_greeks(r['spot'], K, r['T_years'], r['sigma'], opt_type)
                deltas.append(d)
                gammas.append(g)
                
            df_exp['delta'] = deltas
            df_exp['gamma'] = gammas
            
            # Trade evaluation
            def simulate_trade(entry_idx, entry_price):
                # Target = 5x entry (400% gain)
                # Stop Loss = 0.5x entry (50% loss)
                target = entry_price * 5.0
                stop_loss = entry_price * 0.5
                for j in range(entry_idx + 1, len(df_exp)):
                    high = df_exp.loc[j, 'high']
                    low = df_exp.loc[j, 'low']
                    close = df_exp.loc[j, 'close']
                    
                    if low <= stop_loss:
                        return stop_loss - entry_price # Loss
                    if high >= target:
                        return target - entry_price # Hit target (5x!)
                        
                # If neither hit, exit at market close
                return df_exp.iloc[-1]['close'] - entry_price
            
            # Evaluate each row
            # Filter trading window: 14:45 to 15:20
            # To avoid multiple duplicate trades, once we trigger we block triggers for 20 minutes
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
                # CE needs spot rising, PE needs spot falling
                spot_cond = (opt_type == 'CE' and r['spot_change_3m'] >= 0.08) or (opt_type == 'PE' and r['spot_change_3m'] <= -0.08)
                if spot_cond and r['vol_spike'] >= 3.0 and hhmm > blocked_until_a:
                    pnl = simulate_trade(i, price)
                    ta.append(pnl / price) # Return as percentage of entry
                    blocked_until_a = hhmm + 20
                    
                # Rule B: OI Unwinding + Price Breakout
                # 5m OI drops by >= 5%, option price breaks out of 5-period high
                oi_cond = r['oi_change_5m'] <= -5.0
                price_cond = price >= df_exp.loc[i-1, 'price_high5']
                if oi_cond and price_cond and hhmm > blocked_until_b:
                    pnl = simulate_trade(i, price)
                    tb.append(pnl / price)
                    blocked_until_b = hhmm + 20
                    
                # Rule C: Gamma Threshold + Spot Momentum
                # Gamma >= 0.005, Spot moves by 0.06%
                gamma_cond = r['gamma'] >= 0.005
                spot_cond_c = (opt_type == 'CE' and r['spot_change_3m'] >= 0.06) or (opt_type == 'PE' and r['spot_change_3m'] <= -0.06)
                if gamma_cond and spot_cond_c and hhmm > blocked_until_c:
                    pnl = simulate_trade(i, price)
                    tc.append(pnl / price)
                    blocked_until_c = hhmm + 20
                    
        except Exception as e:
            pass
        return ta, tb, tc

    print(f"Scanning {len(files)} parquets for expiry triggers...")
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_file_rules, f): f for f in files[:200]} # Scan a representative sample of 200 files
        
        completed = 0
        for future in as_completed(futures):
            ta, tb, tc = future.result()
            trades_rule_a.extend(ta)
            trades_rule_b.extend(tb)
            trades_rule_c.extend(tc)
            completed += 1
            
    # Report performance of the three rules
    for name, trades in [("RULE A (Spot Velocity + Vol Spike)", trades_rule_a),
                         ("RULE B (OI Unwinding + Price Breakout)", trades_rule_b),
                         ("RULE C (Greeks Gamma + Spot Momentum)", trades_rule_c)]:
        print(f"\n{name}:")
        if not trades:
            print("  No trades triggered.")
            continue
        trades_np = np.array(trades)
        wins = trades_np[trades_np > 0]
        hits_5x = trades_np[trades_np >= 4.0] # 5x target means +400% return
        
        win_rate = 100 * len(wins) / len(trades)
        hit_5x_rate = 100 * len(hits_5x) / len(trades)
        avg_ret = trades_np.mean() * 100
        
        print(f"  Total Trades Triggered: {len(trades)}")
        print(f"  Win Rate (End Green)  : {win_rate:.1f}%")
        print(f"  5x Target Hit Rate    : {hit_5x_rate:.1f}% (Success Ratio for Multi-Baggers)")
        print(f"  Average Trade Return  : {avg_ret:+.1f}%")

if __name__ == '__main__':
    analyze_spike_patterns()
    test_predictive_rules()
