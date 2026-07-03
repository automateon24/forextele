
import json
import os
def is_system_stopped():
    try:
        if os.path.exists(r'C:\25stragy\system_health.json'):
            with open(r'C:\25stragy\system_health.json', 'r') as f:
                data = json.load(f)
                return data.get('master_switch', 'START') == 'STOP'
    except:
        pass
    return False

import json
import os
import asyncio
import re
from datetime import datetime
import pandas as pd
from telethon import TelegramClient, events
from openai import AsyncOpenAI

CONFIG_PATH = r"C:\25stragy\config_telegram.json"
EXCEL_LOG_PATH = r"C:\25stragy\telegram_signals.xlsx"

# The 7 specific channels we want to monitor
MONITORED_CHANNELS = [
    -1002871728862, # ZERO TO HERO
    -1002902210804, # Sensex360
    -1002231238486, # MCX Commodities
    -1002626583811, # BTST VIP+
    -1002115753582, # Premium DIL SE TRADER
    -1002412774015, # Equity Stocks
    -1002264960458  # VIP Stock Options - Gokul
]

# Load Config
with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

client = TelegramClient(r"C:\25stragy\telegram_session", config['api_id'], config['api_hash'])
ai_client = AsyncOpenAI(api_key=config['openai_api_key'])

def get_lot_size(inst_str: str):
    inst_upper = inst_str.upper()
    if "NIFTY" in inst_upper and "BANK" not in inst_upper and "FIN" not in inst_upper and "MIDCP" not in inst_upper:
        return 25
    if "BANKNIFTY" in inst_upper: return 15
    if "FINNIFTY" in inst_upper: return 25
    if "MIDCPNIFTY" in inst_upper: return 50
    if "SENSEX" in inst_upper: return 10
    if "CRUDE" in inst_upper: return 100
    if "GOLD" in inst_upper: return 10
    if "SILVER" in inst_upper: return 1
    if "NATURALGAS" in inst_upper: return 1250
    return 500

def extract_via_regex(text: str):
    text_upper = text.upper()
    
    if "BOOK PROFIT" in text_upper:
        price_match = re.search(r"B/W\s*([\d\.]+)", text_upper)
        price = float(price_match.group(1)) if price_match else 0.0
        return {"instrument": "UNKNOWN", "action": "UPDATE", "status": "MANUAL_BOOK", "price": price, "parser_used": "Regex"}
        
    if "1ST TARGET" in text_upper or "T1 HIT" in text_upper or "FIRST TARGET" in text_upper or "TARGET TESTED SUCCESSFULLY" in text_upper:
        return {"instrument": "UNKNOWN", "action": "UPDATE", "status": "T1_HIT", "parser_used": "Regex"}
        
    if "2ND TARGET" in text_upper or "T2 HIT" in text_upper or "SECOND TARGET" in text_upper:
        return {"instrument": "UNKNOWN", "action": "UPDATE", "status": "T2_HIT", "parser_used": "Regex"}
        
    if "ALL TARGET" in text_upper or "T3 HIT" in text_upper:
        return {"instrument": "UNKNOWN", "action": "UPDATE", "status": "T3_HIT", "parser_used": "Regex"}
        
    if "SL HIT" in text_upper or "STOPLOSS HIT" in text_upper:
        return {"instrument": "UNKNOWN", "action": "EXIT", "status": "SL_HIT", "parser_used": "Regex"}
            
    if "BUY " in text_upper or "ENTER:" in text_upper or "ENTRY:" in text_upper or "BUY" in text_upper:
        try:
            data = {"status": "NEW_SIGNAL", "parser_used": "Regex"}
            
            # Check for explicitly formatted ENTER: `StockName`
            explicit_enter = re.search(r"ENTER:\s*`?([A-Z0-9\s\.\&\-]+?)[`•]", text_upper)
            if explicit_enter:
                data["instrument"] = explicit_enter.group(1).strip()
            else:
                inst_match = re.search(r"(?:BUY\s+|ENTER:\s*`?|ENTRY:\s*)?([A-Z]{3,20})[A-Z0-9\s]+(?:CE|PE|CALL|PUT)\b", text_upper)
                if inst_match:
                    data["instrument"] = inst_match.group(0).replace("BUY ", "").replace("ENTER: ", "").replace("`", "").strip()
                else:
                    return None
                
            data["action"] = "BUY"
            entry_match = re.search(r"(?:ABOVE|AT|@|RANGE)[\s\-:*]*([\d\.]+)", text_upper)
            sl_match = re.search(r"(?:SL|STOPLOSS|STOP LOSS)[\s\-:*A-Z]*([\d\.]+)", text_upper)
            t1_match = re.search(r"(?:TARGET\s*1?|TGT|TG)[\s\-:*]*([\d\.]+)", text_upper)
            
            if entry_match and sl_match and t1_match:
                data["entry_range"] = entry_match.group(1).strip()
                data["stop_loss"] = sl_match.group(1).strip()
                data["target"] = t1_match.group(1).strip()
                return data
        except Exception:
            pass
    return None

