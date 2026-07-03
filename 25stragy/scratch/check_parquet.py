import pandas as pd
import os

path = r"C:\cursor\options\niftyopt\data\nifty_spot_2026_full.parquet"
if os.path.exists(path):
    df = pd.read_parquet(path)
    print("Columns:", df.columns.tolist())
    print("Row count:", len(df))
    if 'timestamp' in df.columns:
        print("Min date:", df['timestamp'].min())
        print("Max date:", df['timestamp'].max())
    elif 'date' in df.columns:
        print("Min date:", df['date'].min())
        print("Max date:", df['date'].max())
    else:
        print("First 5 rows:")
        print(df.head())
else:
    print("Parquet file does not exist!")
