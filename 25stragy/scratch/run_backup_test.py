import os
import shutil
import subprocess
import re

def restore_backup(backup_name):
    src_dir = f"C:\\25stragy\\backups\\{backup_name}"
    for f in ["BACKTEST_V8_AI.py", "config.json", "strategy_dna.json"]:
        src_path = os.path.join(src_dir, f)
        if os.path.exists(src_path):
            shutil.copy(src_path, f"C:\\25stragy\\{f}")
            print(f"Restored {f} from {backup_name}")

def main():
    # Restore backup_v10_optimized_nifty_regime
    restore_backup("backup_v10_optimized_nifty_regime")
    
    # Run the backtest without NUM_DAYS_LIMIT (full 155 days)
    env = os.environ.copy()
    if "NUM_DAYS_LIMIT" in env:
        del env["NUM_DAYS_LIMIT"]
        
    print("Running full backtest (155 days)...")
    proc = subprocess.run(
        ["C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", "BACKTEST_V8_AI.py"],
        cwd="C:\\25stragy",
        env=env,
        capture_output=True,
        text=True
    )
    
    # Save the output
    with open("scratch/backup_test_out.txt", "w") as f:
        f.write(proc.stdout)
        
    print("Output saved to scratch/backup_test_out.txt")
    
    # Parse PnL
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
