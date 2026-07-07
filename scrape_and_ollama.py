import asyncio
from telethon import TelegramClient
from datetime import datetime, timedelta, timezone
import json
import httpx
from pathlib import Path

# API credentials
api_id = 15598350
api_hash = "8cb282656e09b0983a9b71365b0813f4"
session_file = 'c:/anlyzeforex/forextele/telegram_session_backup'

channel_map = {
    "-1001582520126": "Scalping Gold",
    "goldsnipers11": "GOLD Snipers",
    "Marketradercrypto": "Market Trader Crypto Forex",
    "sureshot_fx": "Sureshot FX",
    "-1001661400724": "SureShot GOLD (VIP)",
    "-1001986940315": "GOLD TRADE SIGNALS",
    "-1002871728862": "ZERO TO HERO PRIMIUM GROUP",
    "tradebussunessfx_007": "tradebussunessfx_007",
    "-1001520053536": "Coin Chief",
    "-1001234364040": "Binance Killers VIP",
    "-1001652601224": "Crypto World Updates",
    "-1001553551852": "Binance 360",
    "-1002471742018": "DIL SE TRADER Crypto",
    "-1001737978232": "CryptoSimplicity News",
    "-1001754095061": "Crypto Radar",
    "-1001422000261": "Sureshot FX VIP",
    "GOLD_MAST78": "GOLD_MAST78",
    "forexero": "forexero",
    "forexking1132": "forexking1132",
    "earlypumpdetector": "earlypumpdetector",
    "-1001704062350": "King Crypto Scalp [ LIVE ]",
    "-1001178704438": "GLOBAL PROFIT CLUB",
    "-1002458369770": "EASY FOREX",
    "-1001260601611": "GOLD TRADER",
    "-1001495198097": "GLOBAL GOLD INSIGHT"
}

sem = asyncio.Semaphore(2)

async def ask_ollama(prompt: str) -> str:
    async with sem:
        try:
            endpoint = "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_thread": 4}
            }
            async with httpx.AsyncClient(timeout=45.0) as http_client:
                resp = await http_client.post(endpoint, json=payload)
                resp.raise_for_status()
                return resp.json()["response"].strip()
        except Exception as e:
            return f"OLLAMA_ERROR: {e}"

def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading assistant. The following Telegram message came from the channel \"{channel_name}\". "
        f"It may contain a trade signal, a promotion, or just chatter.\n"
        f"If it contains a *real* trade signal, respond with **exactly** one line in the form:\n"
        f"    ACTION SYMBOL ENTRY_PRICE SL TP\n"
        f"where ACTION is BUY or SELL, SYMBOL is like EURUSD or GBPJPY (use GOLD for XAU). ENTRY_PRICE, SL, and TP are numbers. If SL or TP is not given, output 0.\n"
        f"If there is no genuine trade, reply with the single word: NO_TRADE.\n"
        f"Message:\n{message}"
    )

async def process_channel(client, channel_id, channel_name, time_limit):
    results = []
    try:
        try: entity = int(channel_id)
        except ValueError: entity = channel_id
            
        messages = await client.get_messages(entity, limit=50)
        valid_messages = [msg for msg in messages if msg.date >= time_limit and msg.text]
        
        for msg in valid_messages:
            prompt = build_prompt(msg.text, channel_name)
            response = await ask_ollama(prompt)
            print(f"[{channel_name}] Processed message. AI Response: {response}", flush=True)
            if "NO_TRADE" not in response and "OLLAMA_ERROR" not in response:
                results.append(f"[{channel_name}] [{msg.date.strftime('%Y-%m-%d %H:%M:%S UTC')}] RAW: {msg.text.replace(chr(10), ' ')} -> AI PARSED: {response}")
                
    except Exception as e:
        pass
        
    return results

async def main():
    print("Connecting to Telegram...", flush=True)
    client = TelegramClient(session_file, api_id, api_hash)
    await client.start()
    
    time_limit = datetime.now(timezone.utc) - timedelta(hours=24)
    all_results = []
    
    print("Processing channels with Ollama...", flush=True)
    tasks = []
    for cid, cname in channel_map.items():
        tasks.append(process_channel(client, cid, cname, time_limit))
        
    results = await asyncio.gather(*tasks)
    for res in results:
        all_results.extend(res)
        
    await client.disconnect()
    
    with open("c:/anlyzeforex/forextele/telegram_ollama_report.txt", "w", encoding="utf-8") as f:
        f.write("=== OLLAMA EXTRACTED SIGNALS (LAST 24 HOURS) ===\n\n")
        f.write("\n".join(all_results))
        
    print(f"Done! {len(all_results)} valid signals found by Ollama.")

if __name__ == "__main__":
    asyncio.run(main())
