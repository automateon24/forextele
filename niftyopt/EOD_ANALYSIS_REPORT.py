import sys
import os
import csv
import re
from datetime import datetime

TRADE_LOG_FILE = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
SYSTEM_LOG_FILE = r"C:\cursor\options\niftyopt\data\live_portfolio_trader.log"
OUTPUT_DIR = r"C:\cursor\options\niftyopt\data"

def run_eod_analysis(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    date_clean = date_str.replace("-", "")
    
    # 1. Load today's trades
    trades = []
    if os.path.exists(TRADE_LOG_FILE):
        try:
            with open(TRADE_LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Filter for today's trades
                    entry_time = row.get("entry_time", "")
                    if entry_time.startswith(date_str):
                        trades.append(row)
        except Exception as e:
            print(f"Error loading trades: {e}")
            
    # 2. Parse system logs for today's errors/warnings
    system_issues = []
    if os.path.exists(SYSTEM_LOG_FILE):
        try:
            # Match logs from today
            # Format: 2026-06-12 11:20:09,485 [ERROR] ...
            log_pattern = re.compile(rf"^{date_str} \d{{2}}:\d{{2}}:\d{{2}},\d{{3}} \[(ERROR|WARNING|CRITICAL|API_FAILED|RATE_LIMIT)\] (.*)")
            with open(SYSTEM_LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    match = log_pattern.match(line)
                    if match:
                        level, msg = match.groups()
                        system_issues.append(f"[{level}] {msg.strip()}")
        except Exception as e:
            print(f"Error loading logs: {e}")
            
    # 3. Aggregate statistics
    total_trades = len(trades)
    completed_trades = [t for t in trades if t.get("status") == "CLOSED"]
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    
    realized_pnl = sum(float(t.get("pnl_rs") or 0.0) for t in completed_trades)
    wins = [t for t in completed_trades if float(t.get("pnl_rs") or 0.0) > 0]
    losses = [t for t in completed_trades if float(t.get("pnl_rs") or 0.0) <= 0]
    
    win_rate = (len(wins) / len(completed_trades) * 100) if completed_trades else 0.0
    
    # Strategy Breakdown
    strat_perf = {}
    idx_perf = {}
    for t in completed_trades:
        strat = t.get("strategy", "UNKNOWN")
        idx = t.get("index", "UNKNOWN")
        pnl = float(t.get("pnl_rs") or 0.0)
        
        # Strategy grouping
        if strat not in strat_perf:
            strat_perf[strat] = {"pnl": 0.0, "trades": 0, "wins": 0}
        strat_perf[strat]["pnl"] += pnl
        strat_perf[strat]["trades"] += 1
        if pnl > 0:
            strat_perf[strat]["wins"] += 1
            
        # Index grouping
        if idx not in idx_perf:
            idx_perf[idx] = {"pnl": 0.0, "trades": 0, "wins": 0}
        idx_perf[idx]["pnl"] += pnl
        idx_perf[idx]["trades"] += 1
        if pnl > 0:
            idx_perf[idx]["wins"] += 1

    # 4. Generate Insights
    good_points = []
    bad_points = []
    improve_points = []
    
    # Rule-based Insights: What went good
    if realized_pnl > 0:
        good_points.append(f"The portfolio closed in profit with Rs. {realized_pnl:+,.2f} net PnL.")
    if win_rate > 50:
        good_points.append(f"Strong win rate of {win_rate:.1f}% across {len(completed_trades)} completed trades.")
    
    for strat, data in strat_perf.items():
        if data["pnl"] > 10000:
            good_points.append(f"Strategy '{strat}' was highly profitable, generating Rs. {data['pnl']:+,.2f} over {data['trades']} trades.")
        elif data["trades"] >= 2 and data["wins"] == data["trades"]:
            good_points.append(f"Strategy '{strat}' achieved 100% win rate across {data['trades']} trades.")
            
    for idx, data in idx_perf.items():
        if data["pnl"] > 10000:
            good_points.append(f"Index '{idx}' was a top contributor, yielding Rs. {data['pnl']:+,.2f} profit.")
            
    # Check for smooth TSL exits
    tsl_exits = sum(1 for t in completed_trades if t.get("exit_reason") == "TSL")
    if tsl_exits > 0:
        good_points.append(f"Successfully secured profits on {tsl_exits} trades using trailing stop loss (TSL).")

    if not good_points:
        good_points.append("Execution completed without critical runtime crashes.")

    # Rule-based Insights: What went wrong
    if realized_pnl < 0:
        bad_points.append(f"The portfolio closed in a net loss of Rs. {realized_pnl:+,.2f}.")
    
    for strat, data in strat_perf.items():
        if data["pnl"] < -10000:
            bad_points.append(f"Strategy '{strat}' suffered significant drawdowns, losing Rs. {data['pnl']:+,.2f}.")
            
    for idx, data in idx_perf.items():
        if data["pnl"] < -10000:
            bad_points.append(f"Index '{idx}' trading underperformed, causing Rs. {data['pnl']:+,.2f} in losses.")
            
    # Check for Stop Loss hits
    sl_exits = sum(1 for t in completed_trades if "SL" in t.get("exit_reason", ""))
    if sl_exits > 0:
        bad_points.append(f"{sl_exits} trades hit their stop loss (SPOT_SL / Premium SL).")
        
    # Rate limit warnings
    rate_limit_count = sum(1 for issue in system_issues if "rate limit" in issue.lower() or "805" in issue)
    if rate_limit_count > 0:
        bad_points.append(f"Dhan API rate limit limits (805) were encountered {rate_limit_count} times.")
        
    if not bad_points:
        bad_points.append("No major losses or engine failures occurred today.")

    # Rule-based Insights: What can be improved
    if sl_exits > len(completed_trades) * 0.4:
        improve_points.append("High ratio of SL hits. Review the regime filter parameters or entry thresholds to avoid premature stops.")
    if rate_limit_count > 5:
        improve_points.append("Frequently hit Dhan API rate limits. Consider increasing the cooldown polling intervals in the web dashboard or consolidating scan queries.")
    
    # TSL adjustment suggestion
    stopped_out_early = 0
    for t in completed_trades:
        entry = float(t.get("entry_price") or 0.0)
        highest = float(t.get("highest_premium") or 0.0)
        exit_px = float(t.get("exit_price") or 0.0)
        pnl = float(t.get("pnl_rs") or 0.0)
        if entry > 0 and highest > entry * 1.15 and pnl <= 0:
            stopped_out_early += 1
            
    if stopped_out_early > 0:
        improve_points.append(f"In {stopped_out_early} trades, premiums jumped >15% but eventually stopped out in a loss/breakeven. Consider tightening the TSL activation point or locking profits earlier.")

    if not improve_points:
        improve_points.append("Maintain the current configuration and monitor performance in the upcoming sessions.")

    # 5. Build Report String
    report = []
    report.append("=" * 80)
    report.append(f" EOD PERFORMANCE & SYSTEM AUDIT REPORT - {date_str}")
    report.append("=" * 80)
    report.append(f" Date of Run       : {date_str}")
    report.append(f" Today Net P&L     : Rs. {realized_pnl:+,.2f}")
    report.append(f" Total Trades      : {total_trades} (Completed: {len(completed_trades)}, Open: {len(open_trades)})")
    report.append(f" Wins              : {len(wins)} | Losses: {len(losses)} | Win Rate: {win_rate:.1f}%")
    report.append("-" * 80)
    
    report.append("\nINDEX-WISE PERFORMANCE BREAKDOWN:")
    report.append(f"  {'Index':<12} | {'Trades':<8} | {'Wins':<6} | {'Win Rate':<8} | {'PnL (Rs.)'}")
    report.append("  " + "-" * 55)
    for idx, data in idx_perf.items():
        idx_wr = (data["wins"] / data["trades"] * 100) if data["trades"] else 0.0
        report.append(f"  {idx:<12} | {data['trades']:<8} | {data['wins']:<6} | {idx_wr:>7.1f}% | Rs. {data['pnl']:+,.2f}")
        
    report.append("\nSTRATEGY PERFORMANCE BREAKDOWN:")
    report.append(f"  {'Strategy':<25} | {'Trades':<8} | {'Wins':<6} | {'Win Rate':<8} | {'PnL (Rs.)'}")
    report.append("  " + "-" * 65)
    for strat, data in strat_perf.items():
        strat_wr = (data["wins"] / data["trades"] * 100) if data["trades"] else 0.0
        report.append(f"  {strat:<25} | {data['trades']:<8} | {data['wins']:<6} | {strat_wr:>7.1f}% | Rs. {data['pnl']:+,.2f}")

    report.append("\n" + "=" * 80)
    report.append(" LEARNINGS ++ LOG (SWOT ANALYSIS)")
    report.append("=" * 80)
    
    report.append("\nWHAT WENT GOOD (AS PLANNED):")
    for pt in good_points:
        report.append(f"  ✔ {pt}")
        
    report.append("\nWHAT WENT WRONG (OUT OF TRACK):")
    for pt in bad_points:
        report.append(f"  ❌ {pt}")
        
    report.append("\nWHAT CAN BE IMPROVED (ACTIONABLE INSIGHTS):")
    for pt in improve_points:
        report.append(f"  💡 {pt}")

    report.append("\n" + "=" * 80)
    report.append(" SYSTEM ISSUES & CONNECTION LOGS AUDIT (BUGS FOUND)")
    report.append("=" * 80)
    if system_issues:
        # Deduplicate and count occurrences to keep it concise
        issue_counts = {}
        for issue in system_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        for issue, count in issue_counts.items():
            report.append(f"  • {issue} (Occurred {count} times)")
    else:
        report.append("  • No system errors, API failures, or rate-limiting warnings found in the log.")
        
    report.append("\n" + "=" * 80)
    report.append(" End of Report")
    report.append("=" * 80)
    
    report_content = "\n".join(report)
    
    # Save report to file
    out_file = os.path.join(OUTPUT_DIR, f"daily_analysis_{date_clean}.log")
    try:
        with open(out_file, "w", encoding="utf-8") as out_f:
            out_f.write(report_content)
        print(f"Report saved to {out_file}")
    except Exception as e:
        print(f"Error saving report to file: {e}")
        
    # Trigger EOD self-tuning parameter optimization
    try:
        from eod_optimizer import run_eod_optimization
        print("Reviewing previous AI learning logs before starting tuning...")
        run_eod_optimization()
    except Exception as e:
        print(f"Error triggering self-tuning optimization: {e}")

    # Trigger Full Offline Backtest comparison against Actuals
    try:
        print("Running Actual vs Downloaded Data Backtest Module...")
        import sys
        if r'C:\25stragy' not in sys.path: 
            sys.path.append(r'C:\25stragy')
        from eod_backtest_learning import run_eod_learning_loop
        run_eod_learning_loop()
    except Exception as e:
        print(f"Error triggering actual vs backtest learning loop: {e}")

    # Trigger Telegram EOD Analysis
    try:
        import sys
        if r'C:\25stragy' not in sys.path: 
            sys.path.append(r'C:\25stragy')
        from telegram_eod_analyzer import run_daily_telegram_analysis
        run_daily_telegram_analysis()
    except Exception as e:
        print(f'Error triggering Telegram EOD analysis: {e}')

    return report_content

if __name__ == "__main__":
    dt = sys.argv[1] if len(sys.argv) > 1 else None
    run_eod_analysis(dt)
