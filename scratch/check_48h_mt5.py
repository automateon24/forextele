import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
cfg_file = BASE_DIR / "mt5_config.json"
mt5_cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}

if not mt5.initialize(
    login=int(mt5_cfg.get("login", 0)),
    server=mt5_cfg.get("server", ""),
    password=mt5_cfg.get("password", "")
):
    mt5.initialize()

acct = mt5.account_info()
print(f"MT5 Account: {acct.login} | Server: {acct.server}")
print(f"Current Balance: ${acct.balance:.2f} | Equity: ${acct.equity:.2f} | Profit: ${acct.profit:.2f}")

# Time range: past 48 hours (from Sep 21 17:00 UTC to now)
now_utc = datetime.now(timezone.utc)
from_date = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)
to_date = now_utc + timedelta(days=1)

deals = mt5.history_deals_get(from_date, to_date)
print(f"\nTotal deals since Sep 21 00:00 UTC: {len(deals) if deals else 0}")

# Filter for deals in the last 48 hours (since Sep 21 17:00 UTC)
from_48h = datetime(2026, 9, 21, 17, 0, 0, tzinfo=timezone.utc)
deals_48h = [d for d in (deals or []) if datetime.fromtimestamp(d.time, tz=timezone.utc) >= from_48h]
print(f"Deals strictly in past 48 hours (since Sep 21 17:00 UTC): {len(deals_48h)}")

# Check open positions
positions = mt5.positions_get()
print(f"Currently open positions: {len(positions) if positions else 0}")
if positions:
    for p in positions:
        print(f"  Open: #{p.ticket} | {p.symbol} | Vol:{p.volume} | Type:{'BUY' if p.type==0 else 'SELL'} | OpenPrice:{p.price_open} | CurrentPrice:{p.price_current} | PnL:${p.profit:.2f} | Magic:{p.magic} | Comm:'{p.comment}'")

# Group deals by position_id to get closed trades
pos_groups = defaultdict(list)
for d in deals:
    pos_groups[d.position_id].append(d)

print(f"\nTotal unique positions traded since Sep 21: {len(pos_groups)}")
