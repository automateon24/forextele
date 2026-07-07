import MetaTrader5 as mt5

if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()
    exit()

positions = mt5.positions_get()
if positions:
    print("Active Positions:")
    for pos in positions:
        action = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        print(f"[{pos.symbol}] {action} | Volume: {pos.volume} | SL: {pos.sl} | TP: {pos.tp} | Magic: {pos.magic} | Comment: {pos.comment}")
else:
    print("No active positions.")

mt5.shutdown()
