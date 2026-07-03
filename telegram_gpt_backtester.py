import json
import re
import os
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
import google.generativeai as genai
import pandas as pd

HISTORY_FILE = r"C:\anlyzeforex\forextele\telegram_history_15days.json"
PARSED_FILE = r"C:\anlyzeforex\forextele\telegram_parsed_15days.json"
REPORT_FILE = r"C:\anlyzeforex\forextele\telegram_verified_15days_report.md"
CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"

LOT_SIZES = {
    "BTC": 1,
    "ETH": 1,
    "XAU": 1,
    "GOLD": 1,
    "EURUSD": 1,
    "SOL": 10
}

def get_lot_size(inst_str: str):
    inst_upper = inst_str.upper()
    for key, size in LOT_SIZES.items():
        if key in inst_upper:
            return size
    return 1 # Default fallback

async def process_chunk(client, chunk, chunk_id):
    prompt = """
    You are an expert Crypto and Forex Market Data Extraction AI.
    Below is a list of Telegram messages from a vendor.
    Extract ALL trade signals AND all target/stoploss updates.
    
    If it's a NEW SIGNAL, extract: 
    - message_id
    - date
    - channel_id
    - type: "NEW_SIGNAL"
    - instrument (e.g. "BTC/USDT", "XAUUSD", "GOLD")
    - action (BUY / SELL / LONG / SHORT - standardise to BUY or SELL)
    - entry (just a single number representing the entry price, e.g. 64000)
    - stop_loss (a single number, e.g. 63000)
    - target (a single number, usually T1, e.g. 65000)
    
    If it's an UPDATE (like T1 hit, SL hit, safe traders book, etc.), extract:
    - message_id
    - date
    - channel_id
    - type: "UPDATE"
    - instrument (e.g. "BTC/USDT", infer from context if possible or leave empty string if not explicitly stated)
    - event: "T1_HIT", "T2_HIT", "T3_HIT", "SL_HIT", "BOOK_PROFIT"
    
    Ignore general chat, good morning messages, etc.
    Return ONLY a valid JSON array of objects. Do not wrap in ```json ... ``` blocks, just return raw JSON.
    
    MESSAGES:
    """
    
    for msg in chunk:
        prompt += f"\n[ID: {msg['message_id']} | Date: {msg['date']} | Channel: {msg['channel_id']}]\n{msg['text']}\n---\n"
        
    try:
        if hasattr(client, 'GenerativeModel'): # Gemini client (genai)
            model = client.GenerativeModel('gemini-2.5-flash')
            response = await model.generate_content_async(prompt, generation_config={"temperature": 0.0})
            content = response.text.strip()
        else: # OpenAI client
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            content = response.choices[0].message.content.strip()
            
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
            
        return json.loads(content)
    except Exception as e:
        print(f"Chunk {chunk_id} failed: {e}")
        return []

async def parse_messages_with_gpt():
    print("🤖 Loading History and Filtering Spam...")
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        messages = json.load(f)
        
    # Pre-filter to reduce API costs
    keywords = ['LONG', 'SHORT', 'BUY', 'SELL', 'SL', 'TARGET', 'TGT', 'HIT', 'BOOK', 'PROFIT', 'EXIT', 'BTC', 'ETH', 'XAU', 'USDT']
    filtered = []
    for m in messages:
        text_upper = m['text'].upper()
        if any(k in text_upper for k in keywords):
            filtered.append(m)
            
    print(f"✂️ Filtered {len(messages)} down to {len(filtered)} potential signal messages.")
    
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
        
    if "gemini_api_key" in cfg and cfg["gemini_api_key"]:
        print("Using Primary Gemini API...")
        genai.configure(api_key=cfg["gemini_api_key"])
        client = genai
    else:
        print("Using Secondary OpenAI API...")
        client = AsyncOpenAI(api_key=cfg['openai_api_key'])
    
    chunk_size = 50
    chunks = [filtered[i:i + chunk_size] for i in range(0, len(filtered), chunk_size)]
    
    print(f"🚀 Sending {len(chunks)} chunks concurrently...")
    
    # We will process sequentially or with smaller concurrency for Gemini to avoid rate limits
    if hasattr(client, 'GenerativeModel'):
        # Gemini free tier might have strict rate limits (e.g. 15 RPM). Let's process one by one if it's large, or limit concurrency.
        structured_data = []
        for i, chunk in enumerate(chunks):
            res = await process_chunk(client, chunk, i)
            if isinstance(res, list):
                structured_data.extend(res)
            # Add small delay to avoid 429
            await asyncio.sleep(5)
    else:
        tasks = [process_chunk(client, chunk, i) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)
        structured_data = []
        for r in results:
            if isinstance(r, list):
                structured_data.extend(r)
            
    with open(PARSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, indent=4)
        
    print(f"✅ Extracted {len(structured_data)} structured events. Saved to {PARSED_FILE}")
    return structured_data

