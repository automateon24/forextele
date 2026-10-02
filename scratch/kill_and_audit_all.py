import psutil
import MetaTrader5 as mt5

print("="*60)
print("  EMERGENCY AUDIT & COMPLETE PROCESS TERMINATION")
print("="*60)

# 1. Close any open MT5 positions
if mt5.initialize():
    positions = mt5.positions_get()
    if positions:
        print(f"Found {len(positions)} open positions. Closing now...")
        for p in positions:
            order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(p.symbol)
            price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
            req = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': p.symbol,
                'volume': p.volume,
                'type': order_type,
                'position': p.ticket,
                'price': price,
                'deviation': 25,
                'magic': p.magic,
                'comment': 'Weekend Force Close',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            ret = res.retcode if res else "None"
            profit = p.profit
            print(f"  Closed Ticket #{p.ticket} ({p.symbol} {'BUY' if p.type==0 else 'SELL'}) | PnL: ${profit:+.2f} | Retcode: {ret}")
    else:
        print("✅ Zero open positions in MT5.")

    orders = mt5.orders_get()
    if orders:
        print(f"Found {len(orders)} pending orders. Cancelling...")
        for o in orders:
            req = {'action': mt5.TRADE_ACTION_REMOVE, 'order': o.ticket, 'comment': 'Cancel all'}
            mt5.order_send(req)
    else:
        print("✅ Zero pending orders.")

    acc = mt5.account_info()
    if acc:
        print(f"Account Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Margin: ${acc.margin:,.2f}")
    mt5.shutdown()

# 2. Terminate every process related to forextele, breakout_boss, scanner, telegram, and batch supervisors
print("\nScanning for all related processes...")
targets = [
    'breakout_boss',
    'run_breakout_boss',
    'autonomous_ai_market_scanner',
    'run_autonomous_scanner',
    'telegram_signal_engine',
    'run_telegram_gold_live',
    'start_all_engines',
    'start_monday_live_engines',
    'master_autostart_watchdog',
    'ai_backtest_alignment_watchdog',
    'start_247_live_bot'
]

killed_count = 0
for p in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or []).lower()
        if any(t in cmd for t in targets) and 'kill_and_audit' not in cmd:
            print(f"  Terminating PID {p.info['pid']} ({p.info['name']}): {cmd[:90]}")
            p.kill()
            killed_count += 1
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

print(f"\nTotal processes terminated: {killed_count}")
