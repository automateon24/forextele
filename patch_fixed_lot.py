import re

with open('report_1year_results.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_pnl = '''    # --- FIXED POSITION SIZING ---
    FIXED_LOT = 0.5
    
    pnl_usd_list = []
    lot_list = []
    
    for i, row in df.iterrows():
        if str(row.get('use_grid')).lower() == 'true':
            dynamic_lot = FIXED_LOT / 2.0
        else:
            dynamic_lot = FIXED_LOT
            
        lot_list.append(dynamic_lot)
        
        trade_pnl = compute_pnl(row, dynamic_lot)
        pnl_usd_list.append(trade_pnl)

    df['lot'] = lot_list
    df['pnl_usd'] = pnl_usd_list'''

start = code.find('    # --- COMPOUNDING POSITION SIZING ---')
end = code.find('    df["date"]')
if start != -1 and end != -1:
    code = code[:start] + new_pnl + '\n\n' + code[end:]
    with open('report_1year_results.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Updated report_1year_results.py to Fixed 0.5 Lots successfully!")
else:
    print("Could not find replacement boundaries")
