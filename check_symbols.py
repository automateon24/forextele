import MetaTrader5 as mt5

if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()
    exit()

symbols = mt5.symbols_get()
gold_symbols = [s.name for s in symbols if "GOLD" in s.name.upper() or "XAU" in s.name.upper()]
print("Found Gold Symbols:", gold_symbols)

mt5.shutdown()
