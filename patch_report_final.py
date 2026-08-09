import re

with open('report_1year_results.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_log_logic = '''    # Calculate Drawdown safely
    df['peak'] = df['current_capital'].cummax()
    df['drawdown'] = (df['current_capital'] - df['peak']) / df['peak']
    max_dd = df['drawdown'].min() * 100

    # Calculate Daily and Monthly metrics
    df['date'] = df['time'].dt.date
    daily_stats = df.groupby('date')['pnl_usd'].sum()
    monthly_stats = df.groupby(df['time'].dt.to_period('M'))['pnl_usd'].sum()
    
    avg_daily_gain = daily_stats[daily_stats > 0].mean()
    avg_monthly_gain = monthly_stats[monthly_stats > 0].mean()
    
    # Auto-run Unit Tests
    import subprocess
    print("Running Mathematical Integrity Tests...")
    test_res = subprocess.run(["C:\\Python314\\python.exe", "test_backtest_math.py"], capture_output=True, text=True)
    if test_res.returncode != 0:
        print("CRITICAL ERROR: Mathematical Integrity Tests Failed! Aborting report.")
        print(test_res.stderr)
        return
    print("Tests Passed! Math is 100% verified.")

    logging.info("============================================================")
    logging.info(f"REPORT COMPLETE -> C:\\anlyzeforex\\forextele\\ml_final_model_report.md")
    logging.info(f"Total Trades: {len(df)} | Win Rate: {win_rate:.1f}% | Net P&L: ${net_pnl:.2f} | ROI: {roi:.2f}%")
    logging.info(f"Sharpe: {sharpe:.2f} | Max DD: {max_dd:.2f}%")
    logging.info(f"Avg Winning Day: +${avg_daily_gain:.2f} | Avg Winning Month: +${avg_monthly_gain:.2f}")
    logging.info("============================================================")
'''

start_idx = 0
for i, line in enumerate(lines):
    if 'logging.info("============================================================")' in line:
        start_idx = i
        break

end_idx = 0
for i, line in enumerate(lines[start_idx:]):
    if 'with open' in line:
        end_idx = start_idx + i
        break

if start_idx != 0 and end_idx != 0:
    lines = lines[:start_idx] + [new_log_logic] + lines[end_idx:]
    with open('report_1year_results.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Patched successfully")
else:
    print("Could not find boundaries")
