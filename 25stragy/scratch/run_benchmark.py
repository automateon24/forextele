import subprocess
import os
import json
import pandas as pd

def run_benchmark():
    print("Running 30-day benchmark backtest...")
    env = os.environ.copy()
    env["NUM_DAYS_LIMIT"] = "30"
    
    proc = subprocess.run(
        ["C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", "BACKTEST_V8_AI.py"],
        cwd="C:\\25stragy",
        env=env,
        capture_output=True,
        text=True
    )
    
    # Save output
    os.makedirs("C:\\25stragy\\scratch", exist_ok=True)
    with open("C:\\25stragy\\scratch\\benchmark_stdout.txt", "w", encoding="utf-8") as f:
        f.write(proc.stdout)
    with open("C:\\25stragy\\scratch\\benchmark_stderr.txt", "w", encoding="utf-8") as f:
        f.write(proc.stderr)
        
    print(f"Benchmark run complete. Exit code: {proc.returncode}")
    
    # Parse and print summary
    lines = proc.stdout.split("\n")
    found_summary = False
    for line in lines:
        if "PER INDEX:" in line:
            found_summary = True
        if found_summary:
            print(line)
            if "PER STRATEGY" in line:
                break

if __name__ == "__main__":
    run_benchmark()
