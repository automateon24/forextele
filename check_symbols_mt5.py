import MetaTrader5 as mt5
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"

if MT5_CFG_PATH.exists():
    with open(MT5_CFG_PATH, "r") as f:
        config = json.load(f)
    mt5.initialize(
        login=int(config.get("login", 0)),
        server=config.get("server", ""),
        password=config.get("password", "")
    )
else:
    mt5.initialize()

print("Connected:", mt5.terminal_info() is not None)

symbols = mt5.symbols_get()
if symbols:
    names = [s.name for s in symbols if "GOLD" in s.name.upper() or "XAU" in s.name.upper()]
    print("Gold Symbols available on this broker:", names)
else:
    print("No symbols found or failed to get symbols.")

print("Can select XAUUSD?", mt5.symbol_select("XAUUSD", True))
print("Can select GOLD?", mt5.symbol_select("GOLD", True))

tick = mt5.symbol_info_tick("XAUUSD")
if tick: print("XAUUSD Ask:", tick.ask)
else: print("XAUUSD tick is None")

tick_gold = mt5.symbol_info_tick("GOLD")
if tick_gold: print("GOLD Ask:", tick_gold.ask)
else: print("GOLD tick is None")

mt5.shutdown()
