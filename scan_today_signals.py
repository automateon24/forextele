import asyncio
import json
import os
import shutil
import httpx
from datetime import datetime, timezone
from telethon import TelegramClient
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config_telegram.json")
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

ORIGINAL_SESSION = os.path.join(BASE_DIR, "telegram_session2.session")
TEMP_SESSION = os.path.join(BASE_DIR, "temp_scan.session")
shutil.copy2(ORIGINAL_SESSION, TEMP_SESSION)

CHANNEL_MAP = {
    "-1001582520126": "Scalping Gold", "goldsnipers11": "GOLD Snipers",
    "Marketradercrypto": "Market Trader Crypto Forex", "sureshot_fx": "Sureshot FX",
    "-1001661400724": "SureShot GOLD (VIP)", "-1001986940315": "GOLD TRADE SIGNALS",
    "-1002871728862": "ZERO TO HERO PRIMIUM GROUP", "-1001520053536": "Coin Chief",
    "-1001234364040": "Binance Killers VIP", "-1001652601224": "Crypto World Updates",
    "-1001553551852": "Binance 360", "-1002471742018": "DIL SE TRADER Crypto",
    "-1001737978232": "CryptoSimplicity News", "-1001754095061": "Crypto Radar",
    "-1001422000261": "Sureshot FX VIP", "GOLD_MAST78": "GOLD_MAST78",
    "forexero": "forexero", "forexking1132": "forexking1132",
    "earlypumpdetector": "earlypumpdetector", "-1001704062350": "King Crypto Scalp [ LIVE ]",
    "-1001178704438": "GLOBAL PROFIT CLUB", "-1002458369770": "EASY FOREX",
    "-1001260601611": "GOLD TRADER", "-1001495198097": "GLOBAL GOLD INSIGHT"
}

def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading assistant. The following Telegram message came from the channel \"{channel_name}\". "
        f"It may contain a trade signal, a promotion, or just chatter.\n"
        f"If it contains a *real* trade signal, respond with **exactly** one line in the form:\n"
        f"    ACTION SYMBOL ENTRY_PRICE [LOT]\n"
        f"where ACTION is BUY or SELL, SYMBOL is like EURUSD or GBPJPY. IMPORTANT: If the signal is for Gold (XAUUSD, XAU, etc), use the symbol GOLD. ENTRY_PRICE is a number, and LOT is optional. "
        f"If there is no genuine trade, reply with the single word: NO_TRADE.\n"
        f"Message:\n{message}"
    )

async def ask_ai(client: httpx.AsyncClient, prompt: str, msg_date, ch_name):
    endpoint = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "llama3.2", "prompt": prompt, "stream": False,
        "options": {"temperature": 0.0, "num_thread": 4}
    }
    try:
        resp = await client.post(endpoint, json=payload, timeout=30.0)
        if resp.status_code == 200:
            return (ch_name, msg_date, resp.json()["response"].strip())
    except Exception:
        pass
    return (ch_name, msg_date, "NO_TRADE")

async def main():
    client = TelegramClient(TEMP_SESSION, config["api_id"], config["api_hash"])
    await client.connect()
    
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    chat_list = [int(k) if str(k).lstrip('-').isdigit() else k for k in CHANNEL_MAP.keys()]
    
    tasks = []
    total_msgs = 0
    
    async with httpx.AsyncClient() as http_client:
        for chat_id in chat_list:
            ch_name = CHANNEL_MAP.get(str(chat_id), str(chat_id))
            try:
                entity = await client.get_entity(chat_id)
                messages = await client.get_messages(entity, limit=10) # 10 messages max per channel for speed
                for msg in messages:
                    if msg.date > today and msg.text:
                        total_msgs += 1
                        prompt = build_prompt(msg.text, ch_name)
                        tasks.append(ask_ai(http_client, prompt, msg.date, ch_name))
            except Exception:
                pass
                
        print(f"Scanning {total_msgs} messages concurrently via Ollama...")
        responses = await asyncio.gather(*tasks)

    await client.disconnect()
    
    try:
        os.remove(TEMP_SESSION)
        os.remove(TEMP_SESSION + "-journal")
    except:
        pass
        
    results = defaultdict(list)
    total_signals = 0
    
    for ch_name, date, ai_reply in responses:
        if "NO_TRADE" not in ai_reply.upper():
            results[ch_name].append(f"[{date.strftime('%H:%M')}] {ai_reply}")
            total_signals += 1

    print("\n=======================================================")
    print(f"OLLAMA HISTORICAL SCAN COMPLETE")
    print(f"Scanned {total_msgs} messages today. Found {total_signals} real signals.")
    print("=======================================================\n")
    
    for ch, signals in results.items():
        print(f"[{ch}] : {len(signals)} signals")
        for s in signals:
            print(f"   -> {s}")

if __name__ == "__main__":
    asyncio.run(main())
