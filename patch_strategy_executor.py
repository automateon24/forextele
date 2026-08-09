import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

dumper_code = """
def status_dumper_loop():
    import time
    import json
    while True:
        try:
            with open(BASE_DIR / "thread_status.json", "w") as f:
                json.dump(THREAD_STATUS, f)
        except: pass
        time.sleep(5)

def run_live_engine():"""

if "def status_dumper_loop():" not in code:
    code = code.replace("def run_live_engine():", dumper_code)
    code = code.replace("futures[executor.submit(strategy_pnl_tracker)] = \"PNL_TRACKER\"", 
                        "futures[executor.submit(strategy_pnl_tracker)] = \"PNL_TRACKER\"\n    futures[executor.submit(status_dumper_loop)] = \"STATUS_DUMPER\"")
    with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Injected status_dumper_loop into live_strategy_executor.py!")
else:
    print("status_dumper_loop already injected!")
