import os
import sys
import pandas as pd
from datetime import datetime

# Set output encoding to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\cursor\options\niftyopt"
csv_path = os.path.join(base_dir, "data", "live_portfolio_paper_trades.csv")

print("=== live_portfolio_paper_trades.csv Analysis ===")
if os.path.exists(csv_path):
    try:
        df = pd.read_csv(csv_path)
        if len(df) > 0:
            df['entry_time'] = pd.to_datetime(df['entry_time'], errors='coerce')
            start_date = pd.to_datetime("2026-06-18")
            end_date = pd.to_datetime("2026-06-25 23:59:59")
            weekly_df = df[(df['entry_time'] >= start_date) & (df['entry_time'] <= end_date)]
            print(f"Weekly trades (June 18 - June 25): {len(weekly_df)}")
            if len(weekly_df) > 0:
                pnl_col = [c for c in df.columns if 'pnl' in c.lower() and 'unreal' not in c.lower()]
                if pnl_col:
                    pnl_sum = weekly_df[pnl_col[0]].sum()
                    print(f"Weekly V15 PnL: Rs. {pnl_sum:,.2f}")
                else:
                    print("No PnL column found in CSV")
    except Exception as e:
        print(f"Error reading CSV: {e}")
else:
    print("CSV file does not exist")

print("\n=== daily_analysis log files scan ===")
log_files = sorted([os.path.join(base_dir, "data", f) for f in os.listdir(os.path.join(base_dir, "data")) if f.startswith("daily_analysis_")])
for lf in log_files[-3:]:
    print(f"\n--- {os.path.basename(lf)} ---")
    with open(lf, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Print the lines containing key performance figures
    lines = content.splitlines()
    for line in lines:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in ["total trades", "wins", "losses", "win rate", "pnl (rs.)", "realized pnl", "capital base", "drawdown"]):
            print(line.strip())
