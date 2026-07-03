import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
import pandas as pd
from BACKTEST_V3_TUNED import load_option_data

opt_data = load_option_data()
print('Checking ATM+2 strike data availability:')
day = list(opt_data['date'].unique())[0]
day_data = opt_data[opt_data['date'] == day]

for strike in ['ATM', 'ATM+1', 'ATM+2', 'ATM+3', 'ATM+4']:
    ce = day_data[(day_data['strike'] == strike) & (day_data['option_type_flag'] == 'CE')]
    pe = day_data[(day_data['strike'] == strike) & (day_data['option_type_flag'] == 'PE')]
    if len(ce) > 0:
        cemin = ce['close'].min()
        cemax = ce['close'].max()
        print(f'{strike} CE: {len(ce)} bars, premium range {cemin:.0f}-{cemax:.0f}')
    else:
        print(f'{strike} CE: NO DATA')
    if len(pe) > 0:
        pemin = pe['close'].min()
        pemax = pe['close'].max()
        print(f'{strike} PE: {len(pe)} bars, premium range {pemin:.0f}-{pemax:.0f}')
    else:
        print(f'{strike} PE: NO DATA')
