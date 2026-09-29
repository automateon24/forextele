import sys
from pathlib import Path
BASE_DIR = Path(r"C:\anlyzeforex\forextele")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json

from ai_trade_learning_engine import learning_engine

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
cfg_file = BASE_DIR / "mt5_config.json"
mt5_cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}

if not mt5.initialize(
    login=int(mt5_cfg.get("login", 0)),
    server=mt5_cfg.get("server", ""),
    password=mt5_cfg.get("password", "")
):
    mt5.initialize()

now_utc = datetime.now(timezone.utc)
from_time = now_utc - timedelta(days=7) # sync full week

deals = mt5.history_deals_get(from_time, now_utc)
print(f"Total deals in 7 days: {len(deals) if deals else 0}")

# Group deals by position_id
pos_map = defaultdict(list)
for d in (deals or []):
    pos_map[d.position_id].append(d)

synced_count = 0
for pos_id, d_list in pos_map.items():
    entries = [d for d in d_list if d.entry == 0]
    exits = [d for d in d_list if d.entry in (1, 3)]
    
    if not entries or not exits:
        continue
        
    entry_d = entries[0]
    exit_d = exits[-1]
    
    pos_pnl = sum(d.profit + d.swap + d.commission for d in d_list)
    outcome = "WIN" if pos_pnl > 0.05 else ("LOSS" if pos_pnl < -0.05 else "BREAKEVEN")
    
    # Calculate pips
    symbol = entry_d.symbol
    digits = 2 if "JPY" in symbol or "XAU" in symbol or symbol == "GOLD" else 4
    pip_scale = 10.0 if symbol == "GOLD" else (100.0 if "JPY" in symbol else 10000.0)
    if symbol == "BTCUSD":
        pips = (exit_d.price - entry_d.price) if entry_d.type == 0 else (entry_d.price - exit_d.price)
    else:
        pips = (exit_d.price - entry_d.price) * pip_scale if entry_d.type == 0 else (entry_d.price - exit_d.price) * pip_scale
        
    # Update knowledge base
    learning_engine.update_trade_result(
        ticket=entry_d.position_id,
        pnl_usd=round(pos_pnl, 2),
        pnl_pips=round(pips, 1),
        outcome=outcome
    )
    synced_count += 1

# Force channel profiles recalculation
learning_engine.refresh_channel_profiles()

print(f"Successfully synced and refreshed {synced_count} closed positions into AI learning engine.")
mt5.shutdown()
