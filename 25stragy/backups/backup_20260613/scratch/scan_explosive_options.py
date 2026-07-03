import os
import glob
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

def scan_file_robust(fpath):
    try:
        df = pd.read_parquet(fpath)
        if df.empty:
            return []
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        expiry_date = df['date'].max()
        df_exp = df[df['date'] == expiry_date].copy()
        if len(df_exp) < 10:
            return []
        
        df_exp = df_exp.sort_values('timestamp').reset_index(drop=True)
        
        prices = df_exp['close'].values.astype(float)
        timestamps = df_exp['timestamp'].values
        spots = df_exp['spot'].values.astype(float)
        ois = df_exp['oi'].values.astype(float) if 'oi' in df_exp.columns else np.zeros(len(df_exp))
        ivs = df_exp['iv'].values.astype(float) if 'iv' in df_exp.columns else np.zeros(len(df_exp))
        
        n = len(prices)
        if n < 2:
            return []
            
        best_ratio = 1.0
        best_low_idx = -1
        best_high_idx = -1
        
        # O(N) Running minimum finder with constraints: 2.0 <= P1 <= 400.0
        run_min_val = float('inf')
        run_min_idx = -1
        
        for i in range(n):
            val = prices[i]
            
            # Check ratio if we have a valid prior minimum
            if run_min_idx != -1 and val > 0:
                ratio = val / run_min_val
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_low_idx = run_min_idx
                    best_high_idx = i
            
            # Update running minimum
            if 2.0 <= val <= 400.0:
                if val < run_min_val:
                    run_min_val = val
                    run_min_idx = i
                    
        if best_ratio >= 2.0 and best_low_idx != -1:
            low_val = prices[best_low_idx]
            high_val = prices[best_high_idx]
            low_time = pd.to_datetime(timestamps[best_low_idx])
            high_time = pd.to_datetime(timestamps[best_high_idx])
            
            spot_low = spots[best_low_idx]
            spot_high = spots[best_high_idx]
            spot_change_pct = 100.0 * (spot_high - spot_low) / spot_low
            
            oi_low = ois[best_low_idx]
            oi_high = ois[best_high_idx]
            oi_change_pct = 0.0
            if oi_low > 0:
                oi_change_pct = 100.0 * (oi_high - oi_low) / oi_low
                
            iv_low = ivs[best_low_idx]
            iv_high = ivs[best_high_idx]
            
            symbol = df_exp['symbol'].iloc[0] if 'symbol' in df_exp.columns else 'UNKNOWN'
            strike = df_exp['strike'].iloc[0]
            opt_type = df_exp['option_type'].iloc[0] if 'option_type' in df_exp.columns else ('CE' if 'CALL' in fpath else 'PE')
            
            index_name = 'UNKNOWN'
            for idx in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']:
                if idx in os.path.basename(fpath):
                    index_name = idx
                    break
            
            return [{
                'file': os.path.basename(fpath),
                'index': index_name,
                'expiry_date': str(expiry_date),
                'symbol': symbol,
                'strike': strike,
                'option_type': opt_type,
                'low_price': round(low_val, 2),
                'low_time': str(low_time.time()),
                'high_price': round(high_val, 2),
                'high_time': str(high_time.time()),
                'multiplier': round(best_ratio, 2),
                'spot_low': round(spot_low, 2),
                'spot_high': round(spot_high, 2),
                'spot_change_pct': round(spot_change_pct, 3),
                'oi_low': int(oi_low),
                'oi_high': int(oi_high),
                'oi_change_pct': round(oi_change_pct, 2),
                'iv_low': round(iv_low, 2),
                'iv_high': round(iv_high, 2),
            }]
    except Exception as e:
        pass
    return []

def main():
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    files = glob.glob(os.path.join(raw_dir, '*.parquet'))
    print(f"Starting robust scan of {len(files)} files...")
    
    results = []
    with ProcessPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(scan_file_robust, f): f for f in files}
        
        completed = 0
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.extend(res)
            completed += 1
            if completed % 500 == 0:
                print(f"Processed {completed}/{len(files)} files... Found {len(results)} jumps.")
                
    if results:
        df_res = pd.DataFrame(results)
        df_res.to_csv(r'C:\25stragy\scratch\expiry_jumps.csv', index=False)
        print(f"Scan complete! Saved {len(df_res)} jumps to C:\\25stragy\\scratch\\expiry_jumps.csv")
    else:
        print("No jumps found.")

if __name__ == '__main__':
    main()
