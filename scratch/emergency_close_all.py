import MetaTrader5 as mt5
import time

mt5.initialize()
print("MT5 initialized")

# 1. Close ALL open positions
positions = mt5.positions_get()
print(f"Open positions: {len(positions) if positions else 0}")

if positions:
    for pos in positions:
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 50,
            "magic": pos.magic,
            "comment": "EMERGENCY_CLOSE_ALL",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ Closed #{pos.ticket} {pos.symbol} {pos.volume} lots | PnL: ${pos.profit:.2f}")
        else:
            print(f"❌ Failed to close #{pos.ticket} | retcode: {res.retcode if res else 'None'}")
        time.sleep(0.2)

# 2. Cancel ALL pending limit/stop orders
orders = mt5.orders_get()
print(f"\nPending orders: {len(orders) if orders else 0}")

if orders:
    for order in orders:
        req = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": order.ticket,
            "comment": "EMERGENCY_CANCEL_ALL",
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ Cancelled pending order #{order.ticket} {order.symbol} {order.type}")
        else:
            print(f"❌ Failed to cancel #{order.ticket} | retcode: {res.retcode if res else 'None'}")
        time.sleep(0.2)

# 3. Verify everything is gone
remaining_pos = mt5.positions_get()
remaining_ord = mt5.orders_get()
print(f"\n📊 FINAL STATE:")
print(f"   Remaining positions : {len(remaining_pos) if remaining_pos else 0}")
print(f"   Remaining orders    : {len(remaining_ord) if remaining_ord else 0}")

acc = mt5.account_info()
if acc:
    print(f"   Account Balance     : ${acc.balance:.2f}")
    print(f"   Account Equity      : ${acc.equity:.2f}")

mt5.shutdown()
print("\n✅ MT5 emergency close complete.")
