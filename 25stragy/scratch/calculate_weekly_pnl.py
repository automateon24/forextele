import os
import glob
import pandas as pd
from datetime import datetime, timedelta

base_dir = r"C:\cursor\options\niftyopt"
daily_data_dir = os.path.join(base_dir, "daily_data")
data_dir = os.path.join(base_dir, "data")

start_date = datetime(2026, 6, 18)
end_date = datetime(2026, 6, 25)

print(f"=== Calculating PnL from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ===")

# --- 1. V3 Engine ---
v3_trades_list = []
v3_files = glob.glob(os.path.join(daily_data_dir, "v3_trades_*.csv"))
for f in v3_files:
    try:
        date_str = os.path.basename(f).split("_")[2].replace(".csv", "")
        file_date = datetime.strptime(date_str, "%Y%m%d")
        if start_date <= file_date <= end_date:
            df = pd.read_csv(f)
            df['file_date'] = file_date
            v3_trades_list.append(df)
    except Exception as e:
        pass

if v3_trades_list:
    v3_df = pd.concat(v3_trades_list, ignore_index=True)
    exits = v3_df[v3_df['event'] == 'EXIT']
    v3_pnl = exits['pnl'].astype(float).sum()
    v3_count = len(exits)
    print(f"V3 Engine: {v3_count} closed trades | Realized PnL: Rs. {v3_pnl:,.2f}")
else:
    print("V3 Engine: No trades found in date range.")

# --- 2. V4 Engine ---
v4_trades_list = []
v4_files = glob.glob(os.path.join(daily_data_dir, "modular_trades_*.csv"))
for f in v4_files:
    try:
        date_str = os.path.basename(f).split("_")[2].replace(".csv", "")
        file_date = datetime.strptime(date_str, "%Y%m%d")
        if start_date <= file_date <= end_date:
            df = pd.read_csv(f)
            df['file_date'] = file_date
            v4_trades_list.append(df)
    except Exception as e:
        pass

if v4_trades_list:
    v4_df = pd.concat(v4_trades_list, ignore_index=True)
    exits = v4_df[v4_df['event'] == 'EXIT']
    v4_pnl = exits['pnl'].astype(float).sum()
    v4_count = len(exits)
    print(f"V4 Engine: {v4_count} closed trades | Realized PnL: Rs. {v4_pnl:,.2f}")
else:
    print("V4 Engine: No trades found in date range.")

# --- 3. V15 Engine (Stragy) ---
v15_path = os.path.join(data_dir, "live_portfolio_paper_trades.csv")
if os.path.exists(v15_path):
    v15_df = pd.read_csv(v15_path)
    # Parse exit_time
    v15_df['exit_dt'] = pd.to_datetime(v15_df['exit_time'], errors='coerce')
    v15_df_filtered = v15_df[(v15_df['exit_dt'] >= start_date) & (v15_df['exit_dt'] <= end_date + timedelta(days=1))]
    v15_pnl = v15_df_filtered['pnl_rs'].astype(float).sum()
    v15_count = len(v15_df_filtered)
    print(f"V15 Engine: {v15_count} closed trades | Realized PnL: Rs. {v15_pnl:,.2f}")
    if v15_count > 0:
        print(v15_df_filtered[['exit_time', 'index', 'strategy', 'direction', 'pnl_rs']].to_string())
else:
    print("V15 Engine: No trade file found.")
