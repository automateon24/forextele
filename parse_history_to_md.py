import json
import httpx
from pathlib import Path
import asyncio

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
HISTORY_FILE = BASE_DIR / "telegram_history_15days.json"
PROMPTS_FILE = BASE_DIR / "swarm_prompts.json"

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
        except: return ""

async def main():
    if not HISTORY_FILE.exists():
        print("History file not found.")
        return
        
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
        
    trade_msgs = []
    for entry in history:
        msg = entry.get("text", "")
        if "BUY" in msg.upper() or "SELL" in msg.upper():
            if "SL" in msg.upper() or "TP" in msg.upper():
                trade_msgs.append(entry)
                
    trade_msgs = trade_msgs[-10:]
    
    md_content = "# Telegram Signal Extraction Report (Last 24-48 Hours)\n\n"
    md_content += "| Channel | Signal Text | Action | Symbol | Entry | SL | TP1 |\n"
    md_content += "|---------|-------------|--------|--------|-------|----|-----|\n"
    
    print(f"Testing {len(trade_msgs)} historical signals...")
    for entry in trade_msgs:
        channel = entry.get("channel_id", "Unknown")
        text = entry.get("text", "")
        short_text = text.replace("\n", " ").replace("|", " ")[:40] + "..."
        
        watcher_resp = await _ask_ollama(prompts["WATCHER_PROMPT"], text)
        try:
            clean = watcher_resp.replace("```json", "").replace("```", "").strip()
            w_data = json.loads(clean)
            if w_data.get("classification") == "NEW_TRADE":
                trigger_resp = await _ask_ollama(prompts["TRIGGER_PROMPT"], text)
                clean_t = trigger_resp.replace("```json", "").replace("```", "").strip()
                t_data = json.loads(clean_t)
                
                action = t_data.get("action", "N/A")
                symbol = t_data.get("symbol", "N/A")
                price = t_data.get("entry", "N/A")
                sl = t_data.get("sl", "N/A")
                tp1 = t_data.get("tp1", "N/A")
                
                md_content += f"| {channel} | `{short_text}` | **{action}** | {symbol} | {price} | {sl} | {tp1} |\n"
                print(f"Extracted: {action} {symbol}")
        except Exception as e:
            pass
            
    with open("telegram_extraction_report.md", "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print("Report generated successfully.")

if __name__ == "__main__":
    asyncio.run(main())
