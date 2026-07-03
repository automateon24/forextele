import pandas as pd
import numpy as np
import os

def main():
    raw_dir = 'c:/cursor/options/niftyopt/data/raw'
    
    # We will load SENSEX parquets for 2026-04-30:
    # 1. ATM PUT
    # 2. ATM-1 PUT (which is 1 strike below ATM)
    # 3. ATM+2 PUT (which is 2 strikes above ATM)
    # 4. ATM+2 CALL
    # 5. ATM-1 CALL
    # 6. ATM CALL
    
    date_str = '2026-04-30'
    
    def load_day_data(strike, otype):
        fname = f"SENSEX_expired_2026-04-01_2026-04-30_{strike}_{otype}_1min_MONTH_1.parquet"
        fpath = os.path.join(raw_dir, fname)
        if not os.path.exists(fpath):
            return None
        df = pd.read_parquet(fpath)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df_day = df[df['date'] == pd.to_datetime(date_str).date()].copy().sort_values('timestamp').reset_index(drop=True)
        df_day['hhmm'] = df_day['timestamp'].dt.hour * 100 + df_day['timestamp'].dt.minute
        return df_day

    atm_put = load_day_data('ATM', 'PUT')
    atm_minus1_put = load_day_data('ATM-1', 'PUT')
    atm_plus2_put = load_day_data('ATM+2', 'PUT')
    
    atm_call = load_day_data('ATM', 'CALL')
    atm_minus1_call = load_day_data('ATM-1', 'CALL')
    atm_plus2_call = load_day_data('ATM+2', 'CALL')

    print("="*80)
    print("SENSEX EXPIRY 2026-04-30 DETAILED STRIKE-ROLL DIAGNOSIS")
    print("="*80)
    
    # 1. Show the PUT case
    print("\n[CASE 1] PUT OPTIONS: Entry at 15:09 -> Exit at 15:27 (Index went UP from 76,835 to 77,059)")
    print("-" * 80)
    
    # Entry prices at 15:09
    p_atm_put_entry = atm_put[atm_put['hhmm'] == 1509]['close'].iloc[0]
    p_plus2_put_entry = atm_plus2_put[atm_plus2_put['hhmm'] == 1509]['close'].iloc[0]
    
    # Exit prices at 15:27
    p_atm_put_exit = atm_put[atm_put['hhmm'] == 1527]['close'].iloc[0]
    p_minus1_put_exit = atm_minus1_put[atm_minus1_put['hhmm'] == 1527]['close'].iloc[0]
    
    print(f"Backtest Simulated Trade (Rolling ATM):")
    print(f"  Bought ATM_PUT at 15:09 for : Rs. {p_atm_put_entry:.2f}")
    print(f"  Sold ATM_PUT at 15:27 for   : Rs. {p_atm_put_exit:.2f}")
    print(f"  Simulated Return            : +{((p_atm_put_exit - p_atm_put_entry)/p_atm_put_entry)*100:.1f}% (Rs. {p_atm_put_exit - p_atm_put_entry:+.2f} pts)")
    
    print(f"\nReal-World Fixed-Strike Trades:")
    print(f"  A. If you bought the 76,800 PUT (which was ATM at 15:09, priced at Rs. {p_atm_put_entry:.2f}):")
    print(f"     At 15:27, spot is 77,059. This 76,800 PUT is deep OTM.")
    print(f"     It expires worthless at  : Rs. 0.05")
    print(f"     Real Return              : -98.8% (Rs. {-p_atm_put_entry:+.2f} pts - TOTAL LOSS)")
    
    print(f"\n  B. If you bought the 77,000 PUT (which was ATM+2 at 15:09, priced at Rs. {p_plus2_put_entry:.2f}):")
    print(f"     At 15:27, spot is 77,059. This contract is now ATM-1 PUT (priced at Rs. {p_minus1_put_exit:.2f})")
    print(f"     Sold 77,000 PUT at 15:27 : Rs. {p_minus1_put_exit:.2f}")
    print(f"     Real Return              : {((p_minus1_put_exit - p_plus2_put_entry)/p_plus2_put_entry)*100:.1f}% (Rs. {p_minus1_put_exit - p_plus2_put_entry:+.2f} pts)")

    # 2. Show the CALL case
    print("\n" + "="*80)
    print("[CASE 2] CALL OPTIONS: Entry at 15:09 -> Exit at 15:27 (Index went UP from 76,835 to 77,059)")
    print("-" * 80)
    
    # Entry prices at 15:09
    p_atm_call_entry = atm_call[atm_call['hhmm'] == 1509]['close'].iloc[0]
    p_plus2_call_entry = atm_plus2_call[atm_plus2_call['hhmm'] == 1509]['close'].iloc[0] # 77,000 CALL
    
    # Exit prices at 15:27
    p_atm_call_exit = atm_call[atm_call['hhmm'] == 1527]['close'].iloc[0]
    p_minus1_call_exit = atm_minus1_call[atm_minus1_call['hhmm'] == 1527]['close'].iloc[0] # 77,000 CALL
    
    print(f"Backtest Simulated Trade (Rolling ATM):")
    print(f"  Bought ATM_CALL at 15:09 for: Rs. {p_atm_call_entry:.2f}")
    print(f"  Sold ATM_CALL at 15:27 for  : Rs. {p_atm_call_exit:.2f}")
    print(f"  Simulated Return            : {((p_atm_call_exit - p_atm_call_entry)/p_atm_call_entry)*100:.1f}% (Rs. {p_atm_call_exit - p_atm_call_entry:+.2f} pts)")
    
    print(f"\nReal-World Fixed-Strike Trades:")
    print(f"  A. If you bought the 76,800 CALL (which was ATM at 15:09, priced at Rs. {p_atm_call_entry:.2f}):")
    print(f"     At 15:27, spot is 77,059. This contract is ITM by 259 points. Its price is deep ITM (approx Rs. 260).")
    print(f"     Real Return              : +420.0% (Massive real win!)")
    
    print(f"\n  B. If you bought the 77,000 CALL (which was ATM+2 at 15:09, priced at Rs. {p_plus2_call_entry:.2f}):")
    print(f"     At 15:27, spot is 77,059. This contract is now ATM-1 CALL (priced at Rs. {p_minus1_call_exit:.2f})")
    print(f"     Sold 77,000 CALL at 15:27 : Rs. {p_minus1_call_exit:.2f}")
    print(f"     Real Return              : {((p_minus1_call_exit - p_plus2_call_entry)/p_plus2_call_entry)*100:.1f}% (Rs. {p_minus1_call_exit - p_plus2_call_entry:+.2f} pts - MONSTER SPIKE!)")

if __name__ == '__main__':
    main()
