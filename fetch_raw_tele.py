import asyncio
from telethon import TelegramClient
from pathlib import Path
import shutil

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
ORIG_SESSION = BASE_DIR / "telegram_session.session"
SESSION_TEST = BASE_DIR / "telegram_session_raw.session"

if ORIG_SESSION.exists():
    shutil.copy2(ORIG_SESSION, SESSION_TEST)

API_ID = 15598350
API_HASH = "8cb282656e09b0983a9b71365b0813f4"

FOREX_GOLD_VIPS = [
    "scalping gold", "goldsnipers11", "sureshot fx", "sureshot gold", 
    "gold trade signals", "easy forex", "gold trader", "global gold insight",
    "global profit club", "gold_mast78", "forexero", "forexking1132"
]
CRYPTO_VIPS = [
    "market trader crypto", "coin chief", "binance killers", "crypto world updates",
    "binance 360", "dil se trader crypto", "cryptosimplicity", "crypto radar",
    "king crypto scalp", "earlypumpdetector"
]
ALL_VIPS = FOREX_GOLD_VIPS + CRYPTO_VIPS

async def main():
    client = TelegramClient(str(SESSION_TEST), API_ID, API_HASH)
    await client.start()
    dialogs = await client.get_dialogs()
    
    with open("raw_signals_today.txt", "w", encoding="utf-8") as f:
        count = 0
        for dialog in dialogs:
            title = getattr(dialog, 'title', '').lower()
            is_vip = any(vip in title for vip in ALL_VIPS)
            if is_vip:
                count += 1
                messages = await client.get_messages(dialog, limit=5)
                for msg in messages:
                    if msg.text and len(msg.text) > 15:
                        if "BUY" in msg.text.upper() or "SELL" in msg.text.upper() or "LONG" in msg.text.upper() or "SHORT" in msg.text.upper():
                            f.write(f"--- Channel: {dialog.title} ---\n")
                            f.write(msg.text + "\n\n")
                if count >= 15: break # Fetch from up to 15 channels
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
