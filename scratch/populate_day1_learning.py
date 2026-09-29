import sys
import json
from pathlib import Path

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
sys.path.insert(0, str(BASE_DIR))
from ai_trade_learning_engine import learning_engine
scrape_file = BASE_DIR / "scratch" / "clean_channel_backtest_today.json"

if not scrape_file.exists():
    print("Scrape file not found!")
    exit(1)

with open(scrape_file, encoding='utf-8') as f:
    data = json.load(f)

leaderboard = data.get("leaderboard", [])
print(f"Ingesting trades from {len(leaderboard)} channels into AI Learning Engine...")

count = 0
for ch_data in leaderboard:
    ch = ch_data.get("channel")
    acc = ch_data.get("account")
    for tr in ch_data.get("trades", []):
        sym = tr.get("symbol")
        act = tr.get("action")
        entry = tr.get("entry")
        outcome = tr.get("outcome")
        usd = tr.get("usd", 0.0)
        pips = tr.get("pips", 0.0)
        raw = tr.get("raw", "")
        
        # Record trade setup & reverse engineer SMC context
        rec = learning_engine.record_and_learn_trade(
            channel=ch,
            account=acc,
            symbol=sym,
            action=act,
            entry=entry,
            raw_text=raw
        )
        
        # Update with backtested outcome
        if rec and "ticket" in rec:
            learning_engine.update_trade_result(
                ticket=rec.get("ticket"),
                pnl_usd=usd,
                pnl_pips=pips,
                outcome=outcome
            )
        count += 1

learning_engine.refresh_channel_profiles()
print(f"Successfully reverse-engineered and ingested {count} trades into AI Learning Knowledge Base!")
