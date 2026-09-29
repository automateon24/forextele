import json

with open(r"C:\anlyzeforex\forextele\scratch\comprehensive_channel_backtest_today.json", encoding="utf-8") as f:
    d = json.load(f)

print("ANOMALIES:")
for item in d['leaderboard']:
    if item['total_usd'] < -10 or item['total_pips'] < -100:
        print(f"\n{item['channel']} ({item['account']}): {item['signals']} sigs | Pips: {item['total_pips']} | USD: ${item['total_usd']}")
        for tr in item['trades']:
            if tr['pips'] < -200 or abs(tr['usd']) > 20:
                print(f"  --> {tr['symbol']} {tr['action']} entry:{tr['entry']} exit:{tr['exit']} pips:{tr['pips']} usd:${tr['usd']}")
                print(f"      raw: {tr['raw']}")