async def extract_via_ai(text: str):
    """
    Fallback to OpenAI for messy, unstructured messages.
    """
    prompt = f"""
    You are an expert Indian Stock Market trading assistant. 
    Read the following Telegram message and extract the trading signal details.
    If it is NOT a trading signal (just chat or news), return {{"status": "IGNORE"}}.
    If it is an update like target hit or stoploss hit, set action to "UPDATE" or "EXIT" and status to "T1_HIT", "T2_HIT", or "SL_HIT".
    Extract the data into this EXACT JSON format:
    
    {{
        "instrument": "NIFTY / BANKNIFTY / STOCK NAME + STRIKE + CE/PE",
        "action": "BUY / SELL / UPDATE / EXIT",
        "entry_range": "e.g. 300-320 (leave blank for updates)",
        "stop_loss": "e.g. 250 (leave blank for updates)",
        "target": "e.g. 400 (leave blank for updates)",
        "status": "NEW_SIGNAL, T1_HIT, T2_HIT, T3_HIT, SL_HIT"
    }}
    
    Message:
    "{text}"
    """
    
    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini", # Extremely fast and cheap
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"AI Parse Error: {e}")
        return {"status": "ERROR"}

def save_to_excel(channel_id: int, extracted_data: dict, raw_text: str):
    if extracted_data.get("status") in ["IGNORE", "ERROR"]:
        return
        
    if "HIT" in extracted_data.get("status", "") or extracted_data.get("status") == "MANUAL_BOOK":
        if os.path.exists(EXCEL_LOG_PATH):
            try:
                df = pd.read_excel(EXCEL_LOG_PATH)
                inst = extracted_data.get("instrument", "")
                
                # Match to the most recent open trade loosely
                if inst == "UNKNOWN":
                    # Grab the last open trade for this channel
                    mask = (df['channel_id'] == channel_id) & (df['status'].isin(['NEW_SIGNAL', 'T1_HIT', 'T2_HIT']))
                else:
                    inst_parts = inst.split()
                    key_part = inst_parts[0] if len(inst_parts) > 0 else inst
                    mask = df['instrument'].str.contains(key_part, na=False, case=False) & (df['status'].isin(['NEW_SIGNAL', 'T1_HIT', 'T2_HIT']))
                
                if not df[mask].empty:
                    last_idx = df[mask].index[-1]
                    trade_row = df.loc[last_idx]
                    
                    try:
                        entry = float(re.search(r'[\d\.]+', str(trade_row['entry_range'])).group())
                        sl = float(re.search(r'[\d\.]+', str(trade_row['stop_loss'])).group())
                        tgt = float(re.search(r'[\d\.]+', str(trade_row['target'])).group())
                    except:
                        return
                    
                    lot_size = get_lot_size(str(trade_row['instrument']))
                    actual_lots = lot_size * 1 # User requested 1 Lot for tomorrow
                    
                    exit_px = 0.0
                    if extracted_data["status"] == "MANUAL_BOOK":
                        df.at[last_idx, 'status'] = "MANUAL_BOOK"
                        exit_px = float(extracted_data.get("price", 0.0))
                        if exit_px == 0: exit_px = entry * 1.10
                        df.at[last_idx, 'pnl'] = (exit_px - entry) * actual_lots
                    elif extracted_data["status"] == "T1_HIT":
                        df.at[last_idx, 'status'] = "T1_HIT"
                    elif extracted_data["status"] == "T2_HIT":
                        df.at[last_idx, 'status'] = "T2_HIT"
                    elif extracted_data["status"] == "T3_HIT":
                        df.at[last_idx, 'status'] = "T3_HIT"
                        exit_px = tgt if tgt > entry else entry * 1.10
                        df.at[last_idx, 'pnl'] = (exit_px - entry) * actual_lots
                    elif extracted_data["status"] == "SL_HIT":
                        if trade_row['status'] == "NEW_SIGNAL":
                            df.at[last_idx, 'status'] = "CLOSED_SL"
                            exit_px = sl if sl > 0 else entry * 0.80
                            df.at[last_idx, 'pnl'] = (exit_px - entry) * actual_lots
                        elif trade_row['status'] == "T1_HIT":
                            if channel_id == -1002902210804: # Sensex360 doesn't trail tight
                                df.at[last_idx, 'status'] = "CLOSED_SL"
                                exit_px = sl if sl > 0 else entry * 0.80
                                df.at[last_idx, 'pnl'] = (exit_px - entry) * actual_lots
                            else:
                                df.at[last_idx, 'status'] = "TSL_HIT_AT_COST"
                                df.at[last_idx, 'pnl'] = 0.0
                        elif trade_row['status'] == "T2_HIT":
                            if channel_id == -1002902210804:
                                df.at[last_idx, 'status'] = "CLOSED_SL"
                                exit_px = sl if sl > 0 else entry * 0.80
                                df.at[last_idx, 'pnl'] = (exit_px - entry) * actual_lots
                            else:
                                df.at[last_idx, 'status'] = "TSL_HIT_AT_T1"
                                exit_px = entry + ((tgt - entry) * 0.5)
                                df.at[last_idx, 'pnl'] = (exit_px - entry) * actual_lots
                    
                    if exit_px > 0 or df.at[last_idx, 'status'] in ["TSL_HIT_AT_COST", "T3_HIT", "MANUAL_BOOK", "CLOSED_SL"]:
                        print(f"🔄 Closed/Updated Trade {trade_row['instrument']} -> PnL: Rs. {df.at[last_idx, 'pnl']}")
                        df.at[last_idx, 'exit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                    df.to_excel(EXCEL_LOG_PATH, index=False)
                    return
            except Exception as e:
                print(f"TSL Update Error: {e}")

    extracted_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extracted_data["channel_id"] = channel_id
    extracted_data["raw_message"] = raw_text.replace("\n", " ")
    
    extracted_data["pnl"] = 0.0
    extracted_data["exit_time"] = ""
    
    try:
        entry = float(re.search(r'[\d\.]+', str(extracted_data.get('entry_range', '0'))).group())
        lot_size = get_lot_size(extracted_data.get("instrument", ""))
        extracted_data["capital_utilized"] = entry * lot_size * 1 # 1 Lot logic tomorrow
    except:
        extracted_data["capital_utilized"] = 0.0
        
    df_new = pd.DataFrame([extracted_data])
    
    if os.path.exists(EXCEL_LOG_PATH):
        df_existing = pd.read_excel(EXCEL_LOG_PATH)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new
        
    df_combined.to_excel(EXCEL_LOG_PATH, index=False)
    print(f"✅ Trade Logged to Excel: {extracted_data['instrument']} | {extracted_data['action']}")

@client.on(events.NewMessage(chats=MONITORED_CHANNELS))
async def new_message_handler(event):
    raw_text = event.message.text
    if not raw_text:
        return
        
    print(f"\n[RECEIVED] Message from Channel {event.chat_id}")
    
    # Attempt 1: Fast Regex
    trade_data = extract_via_regex(raw_text)
    
    # Attempt 2: AI Fallback
    if trade_data is None:
        print(" -> Regex failed. Passing to ChatGPT for unstructured extraction...")
        trade_data = await extract_via_ai(raw_text)
        trade_data["parser_used"] = "ChatGPT-4o-Mini"
    else:
        print(" -> Successfully parsed instantly via Regex!")
        
    if trade_data and trade_data.get("status") not in ["IGNORE", "ERROR"]:
        print(f" -> Extracted: {trade_data}")
        save_to_excel(event.chat_id, trade_data, raw_text)

async def main():
    print("🚀 Starting Hybrid AI Telegram Engine...")
    print("Listening to 6 Channels for Live Signals...")
    # Write heartbeat file for Dashboard
    with open(r"C:\25stragy\telegram_status.json", "w") as f:
        json.dump({"status": "CONNECTED", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f)
        
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
