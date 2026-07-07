import subprocess
import sys
import threading
import os

# Ensure we are running in the correct directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

scripts = {
    "DASHBOARD": "dashboard_flask.py",
    "TELEGRAM": "live_order_executor.py",
    "STRATEGY": "live_strategy_executor.py"
}

processes = []

def read_output(process, prefix):
    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"[{prefix}] {line.strip()}", flush=True)

def main():
    print("=======================================")
    print("  Starting Master Forex Engine Runner  ")
    print("=======================================")
    
    # Spawn each script
    for name, script in scripts.items():
        print(f"[*] Launching {name} ({script})...", flush=True)
        # We use unbuffered output so we get logs immediately
        p = subprocess.Popen(
            [sys.executable, "-u", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(p)
        
        # Start a thread to read and print output
        t = threading.Thread(target=read_output, args=(p, name), daemon=True)
        t.start()
        
    print("\n[SUCCESS] All services started in background! Aggregating logs below:\n", flush=True)
    
    # Wait for all processes to finish (which should be never, unless they crash)
    for p in processes:
        p.wait()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down all processes...")
        for p in processes:
            p.terminate()
