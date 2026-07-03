import os
import shutil
import subprocess
import re

def main():
    # Restore backup_v10_optimized_nifty_regime
    src_dir = "C:\\25stragy\\backups\\backup_v10_optimized_nifty_regime"
    for f in ["BACKTEST_V8_AI.py", "config.json", "strategy_dna.json"]:
        shutil.copy(os.path.join(src_dir, f), f"C:\\25stragy\\{f}")
        
    # Modify BACKTEST_V8_AI.py to use dynamic lot sizing
    file_path = "C:\\25stragy\\BACKTEST_V8_AI.py"
    with open(file_path, "r") as f:
        content = f.read()
        
    target = "                    # Dynamic lot sizing loaded from config\n                    actual_lots = MAX_TEST_LOTS"
    replacement = "                    # Dynamic lot sizing loaded from config\n                    lot_multiplier = config_db[\"system\"].get(\"lot_multiplier\", 1.0)\n                    actual_lots = int(get_base_lots(strat.name) * lot_multiplier)"
    content = content.replace(target, replacement)
    
    with open(file_path, "w") as f:
        f.write(content)
        
    # Modify config.json to have lot_multiplier = 3.0 and circuit_breaker = -999999
    config_path = "C:\\25stragy\\config.json"
    with open(config_path, "r") as f:
        cfg_content = f.read()
        
    cfg_content = cfg_content.replace(
        '"daily_circuit_breaker_rs": -10000',
        '"daily_circuit_breaker_rs": -999999,\n    "lot_multiplier": 3.0'
    )
    with open(config_path, "w") as f:
        f.write(cfg_content)
        
    # Run the backtest
    env = os.environ.copy()
    if "NUM_DAYS_LIMIT" in env:
        del env["NUM_DAYS_LIMIT"]
        
    print("Running backtest with NO circuit breaker...")
    proc = subprocess.run(
        ["C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", "BACKTEST_V8_AI.py"],
        cwd="C:\\25stragy",
        env=env,
        capture_output=True,
        text=True
    )
    
    with open("scratch/backup_no_cb_test_out.txt", "w") as f:
        f.write(proc.stdout)
        
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
