import os
import subprocess
import httpx
import asyncio
from datetime import datetime
import MetaTrader5 as mt5
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent
MT5_CFG_PATH = BASE_DIR / "mt5_config.json"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.2"

def get_todays_pnl():
    """Fetch today's closed deals from MT5 to calculate PnL"""
    if not mt5.initialize():
        try:
            with open(MT5_CFG_PATH, "r") as f:
                cfg = json.load(f)
            mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])
        except:
            return "Unable to connect to MT5 to fetch PnL."
            
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day)
    deals = mt5.history_deals_get(start_of_day, now)
    
    if not deals:
        return "No trades executed today."
        
    total_profit = sum(deal.profit for deal in deals)
    return f"Total Daily PnL: ${total_profit:.2f}. Total Trades: {len(deals)}"

async def generate_commit_message(pnl_summary: str):
    """Use Ollama to generate a professional institutional commit message"""
    system_prompt = (
        "You are an AI DevOps Engineer for an institutional Forex trading swarm. "
        "Your task is to generate a single, professional git commit message for the end-of-day backup. "
        "The message should be concise, mention the day's performance if provided, and sound like a state-of-the-art quantitative fund. "
        "Do NOT include markdown, just the raw commit message string."
    )
    
    full_prompt = f"{system_prompt}\n\nToday's Performance:\n{pnl_summary}"
    
    payload = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.3}
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"Failed to reach Ollama: {e}")
        return f"chore: End of Day Backup - {datetime.now().strftime('%Y-%m-%d')}"

def execute_git_sync(commit_message: str):
    """Commit and push to remote"""
    try:
        # Check if git is initialized
        if not (BASE_DIR / ".git").exists():
            print("Git repository not initialized in this folder. Skipping sync.")
            return

        subprocess.run(["git", "add", "."], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
        print("Successfully synced to GitHub!")
    except subprocess.CalledProcessError as e:
        print(f"Git execution failed: {e}")

async def main():
    print("Initiating End-of-Day Backup...")
    pnl_summary = get_todays_pnl()
    print(f"Performance Summary: {pnl_summary}")
    
    commit_msg = await generate_commit_message(pnl_summary)
    # Remove quotes if hallucinated
    commit_msg = commit_msg.strip('"').strip("'")
    print(f"Generated Commit Message: {commit_msg}")
    
    execute_git_sync(commit_msg)

if __name__ == "__main__":
    asyncio.run(main())
