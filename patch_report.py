import re

with open('report_1year_results.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_pnl = '''    # --- COMPOUNDING POSITION SIZING ---
    RISK_PER_TRADE = 0.03 # Risking 3% of capital per trade
    current_capital = INITIAL_CAPITAL
    
    pnl_usd_list = []
    lot_list = []
    
    for i, row in df.iterrows():
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
            dynamic_lot = min(dynamic_lot, 0.2)
            
        lot_list.append(dynamic_lot)
        trade_pnl = compute_pnl(row, dynamic_lot)
        pnl_usd_list.append(trade_pnl)
        
        current_capital += trade_pnl
        current_capital = max(current_capital, INITIAL_CAPITAL * 0.10)

    df['lot'] = lot_list
    df['pnl_usd'] = pnl_usd_list'''

code = code.replace('    # --- Compute P&L ---\n    df["pnl_usd"] = df.apply(lambda r: compute_pnl(r, r["lot"]), axis=1)', new_pnl)

with open('report_1year_results.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Updated report_1year_results.py successfully!')
