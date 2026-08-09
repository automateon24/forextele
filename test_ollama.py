import asyncio
import httpx
import json

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.2"

PROMPT_TEMPLATE = """
You are a financial analyst AI. You are given a log of messages from a Telegram trading channel for a single day.
Analyze the messages and extract the following details in STRICT JSON FORMAT. Do not output anything outside the JSON.

{
  "category": "String (One of: 'Gold', 'Silver', 'Forex', 'Crypto', 'Mixed', 'Spam/None')",
  "total_signals": 0,
  "signals_list": "String (A short summary of the signals, e.g., 'BUY GOLD @ 2450 SL 2445 TP 2460' or 'None' if 0 signals)"
}

RULES:
- Output ONLY valid JSON.
- If there are no signals, total_signals is 0 and signals_list is 'None'.

CHANNEL MESSAGES:
{messages}
"""

async def test_one():
    with open('c:/anlyzeforex/forextele/artifacts/channel_scrapes/[Account 1] A.R.S. CRYPTO  FOREX™.md', 'r', encoding='utf-8') as f:
        text = f.read()
        
    payload = {
        "model": MODEL,
        "prompt": PROMPT_TEMPLATE.replace("{messages}", text),
        "stream": False,
        "format": "json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print("Sending request to Ollama...")
            resp = await client.post(OLLAMA_URL, json=payload, timeout=60.0)
            print(f"Status: {resp.status_code}")
            res = resp.json().get("response", "").strip()
            print(f"RAW OLLAMA OUTPUT:\n{res}")
            
            data = json.loads(res)
            print(f"PARSED JSON: {data}")
        except Exception as e:
            print(f"EXCEPTION: {e}")

asyncio.run(test_one())