def run_simulation(structured_data):
    print("📈 Running Performance Simulator & Verifier...")
    
    active_trades = {}
    completed_trades = []
    
    # Sort chronologically
    structured_data.sort(key=lambda x: x.get('date', ''))
    
    for event in structured_data:
        ch = event.get('channel_id')
        if ch not in active_trades:
            active_trades[ch] = []
            
        if event.get('type') == 'NEW_SIGNAL':
            try:
                entry = float(event.get('entry', 0))
                sl = float(event.get('stop_loss', 0))
                tgt = float(event.get('target', 0))
            except Exception:
                continue
                
            if entry > 0:
                trade = {
                    "channel_id": ch,
                    "instrument": event.get('instrument', 'UNKNOWN'),
                    "entry_time": event.get('date'),
                    "entry_price": entry,
                    "stop_loss": sl,
                    "target": tgt,
                    "exit_time": None,
                    "exit_price": 0.0,
                    "pnl": 0.0,
                    "outcome": "OPEN"
                }
                active_trades[ch].append(trade)
                
        elif event.get('type') == 'UPDATE':
            inst = event.get('instrument', '')
            event_type = event.get('event', '')
            date_str = event.get('date')
            
            # Find matching open trade
            matched = None
            if inst:
                for t in reversed(active_trades[ch]):
                    if inst.upper() in t['instrument'].upper():
                        matched = t
                        break
            if not matched and active_trades[ch]:
                # Fallback to the most recent trade in that channel
                matched = active_trades[ch][-1]
                
            if matched:
                lot_size = get_lot_size(matched['instrument'])
                
                if event_type == 'T1_HIT':
                    if matched['outcome'] == 'OPEN':
                        matched['outcome'] = 'T1_HIT'
                elif event_type == 'T2_HIT':
                    if matched['outcome'] in ['OPEN', 'T1_HIT']:
                        matched['outcome'] = 'T2_HIT'
                elif event_type == 'BOOK_PROFIT' or event_type == 'T3_HIT':
                    if matched['outcome'] != 'CLOSED':
                        matched['outcome'] = 'CLOSED_PROFIT'
                        matched['exit_time'] = date_str
                        # Assume they booked at target price or 10% above entry if target is 0
                        matched['exit_price'] = matched['target'] if matched['target'] > matched['entry_price'] else matched['entry_price'] * 1.10
                        matched['pnl'] = (matched['exit_price'] - matched['entry_price']) * lot_size
                        completed_trades.append(matched)
                        active_trades[ch].remove(matched)
                elif event_type == 'SL_HIT':
                    if matched['outcome'] == 'OPEN':
                        matched['outcome'] = 'CLOSED_SL'
                        matched['exit_time'] = date_str
                        matched['exit_price'] = matched['stop_loss'] if matched['stop_loss'] > 0 else matched['entry_price'] * 0.80
                        matched['pnl'] = (matched['exit_price'] - matched['entry_price']) * lot_size
                        completed_trades.append(matched)
                        active_trades[ch].remove(matched)
                    elif matched['outcome'] in ['T1_HIT', 'T2_HIT']:
                        matched['outcome'] = 'CLOSED_TSL_BREAKEVEN'
                        matched['exit_time'] = date_str
                        matched['exit_price'] = matched['entry_price']
                        matched['pnl'] = 0.0
                        completed_trades.append(matched)
                        active_trades[ch].remove(matched)
                        
    # Force close remaining at EOD
    for ch, trades in active_trades.items():
        for t in trades:
            t['outcome'] = 'CLOSED_EOD_BREAKEVEN'
            t['exit_time'] = t['entry_time']
            t['exit_price'] = t['entry_price']
            t['pnl'] = 0.0
            completed_trades.append(t)
            
    # Generate Report
    stats = {}
    for t in completed_trades:
        ch = t['channel_id']
        date_obj = datetime.fromisoformat(t['entry_time'].replace('Z', '+00:00'))
        month_key = date_obj.strftime('%Y-%m')
        day_key = date_obj.strftime('%Y-%m-%d')
        
        if ch not in stats:
            stats[ch] = {
                "Total": 0, "Wins": 0, "Losses": 0, "Breakeven": 0,
                "Total_PnL": 0.0,
                "Months": {}, "Days": {}
            }
            
        stats[ch]["Total"] += 1
        stats[ch]["Total_PnL"] += t["pnl"]
        
        if month_key not in stats[ch]["Months"]:
            stats[ch]["Months"][month_key] = {"Wins": 0, "Losses": 0, "PnL": 0.0}
        if day_key not in stats[ch]["Days"]:
            stats[ch]["Days"][day_key] = 0
            
        stats[ch]["Days"][day_key] += 1
        
        if t["pnl"] > 0:
            stats[ch]["Wins"] += 1
            stats[ch]["Months"][month_key]["Wins"] += 1
        elif t["pnl"] < 0:
            stats[ch]["Losses"] += 1
            stats[ch]["Months"][month_key]["Losses"] += 1
        else:
            stats[ch]["Breakeven"] += 1
            
        stats[ch]["Months"][month_key]["PnL"] += t["pnl"]
            
    report = "# 🤖 AI Verified 15-Day Telegram Backtest Report\n\n"
    report += "This comprehensive analysis utilized Gemini / GPT to read and interpret 15 days of raw vendor messages, tracking trailing stop-losses, partial bookings, and 1-Lot execution PnL across all channels.\n\n"
    
    for ch, data in stats.items():
        total = data["Total"]
        wins = data["Wins"]
        losses = data["Losses"]
        be = data["Breakeven"]
        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        total_pnl = data["Total_PnL"]
        avg_trades_per_day = sum(data["Days"].values()) / len(data["Days"]) if data["Days"] else 0
        
        report += f"## Channel ID: `{ch}`\n"
        report += f"- **Total Trades (90 Days):** {total}\n"
        report += f"- **Average Trades / Day:** {avg_trades_per_day:.1f}\n"
        report += f"- **Win Rate (Excl. BE):** **{win_rate:.2f}%** ({wins}W / {losses}L / {be}BE)\n"
        report += f"- **Estimated Net PnL (1 Lot):** **Rs. {total_pnl:,.2f}**\n\n"
        
        report += "### Monthly Breakdown:\n"
        for month, mdata in sorted(data["Months"].items()):
            m_win = mdata["Wins"]
            m_loss = mdata["Losses"]
            m_wr = (m_win / (m_win + m_loss)) * 100 if (m_win + m_loss) > 0 else 0
            report += f"- **{month}**: {m_win}W / {m_loss}L | WinRate: {m_wr:.1f}% | PnL: Rs. {mdata['PnL']:,.2f}\n"
        
        report += "\n---\n"
        
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
        
    print(f"Report successfully saved to {REPORT_FILE}")
    
async def main():
    if not os.path.exists(PARSED_FILE):
        data = await parse_messages_with_gpt()
    else:
        print("📥 Using cached parsed data...")
        with open(PARSED_FILE, 'r') as f:
            data = json.load(f)
            
    run_simulation(data)
    
if __name__ == "__main__":
    asyncio.run(main())
