import re

with open('report_1year_results.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_pnl = '''    # --- ANTI-MARTINGALE WITH DAILY CIRCUIT BREAKER ---
    current_capital = INITIAL_CAPITAL
    
    pnl_usd_list = []
    lot_list = []
    
    win_streak = 0
    daily_pnl = 0.0
    current_day = None
    
    for i, row in df.iterrows():
        trade_date = row['time'].date()
        
        # Reset Daily P&L if new day
        if trade_date != current_day:
            current_day = trade_date
            daily_pnl = 0.0
            
        # Circuit Breaker: Stop trading if we lost 2% today
        if daily_pnl <= -(current_capital * 0.02):
            lot_list.append(0)
            pnl_usd_list.append(0)
            continue
            
        # Asymmetric Risk Management
        if win_streak == 0:
            RISK_PER_TRADE = 0.005 # 0.5% risk
        elif win_streak == 1:
            RISK_PER_TRADE = 0.01  # 1% risk
        else:
            RISK_PER_TRADE = 0.02  # 2% max risk
            
        risk_usd = current_capital * RISK_PER_TRADE
        
        sl_pts = row['sl_pts']
        if sl_pts <= 0: sl_pts = 10.0
        
        pt = POINT.get(row['symbol'], 0.00001)
        cs = CONTRACT_SIZE.get(row['symbol'], 100000)
        
        try:
            dynamic_lot = risk_usd / (sl_pts * pt * cs)
        except ZeroDivisionError:
            dynamic_lot = BASE_LOT
            
        dynamic_lot = min(max(dynamic_lot, 0.01), 10.0)
        
        if str(row.get('use_grid')).lower() == 'true':
            dynamic_lot = min(dynamic_lot, 0.1)
            
        lot_list.append(dynamic_lot)
        trade_pnl = compute_pnl(row, dynamic_lot)
        pnl_usd_list.append(trade_pnl)
        
        daily_pnl += trade_pnl
        
        # Update streak
        if trade_pnl > 0:
            win_streak += 1
        else:
            win_streak = 0
            
        current_capital += trade_pnl
        current_capital = max(current_capital, INITIAL_CAPITAL * 0.10)

    df['lot'] = lot_list
    df['pnl_usd'] = pnl_usd_list'''

start = code.find('    # --- ANTI-MARTINGALE')
end = code.find('    df["date"]')
if start != -1 and end != -1:
    code = code[:start] + new_pnl + '\n\n' + code[end:]
    with open('report_1year_results.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Updated Circuit Breaker")
else:
    print("Could not find replacement boundaries")
