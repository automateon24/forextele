import MetaTrader5 as mt5
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
cfg = json.loads((BASE_DIR / "mt5_config.json").read_text())

mt5.initialize(
    login=int(cfg["login"]),
    server=cfg["server"],
    password=cfg["password"]
)

test_symbols = ["GOLD", "BTCUSD", "USDJPY", "AUDJPY", "EURUSD", "GBPJPY", "US30Cash"]
specs = {}

for s in test_symbols:
    mt5.symbol_select(s, True)
    info = mt5.symbol_info(s)
    if info:
        specs[s] = {
            "point": info.point,
            "digits": info.digits,
            "spread_points": info.spread,
            "contract_size": info.trade_contract_size,
            "tick_value": info.trade_tick_value,
            "tick_size": info.trade_tick_size,
            "swap_long": info.swap_long,
            "swap_short": info.swap_short,
            "swap_mode": info.swap_mode,
            "margin_initial": info.margin_initial
        }
    else:
        specs[s] = "NOT_FOUND"

mt5.shutdown()
print(json.dumps(specs, indent=2))
