import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

input_path = r"C:\25stragy\scratch\strategy_files.txt"
if os.path.exists(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    
    print("=== Active Strategy/Backtest Files (Non-Backup) ===")
    filtered = []
    for line in lines:
        if "backups" not in line.lower():
            filtered.append(line)
            print(f"  {line}")
            
    with open(r"C:\25stragy\scratch\active_strategy_files.txt", "w", encoding="utf-8") as f_out:
        for fp in filtered:
            f_out.write(fp + "\n")
else:
    print("strategy_files.txt not found")
