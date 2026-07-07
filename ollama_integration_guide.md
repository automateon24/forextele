# Local AI (Ollama) Integration Guide for Trading Systems

This guide explains how to replace expensive, rate-limited cloud APIs (like OpenAI or Google Gemini) with a **100% free, offline, local AI** using Ollama. This is especially useful for parsing messy Telegram signals (like BankNifty, Sensex) instantly and securely on your own server.

## Step 1: Install & Setup
1. Download Ollama for Windows/Linux from [ollama.com](https://ollama.com/).
2. Open your terminal/command prompt and download a lightweight, fast model. For data extraction, `llama3.2` or `qwen2.5-coder` (1.5B) is highly recommended for CPUs.
   ```bash
   ollama pull llama3.2
   ```
3. Once downloaded, Ollama runs in the background and hosts a local API at `http://127.0.0.1:11434`.

---

## Step 2: Code Integration (Two Methods)

Because Ollama provides an OpenAI-compatible endpoint, you don't need to rewrite your entire codebase. You can use standard Python libraries.

### Method A: Using the Official `openai` Python Library (Easiest)
If your Indian market system is already using the OpenAI library, you just need to change **two lines of code**: the `base_url` and the `model`.

```python
import asyncio
import json
from openai import AsyncOpenAI

# 1. Point the client to Localhost instead of OpenAI servers
ai_client = AsyncOpenAI(
    base_url='http://127.0.0.1:11434/v1', 
    api_key='ollama' # API key is ignored locally, but required by the library
)

async def parse_indian_signal(message: str):
    prompt = f"""
    Extract the trading signal from this message as JSON.
    Format: {{"instrument": "SENSEX 78100", "action": "BUY", "entry": 430, "sl": 330, "target": 650}}
    Message: {message}
    """
    
    response = await ai_client.chat.completions.create(
        model="llama3.2", # 2. Specify the local model you downloaded
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }, # Forces strict JSON output
        temperature=0.0 # Keep at 0.0 for trading logic (no hallucinations)
    )
    
    return json.loads(response.choices[0].message.content)

# Example Usage:
# result = asyncio.run(parse_indian_signal("sensex 78100 in the range of 430 to 445 sl below 330 tgt is 650"))
# print(result)
```

### Method B: Using standard HTTP Requests (`requests` or `httpx`)
If you want a lightweight solution without installing the OpenAI library, you can hit the Ollama API directly.

```python
import httpx

async def parse_signal_raw(message: str) -> str:
    endpoint = "http://127.0.0.1:11434/api/generate"
    
    payload = {
        "model": "llama3.2",
        "prompt": f"Extract Trade Data as JSON from: {message}",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_thread": 4 # Restricts CPU usage so MT5 doesn't freeze
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(endpoint, json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["response"].strip()
```

---

## Best Practices for Trading Systems
1. **CPU Management:** Always pass `"num_thread": 4` (or fewer) in the options if you are running on a server without a GPU. If you let the AI use all CPU cores, it will freeze your MT5 terminal and you will miss price ticks.
2. **Temperature:** Always set `temperature = 0.0`. This forces the AI to be completely deterministic and prevents it from "guessing" or making up fake target prices.
3. **JSON Forcing:** If using the OpenAI library method, always pass `response_format={ "type": "json_object" }`. This physically prevents the AI from outputting conversational text like *"Sure, here is the trade data..."* which breaks python parsers.
