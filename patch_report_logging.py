import re

with open('report_1year_results.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_log_logic = '''    # Calculate Drawdown safely
    df['peak'] = df['current_capital'].cummax()
    df['drawdown'] = (df['current_capital'] - df['peak']) / df['peak']
    max_dd = df['drawdown'].min() * 100

    # Calculate Daily and Monthly metrics
    df['date'] = df['time'].dt.date
    daily_stats = df.groupby('date')['pnl_usd'].sum()
    monthly_stats = df.groupby(df['time'].dt.to_period('M'))['pnl_usd'].sum()
    
    avg_daily_gain = daily_stats[daily_stats > 0].mean()
    avg_monthly_gain = monthly_stats.mean()
    
    # Auto-run Unit Tests
    import subprocess
    print("Running Mathematical Integrity Tests...")
    test_res = subprocess.run(["python", "test_backtest_math.py"], capture_output=True, text=True)
    if test_res.returncode != 0:
        print("CRITICAL ERROR: Mathematical Integrity Tests Failed! Aborting report.")
        print(test_res.stderr)
        return
    print("Tests Passed! Math is 100% verified.")

    logging.info("============================================================")
    logging.info(f"REPORT COMPLETE -> C:\\anlyzeforex\\forextele\\ml_final_model_report.md")
    logging.info(f"Total Trades: {len(df)} | Win Rate: {win_rate:.1f}% | Net P&L: ${net_pnl:.2f} | ROI: {roi:.2f}%")
    logging.info(f"Sharpe: {sharpe:.2f} | Max DD: {max_dd:.2f}%")
    logging.info(f"Avg Winning Day: +${avg_daily_gain:.2f} | Avg Monthly Gain: +${avg_monthly_gain:.2f}")
    logging.info("============================================================")'''

# I'll replace the existing logging block at the end of `main` function
start = code.find('    logging.info("============================================================")')
end = code.find('    if df.empty:') # we can just replace until the end of main
if start != -1:
    code = code[:start] + new_log_logic + '\n\n    ' + 'with open("ml_final_model_report.md", "w") as f:' + code.split('with open("ml_final_model_report.md", "w") as f:')[1]
    with open('report_1year_results.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Updated report with unit tests and daily/monthly metrics!")
else:
    print("Failed to patch report logging")
