import MetaTrader5 as mt5

if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()
else:
    symbols = mt5.symbols_get()
    print("Total symbols:", len(symbols))
    gold_symbols = [s.name for s in symbols if 'XAU' in s.name or 'GOLD' in s.name.upper()]
    print("Gold symbols found:", gold_symbols)
    mt5.shutdown()
