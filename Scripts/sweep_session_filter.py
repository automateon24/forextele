# sweep_session_filter.py
"""Sweep UTC block windows to find the most profitable trading schedule.

This script iterates over predefined hour‑range blocks, temporarily overwrites
`src/common/session_filter.py` with the block configuration, runs the full
concurrent backtest, extracts key performance metrics, and stores both a summary
CSV and the full markdown report for each run.

Assumptions:
- The project root is `c:\\anlyzeforex`.
- The virtual environment executable is `.venv\\Scripts\\python.exe`.
- The backtest script `scripts\\run_concurrent_grok_backtest.py` writes its
  report to `forextele\\reports\\concurrent_portfolio_backtest_report.md`.
"""
import os
import shutil
import subprocess
import re
import csv
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VENV_PY = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
BACKTEST_SCRIPT = os.path.join(PROJECT_ROOT, "forextele", "scripts", "run_concurrent_grok_backtest.py")
REPORT_MD = os.path.join(PROJECT_ROOT, "forextele", "reports", "concurrent_portfolio_backtest_report.md")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "forextele", "reports", "sweep_output")
CSV_PATH = os.path.join(PROJECT_ROOT, "forextele", "reports", "sweep_results.csv")
SESSION_FILTER_PATH = os.path.join(PROJECT_ROOT, "forextele", "src", "common", "session_filter.py")
BACKUP_FILTER_PATH = SESSION_FILTER_PATH + ".bak"

# Define the hour blocks we want to test – two‑hour windows (inclusive).
BLOCKS = [(h, h + 1) for h in range(0, 24, 2)]  # e.g., (0,1), (2,3), …, (22,23)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def backup_filter():
    shutil.copy2(SESSION_FILTER_PATH, BACKUP_FILTER_PATH)

def restore_filter():
    if os.path.exists(BACKUP_FILTER_PATH):
        shutil.move(BACKUP_FILTER_PATH, SESSION_FILTER_PATH)

def generate_filter_content(block_hours):
    """Return a string with the content of `session_filter.py` for a given set
    of blocked hour ranges. The original logic (blocking 21‑22, 11) is kept and
    the new `block_hours` are added as additional `if` statements.
    """
    lines = [
        '"""',
        'Institutional Session & Rollover Failure Gate',
        '===============================================',
        'Filters out high-loss time windows based on empirical failure analysis:',
        '- BLOCKS 21:00 - 22:59 UTC (NY Liquidity Drain & Broker Rollover Spread Spike)',
        '- BLOCKS 11:00 - 11:59 UTC (Pre‑US Economic News Trap)',
        '- ALLOWS Prime Windows: Asian Range (23:00-07:00), London (07:00-11:00), NY (12:30-18:00)',
        '"""',
        '',
        'from datetime import datetime',
        '',
        'def is_prime_trading_hour(dt: datetime) -> bool:',
        '    """',
        '    Returns True if UTC time is within high‑probability trading windows.',
        '    Returns False if UTC time falls in known failure dead zones.',
        '    """',
        '    hour = dt.hour',
        '',
        '    # 1. Block Market Rollover & NY Drain (21:00‑22:59 UTC)',
        '    if 21 <= hour <= 22:',
        '        return False',
        '',
        '    # 2. Block Pre‑US News Trap (11:00‑11:59 UTC)',
        '    if hour == 11:',
        '        return False',
    ]
    for start, end in block_hours:
        lines.extend([
            f'    # Custom block {start:02d}:00‑{end:02d}:59 UTC',
            f'    if {start} <= hour <= {end}:',
            '        return False',
            ''
        ])
    lines.append('    return True')
    lines.append('')
    return "\n".join(lines)

def run_backtest():
    result = subprocess.run([VENV_PY, BACKTEST_SCRIPT], cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print('Backtest failed:', result.stderr)
        return False
    return True

def parse_report(report_path):
    metrics = {'Profit Factor': '', 'Max Drawdown': '', 'Sharpe Ratio': ''}
    if not os.path.exists(report_path):
        return metrics
    with open(report_path, 'r', encoding='utf-8') as f:
        for line in f:
            for key in metrics.keys():
                if key.lower() in line.lower():
                    m = re.search(rf"{key}[:\s]+([0-9.+-]+)", line, re.IGNORECASE)
                    if m:
                        metrics[key] = m.group(1)
    return metrics

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['window', 'start_hour', 'end_hour', 'Profit Factor', 'Max Drawdown', 'Sharpe Ratio'])

def append_csv(row):
    with open(CSV_PATH, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(row)

def main():
    backup_filter()
    ensure_output_dir()
    try:
        for start, end in BLOCKS:
            custom_blocks = [(start, end)]
            new_content = generate_filter_content(custom_blocks)
            with open(SESSION_FILTER_PATH, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Running backtest with block {start:02d}-{end:02d} UTC ...')
            if not run_backtest():
                continue
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            dest_md = os.path.join(OUTPUT_DIR, f'window_{start:02d}_{end:02d}_{timestamp}.md')
            shutil.copy2(REPORT_MD, dest_md)
            metrics = parse_report(REPORT_MD)
            row = [f'{start:02d}-{end:02d}', start, end,
                   metrics.get('Profit Factor', ''),
                   metrics.get('Max Drawdown', ''),
                   metrics.get('Sharpe Ratio', '')]
            append_csv(row)
    finally:
        restore_filter()
        print('Original session filter restored.')

if __name__ == '__main__':
    main()
