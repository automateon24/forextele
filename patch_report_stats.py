import re

with open('report_1year_results.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_log_logic = '''    # Calculate Daily and Monthly metrics
    df['date'] = df['time'].dt.date
    daily_stats = df.groupby('date')['pnl_usd'].sum()
    monthly_stats = df.groupby(df['time'].dt.to_period('M'))['pnl_usd'].sum()
    
    avg_daily_gain = daily_stats[daily_stats > 0].mean()
    avg_monthly_gain = monthly_stats[monthly_stats > 0].mean()
    
    # Auto-run Unit Tests
    import subprocess
    print("\\n\\n==========================================")
    print("Running Mathematical Integrity Tests...")
    print("==========================================")
    test_res = subprocess.run(["C:\\\\Python314\\\\python.exe", "test_backtest_math.py"], capture_output=True, text=True)
    if test_res.returncode != 0:
        print("CRITICAL ERROR: Mathematical Integrity Tests Failed! Aborting report.")
        print(test_res.stderr)
        return
    print(test_res.stderr)
    print("Tests Passed! Math is 100% verified.")
    print("==========================================\\n\\n")

    log.info("="*60)
    log.info("REPORT COMPLETE -> %s", REPORT_PATH)
    log.info("Total Trades: %d | Win Rate: %.1f%% | Net P&L: $%.2f | ROI: %.2f%%",
             total_trades, total_wr, total_pnl, total_pnl/CAPITAL*100)
    log.info("Sharpe: %.2f | Max DD: %.2f%%", sharpe, max_dd*100)
    log.info("Avg Winning Day: +$%.2f | Avg Winning Month: +$%.2f", avg_daily_gain, avg_monthly_gain)
    log.info("="*60)'''

start = code.find('    log.info("="*60)')
end = code.find('    log.info("="*60)\n\n\nif __name__') + len('    log.info("="*60)')
if start != -1 and end != -1:
    code = code[:start] + new_log_logic + code[end:]
    with open('report_1year_results.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Patched logging logic with testing and stats")
else:
    print("Failed to find boundaries")
