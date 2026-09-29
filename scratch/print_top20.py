import json

with open(r"C:\anlyzeforex\forextele\scratch\clean_channel_backtest_today.json", encoding="utf-8") as f:
    d = json.load(f)

print(f"Top 20 channels today out of {len(d['leaderboard'])}:")
for rank, item in enumerate(d['leaderboard'][:20], 1):
    print(f"{rank:>2}. {item['channel']:<35} ({item['account']}) | Sigs: {item['signals']:>2} | W/BE/L: {item['wins']}/{item['be']}/{item['losses']} | Pips: {item['total_pips']:>7.1f}p | Max MFE: {item['max_mfe']:>6.1f}p | Net USD: ${item['total_usd']:>6.2f}")
