import os
import shutil
import subprocess
import re

def main():
    # Restore BACKTEST_V8_AI.py from backup_2026-06-06_2010_multilot
    shutil.copy(
        "C:\\25stragy\\backups\\backup_2026-06-06_2010_multilot\\BACKTEST_V8_AI.py",
        "C:\\25stragy\\BACKTEST_V8_AI.py"
    )
    print("Restored BACKTEST_V8_AI.py from backup_2026-06-06_2010_multilot")
    
    # Modify BACKTEST_V8_AI.py to use multiplier 3 instead of CAPITAL // 100_000
    file_path = "C:\\25stragy\\BACKTEST_V8_AI.py"
    with open(file_path, "r") as f:
        content = f.read()
        
    # Replace the lot scaling line
    target = "                    actual_lots = get_base_lots(strat.name) * (CAPITAL // 100_000)"
    replacement = "                    actual_lots = get_base_lots(strat.name) * 3"
    
    if target in content:
        content = content.replace(target, replacement)
        print("Updated lot sizing to multiplier 3.")
    else:
        print("ERROR: Target line not found in BACKTEST_V8_AI.py")
        
    with open(file_path, "w") as f:
        f.write(content)
        
    # Run the backtest
    env = os.environ.copy()
    if "NUM_DAYS_LIMIT" in env:
        del env["NUM_DAYS_LIMIT"]
        
    print("Running full backtest for multilot...")
    proc = subprocess.run(
        ["C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", "BACKTEST_V8_AI.py"],
        cwd="C:\\25stragy",
        env=env,
        capture_output=True,
        text=True
    )
    
    with open("scratch/backup_multilot_test_out.txt", "w") as f:
        f.write(proc.stdout)
    print("Output saved to scratch/backup_multilot_test_out.txt")
    
    stdout = proc.stdout
    trades_match = re.search(r'Trades\s*:\s*(\d+)', stdout)
    wr_match = re.search(r'Win rate\s*:\s*([\d\.]+)%', stdout)
    pnl_match = re.search(r'Total PnL\s*:\s*Rs\.([\+\-]?[\d,]+)', stdout)
    dd_match = re.search(r'Max Drawdown\s*:\s*Rs\.([\+\-]?[\d,]+)', stdout)
    
    print("\n=== RUN RESULTS ===")
    if trades_match:
        print(f"Trades: {trades_match.group(1)}")
    if wr_match:
        print(f"Win Rate: {wr_match.group(1)}%")
    if pnl_match:
        print(f"Total PnL: Rs. {pnl_match.group(1)}")
    if dd_match:
        print(f"Max Drawdown: Rs. {dd_match.group(1)}")

if __name__ == "__main__":
    main()
