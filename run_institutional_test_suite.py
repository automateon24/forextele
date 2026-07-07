import asyncio
import httpx
import os
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
REPORT_FILE = BASE_DIR / "SWARM_INSTITUTIONAL_QA_REPORT.md"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.2"

FILES_TO_AUDIT = [
    "master_swarm_runner.py",
    "swarm_engine.py",
    "real_mt5_execution.py",
    "telegram_signal_engine.py"
]

QA_SYSTEM_PROMPT = """You are the Lead Institutional QA Engineer for a Tier-1 Quantitative Trading Firm.
Your job is to ruthlessly audit the provided Python file from an AI-driven Forex Trading Swarm.

You must evaluate the code across the following strict parameters:
1. Sanity & Regression: Logical soundness, edge cases.
2. Code Quality & Calculation Bugs: Mathematical flaws, division by zero, invalid lot sizes.
3. Memory Leaks & Thread Safety: Zombie processes, orphaned threads.

Provide a highly detailed, professional markdown report for this specific file.
"""

async def analyze_file(file_name: str, code: str):
    full_prompt = f"{QA_SYSTEM_PROMPT}\n\nHere is the code for {file_name}:\n{code}"
    
    payload = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    
    print(f"Feeding {file_name} to Ollama AI for Deep Inspection...")
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            print(f"Failed to analyze {file_name}: {e}")
            return f"**ERROR:** Failed to analyze {file_name} due to {e}"

async def run_institutional_audit():
    print("Initiating Institutional QA Audit (Stage-by-Stage)...")
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 🛡️ INSTITUTIONAL SWARM QA AUDIT REPORT\n")
        f.write(f"**Date Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    for file_name in FILES_TO_AUDIT:
        path = BASE_DIR / file_name
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            report = await analyze_file(file_name, code)
            
            with open(REPORT_FILE, "a", encoding="utf-8") as f:
                f.write(f"## QA Report for `{file_name}`\n")
                f.write(report)
                f.write("\n\n---\n\n")
        else:
            with open(REPORT_FILE, "a", encoding="utf-8") as f:
                f.write(f"## QA Report for `{file_name}`\n**ERROR:** File not found.\n\n---\n\n")
                
    print(f"Audit Complete! Complete stage-by-stage report saved to {REPORT_FILE.name}")

if __name__ == "__main__":
    asyncio.run(run_institutional_audit())
