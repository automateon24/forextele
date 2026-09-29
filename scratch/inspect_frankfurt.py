import json

with open(r'c:\anlyzeforex\forextele\scratch\all_sessions_gold_results.json') as f:
    data = json.load(f)

print("=== ALL 20 FRANKFURT OPEN SETUPS ===")
total_pnl = 0.0
for r in data:
    if 'Frankfurt' in r['session']:
        print(f"{r['tf']:<4} | {r['rr']:<6} | Trades: {r['trades']:<3} | WR: {r['win_rate']:<5.1f}% | Net PnL: ${r['net_pnl']:<+8.2f} | PF: {r['pf']:<5.2f}")
        total_pnl += r['net_pnl']
print(f"Sum of all 20 Frankfurt setups: ${total_pnl:.2f}")

print("\n=== TOTALS BY SESSION ACROSS ALL SETUPS ===")
session_sums = {}
for r in data:
    s = r['session']
    session_sums[s] = session_sums.get(s, 0.0) + r['net_pnl']

for s, pnl in session_sums.items():
    print(f"{s:<26}: ${pnl:<+10.2f}")

grand_total = sum(session_sums.values())
print(f"\nGRAND TOTAL OF ALL SESSIONS COMBINED: ${grand_total:.2f}")
