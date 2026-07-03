import pandas as pd
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

v3_path = r"C:\cursor\options\niftyopt\daily_data\v3_trades_20260625.csv"
v4_path = r"C:\cursor\options\niftyopt\daily_data\modular_trades_20260625.csv"
v15_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"

print("========================================")
print("DEEP-DIVE: DETAILED LIVE TRADES FOR JUNE 25")
print("========================================\n")

# 1. Summarize V3
if os.path.exists(v3_path):
    print("--- V3 DETAILED TRADES ---")
    df = pd.read_csv(v3_path)
    trades = {}
    for _, row in df.iterrows():
        tid = row.get('trade_id')
        if not tid:
            continue
        event = row.get('event')
        if event == 'ENTER':
            trades[tid] = {
                'entry_time': row.get('timestamp'),
                'strategy': row.get('strategy') or row.get('module'),
                'direction': row.get('direction'),
                'strike': row.get('strike'),
                'entry_price': row.get('entry'),
                'lots': row.get('lots', 1),
                'exit_price': None,
                'exit_time': None,
                'pnl': None,
                'exit_reason': None
            }
        elif event == 'EXIT' and tid in trades:
            trades[tid]['exit_price'] = row.get('exit')
            trades[tid]['exit_time'] = row.get('timestamp')
            trades[tid]['pnl'] = row.get('pnl')
            trades[tid]['exit_reason'] = row.get('exit_reason')
            
    for tid, t in trades.items():
        print(f"Trade ID: {tid} | Strat: {t['strategy']} | Dir: {t['direction']} | Strike: {t['strike']} | Lots: {t['lots']}")
        print(f"  Entry: {t['entry_time']} @ Rs. {t['entry_price']:.2f}")
        if t['exit_time']:
            print(f"  Exit:  {t['exit_time']} @ Rs. {t['exit_price']} | PnL: Rs. {t['pnl']} | Reason: {t['exit_reason']}")
        else:
            print("  Exit:  STILL OPEN or Unmatched Exit")
        print("-" * 50)

# 2. Summarize V4
if os.path.exists(v4_path):
    print("\n--- V4/MODULAR DETAILED TRADES ---")
    df = pd.read_csv(v4_path)
    trades = {}
    for _, row in df.iterrows():
        tid = row.get('trade_id')
        if not tid:
            continue
        event = row.get('event')
        if event == 'ENTER':
            trades[tid] = {
                'entry_time': row.get('timestamp'),
                'strategy': row.get('strategy') or row.get('module'),
                'direction': row.get('direction'),
                'strike': row.get('strike'),
                'entry_price': row.get('entry'),
                'lots': row.get('lots', 1),
                'exit_price': None,
                'exit_time': None,
                'pnl': None,
                'exit_reason': None
            }
        elif event == 'EXIT' and tid in trades:
            trades[tid]['exit_price'] = row.get('exit')
            trades[tid]['exit_time'] = row.get('timestamp')
            trades[tid]['pnl'] = row.get('pnl')
            trades[tid]['exit_reason'] = row.get('exit_reason')
            
    for tid, t in trades.items():
        print(f"Trade ID: {tid} | Strat: {t['strategy']} | Dir: {t['direction']} | Strike: {t['strike']} | Lots: {t['lots']}")
        print(f"  Entry: {t['entry_time']} @ Rs. {t['entry_price']:.2f}")
        if t['exit_time']:
            print(f"  Exit:  {t['exit_time']} @ Rs. {t['exit_price']} | PnL: Rs. {t['pnl']} | Reason: {t['exit_reason']}")
        else:
            print("  Exit:  STILL OPEN or Unmatched Exit")
        print("-" * 50)

# 3. Summarize V15
if os.path.exists(v15_path):
    print("\n--- V15 DETAILED TRADES ---")
    df = pd.read_csv(v15_path)
    print(df[['index', 'strategy', 'direction', 'entry_price', 'exit_price', 'pnl_rs', 'exit_reason', 'entry_time', 'exit_time']])
