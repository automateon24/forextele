import pandas as pd
import numpy as np

csv_path = r"C:\25stragy\backtest_results\aggressive_100k_trades.csv"
df = pd.read_csv(csv_path)

# Group PnL by date
daily_pnl = df.groupby('date')['pnl_rs'].sum().sort_index()

# Initialize equity curve starting with Rs. 500,000
initial_capital = 500000.0
equity = [initial_capital]
dates = [pd.to_datetime(daily_pnl.index[0]) - pd.Timedelta(days=1)]

for date, pnl in daily_pnl.items():
    equity.append(equity[-1] + pnl)
    dates.append(pd.to_datetime(date))

equity_df = pd.DataFrame({'date': dates, 'equity': equity})
equity_df['peak'] = equity_df['equity'].cummax()
equity_df['drawdown_rs'] = equity_df['equity'] - equity_df['peak']
equity_df['drawdown_pct'] = (equity_df['drawdown_rs'] / equity_df['peak']) * 100

min_equity = equity_df['equity'].min()
max_drawdown_rs = equity_df['drawdown_rs'].min()
max_drawdown_pct = equity_df['drawdown_pct'].min()

print("=== PORTFOLIO EQUITY CURVE ANALYSIS ===")
print(f"Starting Capital       : Rs. {initial_capital:,.2f}")
print(f"Ending Equity          : Rs. {equity_df['equity'].iloc[-1]:,.2f}")
print(f"Minimum Equity Reached : Rs. {min_equity:,.2f}")
print(f"Max Absolute Drawdown  : Rs. {max_drawdown_rs:,.2f}")
print(f"Max Percentage Drawdown: {max_drawdown_pct:.2f}%")

if min_equity < 0:
    print("\nWARNING: Account equity went negative! Portfolio was wiped out.")
else:
    print("\nSUCCESS: Account was never wiped out. Minimum equity stayed above Rs. 0.")
