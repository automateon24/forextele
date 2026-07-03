import json
import os
import pandas as pd

# Load DNA and config
with open(r'C:\25stragy\strategy_dna.json') as f:
    dna = json.load(f)
with open(r'C:\25stragy\config.json') as f:
    config = json.load(f)

# Find all strategies in DNA
all_strats = list(dna.get('strategies', {}).keys())

# Find active strategies across all indices in config
active_strats = set()
for idx, profile in config.get('index_profiles', {}).items():
    active_strats.update(profile.get('active_strategies', []))

# Parse backtest output for trade stats
trades_file = r'C:\25stragy\backtest_results\v8_multiindex_trades.csv'
strat_stats = {s: {'trades': 0, 'wins': 0, 'pnl': 0.0} for s in all_strats}

if os.path.exists(trades_file):
    df = pd.read_csv(trades_file)
    for idx_row, row in df.iterrows():
        strat = row['strategy']
        pnl = row['pnl_rs']
        if strat in strat_stats:
            strat_stats[strat]['trades'] += 1
            strat_stats[strat]['pnl'] += pnl
            if pnl > 0:
                strat_stats[strat]['wins'] += 1

# Analyze each strategy
audit_list = []
for s in all_strats:
    is_active = s in active_strats
    stats = strat_stats[s]
    trades = stats['trades']
    pnl = stats['pnl']
    wr = (stats['wins'] / trades * 100) if trades > 0 else 0.0
    
    if not is_active:
        status = 'Disabled in Config'
        reason = 'Gated in configuration'
    elif trades == 0:
        status = 'Not Triggered'
        reason = 'No entry signals generated'
    elif pnl < 0:
        status = 'Underperforming'
        reason = f'Negative PnL: Rs. {pnl:,.2f}'
    else:
        status = 'Working & Profitable'
        reason = f'Profitable: Rs. +{pnl:,.2f}'
        
    audit_list.append({
        'strategy': s,
        'status': status,
        'trades': trades,
        'win_rate': f'{wr:.1f}%' if trades > 0 else 'N/A',
        'pnl': pnl,
        'reason': reason
    })

# Print non-working, disabled or not-triggered strategies
print("--- STRATEGIES REQUIRING ATTENTION (NOT WORKING / DISABLED / NOT TRIGGERED) ---")
print(f"{'Strategy Name':<28} | {'Status':<20} | {'Trades':<6} | {'Win Rate':<8} | {'Net PnL (Rs.)':<13} | {'Details / Notes'}")
print("-" * 110)

non_profitable_strats = [item for item in audit_list if item['status'] != 'Working & Profitable']
# Sort by status, then by PnL
non_profitable_strats.sort(key=lambda x: (x['status'], x['pnl']))

for item in non_profitable_strats:
    print(f"{item['strategy']:<28} | {item['status']:<20} | {item['trades']:<6} | {item['win_rate']:<8} | {item['pnl']:+13,.2f} | {item['reason']}")

print("\n--- WORKING & PROFITABLE STRATEGIES ---")
print(f"{'Strategy Name':<28} | {'Status':<20} | {'Trades':<6} | {'Win Rate':<8} | {'Net PnL (Rs.)':<13} | {'Details / Notes'}")
print("-" * 110)

profitable_strats = [item for item in audit_list if item['status'] == 'Working & Profitable']
profitable_strats.sort(key=lambda x: x['pnl'], reverse=True)
for item in profitable_strats:
    print(f"{item['strategy']:<28} | {item['status']:<20} | {item['trades']:<6} | {item['win_rate']:<8} | {item['pnl']:+13,.2f} | {item['reason']}")
