import MetaTrader5 as mt5

if not mt5.initialize():
    print("MT5 init failed")
    exit(1)

for s in ["BTCUSD", "BTCUSD#", "BTCUSDm", "BTCUSD.a"]:
    info = mt5.symbol_info(s)
    if info:
        mt5.symbol_select(s, True)
        tick = mt5.symbol_info_tick(s)
        print(f"AVAILABLE: {s} | Bid: {tick.bid if tick else 'N/A'} | Ask: {tick.ask if tick else 'N/A'} | Digits: {info.digits}")
        break
mt5.shutdown()
