import os
import glob
import pandas as pd
import numpy as np
import math
from concurrent.futures import ProcessPoolExecutor, as_completed

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
        try: return float(strike_str)
        except: return atm

def get_strike_str(offset):
    if offset == 0: return 'ATM'
    elif offset > 0: return f'ATM+{offset}'
    else: return f'ATM{offset}' # e.g. ATM-1

def process_file_stitching(fpath):
    # We will load the corresponding group of parquets to allow stitching
    # e.g. for SENSEX_expired_2026-04-01_2026-04-30_*
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    base_name = os.path.basename(fpath)
    # Parse contract details
    parts = base_name.split('_')
    if len(parts) < 5: return []
    idx_name = parts[0]
    ps = parts[2]
    pe = parts[3]
    otype = 'CALL' if 'CALL' in base_name else 'PUT'
    
    atm_steps = {'NIFTY': 50, 'BANKNIFTY': 100, 'FINNIFTY': 50, 'SENSEX': 100}
    atm_step = atm_steps.get(idx_name, 100)
    
    # Load all 7 strikes for this contract group
    strikes = ['ATM', 'ATM+1', 'ATM+2', 'ATM+3', 'ATM-1', 'ATM-2', 'ATM-3']
    strike_dfs = {}
    
    for s in strikes:
        fn = f"{idx_name}_expired_{ps}_{pe}_{s}_{otype}_1min_MONTH_1.parquet"
        fp = os.path.join(raw_dir, fn)
        if os.path.exists(fp):
            try:
                df = pd.read_parquet(fp)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['date'] = df['timestamp'].dt.date
                df_exp = df[df['date'] == df['date'].max()].copy().sort_values('timestamp').reset_index(drop=True)
                df_exp['hhmm'] = df_exp['timestamp'].dt.hour * 100 + df_exp['timestamp'].dt.minute
                strike_dfs[s] = df_exp.set_index('timestamp')
            except:
                pass
                
    if 'ATM' not in strike_dfs:
        return []
        
    atm_df = strike_dfs['ATM']
    results = []
    
    # Evaluate ZERO_HERO style trade: Buy ATM at 14:50 and hold
    # Let's check both CE and PE
    # We will simulate:
    # 1. Unstitched (Rolling ATM): Entry and exit from the same ATM parquet
    # 2. Stitched (Fixed Strike): Reconstructing the entry contract's price path
    
    entry_hhmm = 1450
    exit_hhmm = 1528
    
    rows_entry = atm_df[atm_df['hhmm'] == entry_hhmm]
    rows_exit = atm_df[atm_df['hhmm'] == exit_hhmm]
    
    if len(rows_entry) == 0 or len(rows_exit) == 0:
        return []
        
    ts_entry = rows_entry.index[0]
    ts_exit = rows_exit.index[0]
    
    entry_row = atm_df.loc[ts_entry]
    exit_row = atm_df.loc[ts_exit]
    
    entry_price_rolling = entry_row['close']
    exit_price_rolling = exit_row['close']
    
    # Lock the numerical strike at entry
    entry_spot = entry_row['spot']
    locked_strike = round(entry_spot / atm_step) * atm_step
    
    # Stitch price path
    # Find the price at exit time for the locked strike
    # The locked strike at exit corresponds to a relative offset:
    exit_spot = exit_row['spot']
    exit_atm = round(exit_spot / atm_step) * atm_step
    offset_at_exit = round((locked_strike - exit_atm) / atm_step)
    
    # Get the appropriate parquet for this offset
    strike_str_exit = get_strike_str(offset_at_exit)
    
    exit_price_stitched = np.nan
    if strike_str_exit in strike_dfs:
        exit_df = strike_dfs[strike_str_exit]
        if ts_exit in exit_df.index:
            exit_price_stitched = exit_df.loc[ts_exit, 'close']
            
    # Fallback if strike is out of range
    if np.isnan(exit_price_stitched) or offset_at_exit not in [-3, -2, -1, 0, 1, 2, 3]:
        # Estimate intrinsic value at exit
        if otype == 'CALL':
            exit_price_stitched = max(0.05, exit_spot - locked_strike)
        else:
            exit_price_stitched = max(0.05, locked_strike - exit_spot)
            
    pnl_rolling = exit_price_rolling - entry_price_rolling
    ret_rolling = pnl_rolling / entry_price_rolling * 100
    
    pnl_stitched = exit_price_stitched - entry_price_rolling
    ret_stitched = pnl_stitched / entry_price_rolling * 100
    
    return [{
        'file': base_name,
        'otype': otype,
        'entry_spot': entry_spot,
        'exit_spot': exit_spot,
        'strike': locked_strike,
        'entry_price': entry_price_rolling,
        'exit_rolling': exit_price_rolling,
        'exit_stitched': exit_price_stitched,
        'ret_rolling': ret_rolling,
        'ret_stitched': ret_stitched
    }]

def main():
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    # Find unique ATM CALL parquet files
    files = glob.glob(os.path.join(raw_dir, '*_ATM_CALL_1min_MONTH_1.parquet')) + \
            glob.glob(os.path.join(raw_dir, '*_ATM_PUT_1min_MONTH_1.parquet'))
            
    print(f"Scanning {len(files)} contracts for trade stitching analysis...")
    
    results = []
    with ProcessPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(process_file_stitching, f): f for f in files}
        for future in as_completed(futures):
            res = future.result()
            results.extend(res)
            
    df = pd.DataFrame(results)
    if df.empty:
        print("No trades simulated.")
        return
        
    print("\n" + "="*80)
    print("COMPARISON OF TRADE RETURNS (ENTRY 14:50 -> EXIT 15:28)")
    print("="*80)
    print(f"Total Trades Evaluated: {len(df)}")
    
    print("\nUNSTITCHED (ROLLING ATM):")
    print(f"  Average Return      : {df['ret_rolling'].mean():+.1f}%")
    print(f"  Win Rate (Return > 0): {(df['ret_rolling'] > 0).mean()*100:.1f}%")
    print(f"  Max Profit          : {df['ret_rolling'].max():.1f}%")
    
    print("\nSTITCHED (REAL FIXED STRIKE):")
    print(f"  Average Return      : {df['ret_stitched'].mean():+.1f}%")
    print(f"  Win Rate (Return > 0): {(df['ret_stitched'] > 0).mean()*100:.1f}%")
    print(f"  Max Profit          : {df['ret_stitched'].max():.1f}%")
    
    # Print the top 5 rolling profits vs their stitched reality
    print("\n" + "="*80)
    print("TOP 5 ROLLING JUMPS VS THEIR STITCHED REALITY")
    print("="*80)
    df_sorted = df.sort_values('ret_rolling', ascending=False)
    cols = ['file', 'otype', 'entry_price', 'exit_rolling', 'ret_rolling', 'exit_stitched', 'ret_stitched']
    print(df_sorted[cols].head(10).to_string(index=False))

if __name__ == '__main__':
    main()
