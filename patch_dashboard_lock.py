import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

find_tg = """def get_telegram_status():
    async def check():
        client = TelegramClient(str(SESSION_FILE), TELEGRAM_API_ID, TELEGRAM_API_HASH)
        try:
            await client.connect()
            authorized = await client.is_user_authorized()
            await client.disconnect()
            return authorized
        except Exception as e:
            return str(e)
    return asyncio.run(check())"""

replace_tg = """def get_telegram_status():
    status_file = BASE_DIR / "telegram_status.json"
    if status_file.exists():
        try:
            import json, time
            from pathlib import Path
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return True if data.get("status") == "Running" else "Stopped"
        except Exception as e:
            return str(e)
    return "Unknown" """

code = code.replace(find_tg, replace_tg)

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed telegram status database lock in dashboard_flask.py!")
