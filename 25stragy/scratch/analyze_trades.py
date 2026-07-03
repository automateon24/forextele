import os
import glob
import re
import pandas as pd
from datetime import datetime

base_dir = r"C:\cursor\options\niftyopt"
search_paths = [
    os.path.join(base_dir, "daily_data", "*.csv"),
    os.path.join(base_dir, "trades", "*.csv"),
    os.path.join(base_dir, "*.csv")
]

all_data = []
for gp in search_paths:
    for f in glob.glob(gp):
        basename = os.path.basename(f)
        
        # Extract 8-digit date
        date_match = re.search(r"\d{8}", basename)
        if not date_match:
            continue
        date_str = date_match.group(0)
        dt = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        
        # Determine engine
        engine = "Unknown"
        if "v3" in basename.lower():
            engine = "V3"
        elif "modular" in basename.lower() or "v4" in basename.lower():
            engine = "V4"
        elif "v15" in basename.lower() or "stragy" in basename.lower() or "trades_202" in basename.lower():
            engine = "V15"
            
        try:
            df = pd.read_csv(f)
            if len(df) == 0:
                continue
            
            pnl_col = None
            for col in df.columns:
                if 'pnl' in col.lower() and 'unreal' not in col.lower():
                    pnl_col = col
                    break
            
            if pnl_col:
                total_pnl = df[pnl_col].sum()
                all_data.append({
                    "file": basename,
                    "date": dt,
                    "engine": engine,
                    "trades": len(df),
                    "pnl": total_pnl
                })
        except Exception as e:
            pass

summary_df = pd.DataFrame(all_data)
if not summary_df.empty:
    summary_df['date'] = pd.to_datetime(summary_df['date'])
    # Filter for last 1 week (from June 18 to June 25, 2026, inclusive)
    start_date = pd.to_datetime("2026-06-18")
    end_date = pd.to_datetime("2026-06-25")
    weekly_df = summary_df[(summary_df['date'] >= start_date) & (summary_df['date'] <= end_date)]
    
    print("=== ALL WEEKLY FILES ===")
    print(weekly_df.sort_values("date").to_string(index=False))
    
    print("\n=== WEEKLY PNL BY ENGINE ===")
    pnl_by_engine = weekly_df.groupby("engine")["pnl"].sum()
    trades_by_engine = weekly_df.groupby("engine")["trades"].sum()
    for eng in ["V3", "V4", "V15"]:
        pnl_val = pnl_by_engine.get(eng, 0.0)
        trades_val = trades_by_engine.get(eng, 0)
        print(f"Engine {eng}: PnL = Rs. {pnl_val:,.2f} ({trades_val} trades)")
else:
    print("No data parsed")
