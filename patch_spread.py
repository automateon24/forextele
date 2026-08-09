import re

with open('backtest_high_res.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_spread = '''        if s['symbol'] == 'BTCUSD':
            spread_pts = 300.0
        elif s['symbol'] == 'ETHUSD':
            spread_pts = 150.0
        else:
            spread_pts = 10.0'''

code = code.replace("        spread_pts = 10.0 if \"JPY\" not in s['symbol'] else 0.010", new_spread)
code = code.replace("        spread_pts = 10.0 if 'JPY' not in s['symbol'] else 0.010", new_spread)

with open('backtest_high_res.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Fixed spread calculation")
