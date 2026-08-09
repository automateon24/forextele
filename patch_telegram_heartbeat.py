import re

with open('telegram_signal_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

find_heartbeat = """async def main():
    log.info("Booting Autonomous Dual-Account Telegram Listener...")"""

replace_heartbeat = """async def heartbeat_loop():
    while True:
        try:
            status_file = BASE_DIR / "telegram_status.json"
            with open(status_file, "w") as f:
                import time
                json.dump({"last_heartbeat": time.time(), "status": "Active"}, f)
        except: pass
        await asyncio.sleep(10)

async def main():
    asyncio.create_task(heartbeat_loop())
    log.info("Booting Autonomous Dual-Account Telegram Listener...")"""

if "async def heartbeat_loop()" not in code:
    code = code.replace(find_heartbeat, replace_heartbeat)
    with open('telegram_signal_engine.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Injected Telegram Heartbeat!")
else:
    print("Already injected!")
