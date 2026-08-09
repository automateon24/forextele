import os
import glob
import json
import httpx
import asyncio

SCRAPES_DIR = 'c:/anlyzeforex/forextele/artifacts/channel_scrapes'
OUT_DIR = 'c:/anlyzeforex/forextele/artifacts'

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.2"

PROMPT_TEMPLATE = """
You are a financial analyst AI. You are given a log of messages from a Telegram trading channel for a single day.
Analyze the messages and extract the following details in STRICT JSON FORMAT. Do not output anything outside the JSON.

{
  "category": "String (One of: 'Gold', 'Silver', 'Forex', 'Crypto', 'Mixed', 'Spam/None')",
  "total_signals": "Integer (How many distinct BUY or SELL signals were posted. Exclude 'TP Hit' or 'SL Hit' update messages)",
  "signals_list": "String (A short summary of the signals, e.g., 'BUY GOLD @ 2450 SL 2445 TP 2460' or 'SELL EURUSD @ CMP no SL' or 'None' if 0 signals)"
}

RULES:
- Output ONLY valid JSON. Nothing else.
- A signal must propose a NEW trade entry (e.g. 'Buy Gold', 'Long BTC', 'Sell EURUSD').
- 'TP hit' or 'Close half' are NOT new signals.
- If they say 'Buy at CMP' it is a valid signal.
- If there are no signals, total_signals is 0 and signals_list is 'None'.

CHANNEL MESSAGES:
{messages}
"""

async def query_ollama(client, text):
    if len(text) > 6000:
        text = text[-6000:]
        
    payload = {
        "model": MODEL,
        "prompt": PROMPT_TEMPLATE.replace("{messages}", text),
        "stream": False,
        "format": "json"
    }
    
    try:
        resp = await client.post(OLLAMA_URL, json=payload, timeout=120.0)
        resp.raise_for_status()
        res = resp.json().get("response", "").strip()
        return json.loads(res)
    except Exception as e:
        return {"category": "Error", "total_signals": 0, "signals_list": f"Exception: {str(e)}"}

async def process_account(client, acc_name, files):
    out_file = os.path.join(OUT_DIR, f"{acc_name.replace(' ', '')}_Analysis.md")
    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"# {acc_name} Channel Analysis\n\n")
        f.write("| Channel Name | Asset Class | Total Signals Today | Signal Details (Entry, SL, TP) |\n")
        f.write("|---|---|---|---|\n")
        f.flush()
        
        for idx, file in enumerate(files):
            filename = os.path.basename(file)
            ch_name = filename.replace(f"[{acc_name}] ", "").replace(".md", "")
            
            with open(file, 'r', encoding='utf-8') as sf:
                text = sf.read()
                
            print(f"[{idx+1}/{len(files)}] Analyzing: {ch_name[:30]}...".encode('ascii','ignore').decode())
            
            result = await query_ollama(client, text)
            
            cat = str(result.get('category', 'Unknown')).replace('|', '')
            tot = str(result.get('total_signals', '0')).replace('|', '')
            sigs = str(result.get('signals_list', 'None')).replace('\n', ' ').replace('|', '')
            
            f.write(f"| {ch_name} | {cat} | {tot} | {sigs} |\n")
            f.flush()

async def main():
    acc1_files = glob.glob(os.path.join(SCRAPES_DIR, "[Account 1]*.md"))
    acc2_files = glob.glob(os.path.join(SCRAPES_DIR, "[Account 2]*.md"))
    
    timeout = httpx.Timeout(120.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        await process_account(client, "Account 1", acc1_files)
        await process_account(client, "Account 2", acc2_files)
        
    print("ALL DONE!")

if __name__ == "__main__":
    asyncio.run(main())
