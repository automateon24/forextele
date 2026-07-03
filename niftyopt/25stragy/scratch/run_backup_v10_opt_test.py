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
    # Restore backup_2026-06-07_v10_optimizations
    restore_backup("backup_2026-06-07_v10_optimizations")
    
    # Modify BACKTEST_V8_AI.py to use dynamic lot sizing
    file_path = "C:\\25stragy\\BACKTEST_V8_AI.py"
    with open(file_path, "r") as f:
        content = f.read()
        
    # Find and replace static lot sizing
    target = "                    # Dynamic lot sizing loaded from config\n                    actual_lots = MAX_TEST_LOTS"
    replacement = "                    # Dynamic lot sizing loaded from config\n                    lot_multiplier = config_db[\"system\"].get(\"lot_multiplier\", 1.0)\n                    actual_lots = int(get_base_lots(strat.name) * lot_multiplier)"
    
    if target in content:
        content = content.replace(target, replacement)
        print("Updated BACKTEST_V8_AI.py with dynamic sizing.")
    else:
        print("ERROR: Target string not found in BACKTEST_V8_AI.py")
        
    with open(file_path, "w") as f:
        f.write(content)
        
    # Make sure lot_multiplier is in config.json
    config_path = "C:\\25stragy\\config.json"
    with open(config_path, "r") as f:
        cfg_content = f.read()
    
    # We can replace daily_circuit_breaker_rs as well
    cfg_content = cfg_content.replace(
        '"daily_circuit_breaker_rs": -10000',
        '"daily_circuit_breaker_rs": -25000,\n    "lot_multiplier": 3.0'
    )
    with open(config_path, "w") as f:
        f.write(cfg_content)
    print("Updated config.json with lot_multiplier.")
        
    # Run the backtest
    env = os.environ.copy()
    if "NUM_DAYS_LIMIT" in env:
        del env["NUM_DAYS_LIMIT"]
        
    print("Running full backtest for v10_optimizations...")
    proc = subprocess.run(
        ["C:\\Users\\Administrator\\AppData\Local\\Programs\\Python\\Python311\\python.exe", "BACKTEST_V8_AI.py"],
        cwd="C:\\25stragy",
        env=env,
        capture_output=True,
        text=True
    )
    
    with open("scratch/backup_v10_opt_test_out.txt", "w") as f:
        f.write(proc.stdout)
    print("Output saved to scratch/backup_v10_opt_test_out.txt")
    
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
