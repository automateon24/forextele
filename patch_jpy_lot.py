import re

with open('report_1year_results.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_lot = '''        pt = POINT.get(row['symbol'], 0.00001)
        cs = CONTRACT_SIZE.get(row['symbol'], 100000)
        
        # Calculate risk in USD correctly
        usd_val = sl_pts * pt * cs
        if row['symbol'] == 'USDJPY':
            usd_val /= 150.0
            
        try:
            dynamic_lot = risk_usd / usd_val
        except ZeroDivisionError:
            dynamic_lot = BASE_LOT'''

code = code.replace("        pt = POINT.get(row['symbol'], 0.00001)\n        cs = CONTRACT_SIZE.get(row['symbol'], 100000)\n        \n        try:\n            dynamic_lot = risk_usd / (sl_pts * pt * cs)\n        except ZeroDivisionError:\n            dynamic_lot = BASE_LOT", new_lot)

with open('report_1year_results.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Fixed USDJPY Lot sizing")
