import os

log_path = r"C:\25stragy\backtest_v7_TIERED_2LOTS_FINAL.log"
out_path = r"C:\25stragy\backtest_v7_TIERED_2LOTS_FINAL_utf8.log"

if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-16le') as f:
        content = f.read()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully converted log file to UTF-8.")
else:
    print("Log file not found.")
