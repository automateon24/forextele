import pandas as pd
import numpy as np
import os
import math

def norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
def norm_pdf(x):
    return math.exp(-0.5 * x**2) / math.sqrt(2.0 * math.pi)

def calculate_greeks(S, K, T, sigma, option_type, r=0.07):
    T = max(T, 1e-6)
    sigma = max(sigma, 1e-4)
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        delta = norm_cdf(d1) if option_type == 'CE' else norm_cdf(d1) - 1.0
        gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
        return delta, gamma
    except:
        return 0.0, 0.0

def main():
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    # Find the SENSEX file for 2026-04-30.
    # The file could be like SENSEX_expired_2026-04-01_2026-04-30_ATM_PUT_1min_MONTH_1.parquet or similar
    # Let's search for files matching SENSEX*2026-04-30*
    files = [f for f in os.listdir(raw_dir) if 'SENSEX' in f and '2026-04-30' in f]
    print("Found files:", files)
    
    for f in files:
        if 'ATM_PUT' not in f and 'ATM-1_PUT' not in f:
            continue
        print("\n" + "="*80)
        print("ANALYZING FILE:", f)
        print("="*80)
        
        df = pd.read_parquet(os.path.join(raw_dir, f))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        expiry_date = df['date'].max()
        df_exp = df[df['date'] == expiry_date].copy().sort_values('timestamp').reset_index(drop=True)
        
        df_exp['hour'] = df_exp['timestamp'].dt.hour
        df_exp['minute'] = df_exp['timestamp'].dt.minute
        df_exp['hhmm'] = df_exp['hour'] * 100 + df_exp['minute']
        
        # Spot changes and rolling volume
        df_exp['spot_chg_3m'] = df_exp['spot'].pct_change(3) * 100
        df_exp['vol_ma5'] = df_exp['volume'].rolling(5).mean()
        df_exp['vol_spike'] = df_exp['volume'] / df_exp['vol_ma5'].replace(0, 1)
        if 'oi' in df_exp.columns:
            df_exp['oi_change_5m'] = df_exp['oi'].pct_change(5) * 100
        else:
            df_exp['oi_change_5m'] = 0.0
            
        # Greeks
        df_exp['minutes_left'] = (15 - df_exp['hour']) * 60 + (30 - df_exp['minute'])
        df_exp.loc[df_exp['minutes_left'] <= 0, 'minutes_left'] = 1.0
        df_exp['T'] = df_exp['minutes_left'] / (365 * 24 * 60)
        
        opt_type = 'CE' if 'CALL' in f else 'PE'
        strike_str = 'ATM'
        if 'ATM-1' in f: strike_str = 'ATM-1'
        
        deltas, gammas = [], []
        for k, r in df_exp.iterrows():
            K = round(r['spot'] / 100) * 100
            if strike_str == 'ATM-1':
                K = K - 100
            d, g = calculate_greeks(r['spot'], K, r['T'], r['iv']/100.0, opt_type)
            deltas.append(d)
            gammas.append(g)
        df_exp['delta'] = deltas
        df_exp['gamma'] = gammas
        
        # Print slice around 15:00 to 15:30
        print_df = df_exp[(df_exp['hhmm'] >= 1500) & (df_exp['hhmm'] <= 1530)]
        cols = ['timestamp', 'close', 'spot', 'spot_chg_3m', 'volume', 'vol_spike', 'oi', 'oi_change_5m', 'iv', 'delta', 'gamma']
        print(print_df[cols].to_string(index=False))

if __name__ == '__main__':
    main()
