import os

file_path = r"c:\anlyzeforex\forextele\live_strategy_executor.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                    mt5.order_send(request)
                    logging.info(f"[{symbol}] Strategy Step-Trail: Locked SL to {new_sl}")"""

replacement = """                    res = mt5.order_send(request)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        logging.info(f"[{symbol}] Strategy Step-Trail: Locked SL to {new_sl}")"""

content = content.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched live_strategy_executor.py successfully!")
