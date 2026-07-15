import MetaTrader5 as mt5
from datetime import datetime, timedelta

mt5.initialize()

start_time = datetime.now() - timedelta(hours=15)
end_time = datetime.now() + timedelta(hours=24)

deals = mt5.history_deals_get(start_time, end_time)

if deals is None:
    print("Failed to get history deals")
else:
    ai_opened = 0
    ai_closed = 0
    ai_pnl = 0.0
    
    tele_opened = 0
    tele_closed = 0
    tele_pnl = 0.0
    
    for d in deals:
        if d.magic == 888888:
            if d.entry == mt5.DEAL_ENTRY_IN:
                ai_opened += 1
            elif d.entry == mt5.DEAL_ENTRY_OUT:
                ai_closed += 1
                ai_pnl += d.profit
        elif d.magic == 777777:
            if d.entry == mt5.DEAL_ENTRY_IN:
                tele_opened += 1
            elif d.entry == mt5.DEAL_ENTRY_OUT:
                tele_closed += 1
                tele_pnl += d.profit
                
    print(f"AI Engine (Magic 888888): Opened: {ai_opened}, Closed: {ai_closed}, Realized PnL: ${ai_pnl:.2f}")
    print(f"Telegram (Magic 777777): Opened: {tele_opened}, Closed: {tele_closed}, Realized PnL: ${tele_pnl:.2f}")
    print(f"Total Trades Placed (IN): {ai_opened + tele_opened}")
    print(f"Total Trades Closed (OUT): {ai_closed + tele_closed}")
    print(f"Total Net Profit: ${ai_pnl + tele_pnl:.2f}")
