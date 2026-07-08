import asyncio
from telethon import TelegramClient
from pathlib import Path
import json
import httpx
import shutil

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
ORIG_SESSION = BASE_DIR / "telegram_session.session"
SESSION_TEST = BASE_DIR / "telegram_session_test.session"

# Clone DB to avoid database locking!
if ORIG_SESSION.exists():
    shutil.copy2(ORIG_SESSION, SESSION_TEST)

PROMPTS_FILE = BASE_DIR / "swarm_prompts.json"

API_ID_1 = 15598350
API_HASH_1 = "8cb282656e09b0983a9b71365b0813f4"

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

with open(PROMPTS_FILE, "r") as f:
    prompts = json.load(f)

async def _ask_ollama(system_prompt: str, user_text: str) -> str:
    full_prompt = f"{system_prompt}\n\nUSER INPUT:\n{user_text}"
    payload = {
        "model": "llama3.2",
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            resp = await client.post("http://127.0.0.1:11434/api/generate", json=payload)
            return resp.json().get("response", "").strip()
        except: 
            return ""

async def main():
    print("Connecting to Cloned Account 1 Session...")
    client1 = TelegramClient(str(SESSION_TEST), API_ID_1, API_HASH_1)
    await client1.start()
    
    print("Fetching recent channels...")
    dialogs = await client1.get_dialogs()
    results = []
    
    scraped_count = 0
    for dialog in dialogs:
        title = getattr(dialog, 'title', '').lower()
        if not title: continue
        
        is_vip = False
        for vip in ALL_VIPS:
            if vip in title:
                is_vip = True
                break
                
        if is_vip:
            if scraped_count >= 5: break # Don't take too long, just scrape 5 channels for a quick sample
            
            print(f"Scraping channel: {dialog.title}...")
            messages = await client1.get_messages(dialog, limit=3) # Grab 3 messages
            scraped_count += 1
            for msg in messages:
                if msg.text and len(msg.text) > 15:
                    watcher_resp = await _ask_ollama(prompts["WATCHER_PROMPT"], msg.text)
                    try:
                        clean = watcher_resp.replace("```json", "").replace("```", "").strip()
                        w_data = json.loads(clean)
                        cls = w_data.get("classification")
                        if cls == "NEW_TRADE":
                            trigger_resp = await _ask_ollama(prompts["TRIGGER_PROMPT"], msg.text)
                            clean_t = trigger_resp.replace("```json", "").replace("```", "").strip()
                            t_data = json.loads(clean_t)
                            results.append({
                                "channel": dialog.title,
                                "raw_text": msg.text,
                                "extracted_trade": t_data
                            })
                            print(f"  -> [SUCCESS] Extracted Trade: {t_data['action']} {t_data.get('symbol')} @ {t_data.get('entry')}")
                    except Exception as e:
                        pass
                        
    await client1.disconnect()
    
    with open("scraped_orders.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"\nCompleted scraping. Found {len(results)} valid trades.")

if __name__ == "__main__":
    asyncio.run(main())
