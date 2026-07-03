import pandas as pd
from BACKTEST_V15_HYBRID_AGGRESSIVE import INDEX_CONFIGS, load_option_data_for_index

opt = load_option_data_for_index('NIFTY')
unique_dates_opt = opt['date'].unique()
print("Type of element in opt['date'].unique():", type(unique_dates_opt[0]))
print("hasattr(unique_dates_opt[0], 'weekday'):", hasattr(unique_dates_opt[0], 'weekday'))

all_dates = sorted(list(set().union(opt['date'].unique())))
print("Type of element in all_dates:", type(all_dates[0]))
print("hasattr(all_dates[0], 'weekday'):", hasattr(all_dates[0], 'weekday'))
