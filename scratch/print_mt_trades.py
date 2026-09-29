import json

with open(r"C:\anlyzeforex\forextele\scratch\clean_channel_backtest_today.json", encoding="utf-8") as f:
    d = json.load(f)

for item in d['leaderboard']:
    if "market trader" in item['channel'].lower():
        print(f"=== {item['channel']} ===")
        for tr in item['trades']:
            print(f"  {tr['time']} | {tr['symbol']} {tr['action']} | Entry: {tr['entry']} -> Exit: {tr['exit']} | Outcome: {tr['outcome']} | Pips: {tr['pips']} | USD: ${tr['usd']} | MFE: {tr['mfe_pips']}p | MAE: {tr['mae_pips']}p")
            print(f"    Raw: {tr['raw']}")
