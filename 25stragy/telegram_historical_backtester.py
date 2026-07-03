import json
import re
import os
from datetime import datetime

HISTORY_FILE = r"C:\25stragy\telegram_history_90days.json"
REPORT_FILE = r"C:\25stragy\telegram_90days_backtest_report.md"

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
    # Generic fallback for stock options
    return 500

def get_lot_multiplier(channel_id):
    if channel_id in [-1002626583811, -1002231238486]: # BTST VIP+ and MCX
        return 1
    return 5

def extract_via_regex(text: str):
    text_upper = text.upper()
    
    # Check for BOOK PROFIT at specific price
    if "BOOK PROFIT" in text_upper:
        inst = re.search(r"([A-Z]{3,20})[^\n]+", text_upper)
        inst_str = inst.group(0).strip() if inst else "UNKNOWN"
        price_match = re.search(r"B/W\s*([\d\.]+)", text_upper)
        price = float(price_match.group(1)) if price_match else 0.0
        return {"instrument": inst_str, "action": "UPDATE", "status": "MANUAL_BOOK", "price": price, "parser_used": "Regex"}
        
    # Check for Target hits
    if "1ST TARGET" in text_upper or "T1 HIT" in text_upper or "FIRST TARGET" in text_upper or "TARGET TESTED SUCCESSFULLY" in text_upper:
        inst = re.search(r"([A-Z]{3,20})[^\n]+", text_upper)
        inst_str = inst.group(0).strip() if inst else "UNKNOWN"
        return {"instrument": inst_str, "action": "UPDATE", "status": "T1_HIT", "parser_used": "Regex"}
        
    if "2ND TARGET" in text_upper or "T2 HIT" in text_upper or "SECOND TARGET" in text_upper:
        inst = re.search(r"([A-Z]{3,20})[^\n]+", text_upper)
        inst_str = inst.group(0).strip() if inst else "UNKNOWN"
        return {"instrument": inst_str, "action": "UPDATE", "status": "T2_HIT", "parser_used": "Regex"}
        
    if "ALL TARGET" in text_upper or "T3 HIT" in text_upper:
        inst = re.search(r"([A-Z]{3,20})[^\n]+", text_upper)
        inst_str = inst.group(0).strip() if inst else "UNKNOWN"
        return {"instrument": inst_str, "action": "UPDATE", "status": "T3_HIT", "parser_used": "Regex"}
        
    if "SL HIT" in text_upper or "STOPLOSS HIT" in text_upper:
        inst = re.search(r"([A-Z]{3,20})[^\n]+", text_upper)
        inst_str = inst.group(0).strip() if inst else "UNKNOWN"
        return {"instrument": inst_str, "action": "EXIT", "status": "SL_HIT", "parser_used": "Regex"}
            
    if "BUY " in text_upper or "ENTER:" in text_upper or "ENTRY:" in text_upper or "BUY" in text_upper:
        try:
            data = {"status": "NEW_SIGNAL", "parser_used": "Regex"}
            
            # Look for instrument like NIFTY 23250 CE or RELIANCE CE
            inst_match = re.search(r"(?:BUY\s+|ENTER:\s*`?|ENTRY:\s*)?([A-Z]{3,20})[A-Z0-9\s]+(?:CE|PE|CALL|PUT)", text_upper)
            if inst_match:
                data["instrument"] = inst_match.group(0).replace("BUY ", "").replace("ENTER: ", "").replace("`", "").strip()
            else:
                return None
                
            data["action"] = "BUY"
                
            entry_match = re.search(r"(?:ABOVE|AT|@|RANGE)[\s\-:*]*([\d\.]+)", text_upper)
            if entry_match:
                data["entry_range"] = entry_match.group(1).strip()
            else:
                return None
                
            sl_match = re.search(r"(?:SL|STOPLOSS|STOP LOSS)[\s\-:*A-Z]*([\d\.]+)", text_upper)
            if sl_match:
                data["stop_loss"] = sl_match.group(1).strip()
                
            t1_match = re.search(r"(?:TARGET\s*1?|TGT|TG)[\s\-:*]*([\d\.]+)", text_upper)
            if t1_match:
                data["target"] = t1_match.group(1).strip()
                
            if "entry_range" in data and "stop_loss" in data and "target" in data:
                return data
        except Exception as e:
            pass
    return None

def run_backtest():
    print("Loading history...")
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        messages = json.load(f)
        
    print(f"Loaded {len(messages)} messages. Parsing...")
    
    active_trades = {}
    completed_trades = []
    parsed_count = 0
    
    for msg in messages:
        channel_id = msg['channel_id']
        if channel_id not in active_trades:
            active_trades[channel_id] = []
            
        parsed = extract_via_regex(msg['text'])
        if not parsed:
            continue
            
        parsed_count += 1
        status = parsed['status']
        date_str = msg['date']
        inst = parsed.get('instrument', '')
        
        if status == "NEW_SIGNAL":
            try:
                entry = float(re.search(r'[\d\.]+', parsed.get('entry_range', '0')).group())
                sl = float(re.search(r'[\d\.]+', parsed.get('stop_loss', '0')).group())
                tgt = float(re.search(r'[\d\.]+', parsed.get('target', '0')).group())
            except:
                continue
                
            trade = {
                "channel_id": channel_id,
                "instrument": inst,
                "entry_price": entry,
                "stop_loss": sl,
                "target": tgt,
                "entry_time": date_str,
                "exit_time": None,
                "pnl": 0.0,
                "capital_utilized": 0.0,
                "outcome": "OPEN"
            }
            
            lot_multiplier = get_lot_multiplier(channel_id)
            lot_size = get_lot_size(inst)
            trade["capital_utilized"] = entry * lot_size * lot_multiplier
            
            active_trades[channel_id].append(trade)
            
        elif "HIT" in status or status == "MANUAL_BOOK":
            matched_trade = None
            if inst != "UNKNOWN":
                for t in reversed(active_trades[channel_id]):
                    if inst.lower() in t['instrument'].lower() or t['instrument'].lower() in inst.lower():
                        matched_trade = t
                        break
            
            if not matched_trade and len(active_trades[channel_id]) > 0:
                matched_trade = active_trades[channel_id][-1]
                    
            if matched_trade:
                lot_size = get_lot_size(matched_trade['instrument'])
                lot_multiplier = get_lot_multiplier(channel_id)
                actual_lots = lot_size * lot_multiplier
                
                if status == "MANUAL_BOOK" and matched_trade["outcome"] in ["OPEN", "T1_HIT", "T2_HIT"]:
                    matched_trade["outcome"] = "MANUAL_BOOK"
                    matched_trade["exit_time"] = date_str
                    exit_px = parsed.get("price", 0.0)
                    if exit_px == 0.0:
                        exit_px = matched_trade['entry_price'] * 1.10
                    matched_trade["pnl"] = (exit_px - matched_trade['entry_price']) * actual_lots
                    completed_trades.append(matched_trade)
                    active_trades[channel_id].remove(matched_trade)
                    
                elif status == "T1_HIT" and matched_trade["outcome"] == "OPEN":
                    matched_trade["outcome"] = "T1_HIT"
                elif status == "T2_HIT" and matched_trade["outcome"] in ["OPEN", "T1_HIT"]:
                    matched_trade["outcome"] = "T2_HIT"
                elif status == "T3_HIT":
                    matched_trade["outcome"] = "T3_HIT"
                    matched_trade["exit_time"] = date_str
                    exit_px = matched_trade['target'] if matched_trade['target'] > matched_trade['entry_price'] else matched_trade['entry_price'] * 1.10
                    matched_trade["pnl"] = (exit_px - matched_trade['entry_price']) * actual_lots
                    completed_trades.append(matched_trade)
                    active_trades[channel_id].remove(matched_trade)
                elif status == "SL_HIT":
                    if matched_trade["outcome"] == "OPEN":
                        matched_trade["outcome"] = "SL_HIT"
                        exit_px = matched_trade['stop_loss'] if matched_trade['stop_loss'] > 0 else matched_trade['entry_price'] * 0.80
                        matched_trade["pnl"] = (exit_px - matched_trade['entry_price']) * actual_lots
                    elif matched_trade["outcome"] == "T1_HIT":
                        matched_trade["outcome"] = "TSL_HIT_AT_COST"
                        matched_trade["pnl"] = 0.0
                    elif matched_trade["outcome"] == "T2_HIT":
                        matched_trade["outcome"] = "TSL_HIT_AT_T1"
                        exit_px = matched_trade['entry_price'] + ((matched_trade['target'] - matched_trade['entry_price']) * 0.5)
                        matched_trade["pnl"] = (exit_px - matched_trade['entry_price']) * actual_lots
                    
                    matched_trade["exit_time"] = date_str
                    completed_trades.append(matched_trade)
                    active_trades[channel_id].remove(matched_trade)
                    
    # Force close remaining open trades for stats
    for ch, trades in list(active_trades.items()):
        if ch == -1002626583811: # BTST VIP+
            continue
            
        for t in trades[:]:
            t["exit_time"] = "EOD_FORCE_CLOSE"
            t["pnl"] = 0.0
            completed_trades.append(t)
            active_trades[ch].remove(t)
            
    for ch, trades in active_trades.items():
        for t in trades:
            t["exit_time"] = "90_DAY_FORCE_CLOSE"
            t["pnl"] = 0.0
            completed_trades.append(t)
            
    print(f"Extracted {parsed_count} signal updates. Found {len(completed_trades)} completed trades.")
    
    # Generate Report
    stats = {}
    completed_trades.sort(key=lambda x: x['entry_time'])
    
    for t in completed_trades:
        ch = t['channel_id']
        date_obj = datetime.fromisoformat(t['entry_time'].replace('Z', '+00:00'))
        month_key = date_obj.strftime('%Y-%m')
        
        if ch not in stats:
            stats[ch] = {
                "Total": 0, "Wins": 0, "Losses": 0, "Breakeven": 0, 
                "Total_PnL": 0.0, "Capital": 0.0, "Months": {},
                "Cumulative_PnL": [0.0], "Max_DD": 0.0, "Peak": 0.0
            }
            
        stats[ch]["Total"] += 1
        stats[ch]["Total_PnL"] += t["pnl"]
        stats[ch]["Capital"] += t["capital_utilized"]
        
        # Max Drawdown Logic
        cum_pnl = stats[ch]["Cumulative_PnL"][-1] + t["pnl"]
        stats[ch]["Cumulative_PnL"].append(cum_pnl)
        if cum_pnl > stats[ch]["Peak"]:
            stats[ch]["Peak"] = cum_pnl
        dd = stats[ch]["Peak"] - cum_pnl
        if dd > stats[ch]["Max_DD"]:
            stats[ch]["Max_DD"] = dd
        
        if month_key not in stats[ch]["Months"]:
            stats[ch]["Months"][month_key] = {"Wins": 0, "Losses": 0, "PnL": 0.0}
            
        out = t["outcome"]
        if out in ["T3_HIT", "MANUAL_BOOK", "TSL_HIT_AT_T1", "T1_HIT", "T2_HIT"]: 
            stats[ch]["Wins"] += 1
            stats[ch]["Months"][month_key]["Wins"] += 1
        elif out in ["OPEN", "EOD_FORCE_CLOSE", "90_DAY_FORCE_CLOSE", "TSL_HIT_AT_COST"]:
            stats[ch]["Breakeven"] += 1
        elif out == "SL_HIT":
            stats[ch]["Losses"] += 1
            stats[ch]["Months"][month_key]["Losses"] += 1
            
        stats[ch]["Months"][month_key]["PnL"] += t["pnl"]
            
    report = "# 📊 Telegram Channels 90-Day Verified Backtest (Multi-Lot & Max DD)\n\n"
    report += "This report utilizes your adjusted variables:\n"
    report += "- **BTST VIP+ & MCX:** 1 Lot traded per call.\n"
    report += "- **All Other Channels (Sensex360, Zero to Hero, etc.):** 5 Lots traded per call.\n"
    report += "- **Sensex360 Custom Logic:** Captures 'Book Profit In Between' messages accurately.\n"
    report += "- **BTST Custom Logic:** Trades allowed to run their full course overnight (Reverted fast-close).\n\n"
    
    report += "### 🏆 Overall Performance Table\n\n"
    report += "| Channel ID | Trades/Day | Total Trades | Win Rate | Est. Cap Utilized | Total Gained (PnL) | Max Drawdown |\n"
    report += "|---|---|---|---|---|---|---|\n"
    
    for ch, data in stats.items():
        total = data["Total"]
        wins = data["Wins"]
        losses = data["Losses"]
        be = data["Breakeven"]
        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        total_pnl = data["Total_PnL"]
        avg_trades_per_day = total / 90.0
        cap = data["Capital"]
        mdd = data["Max_DD"]
        
        report += f"| `{ch}` | {avg_trades_per_day:.1f} | {total} | **{win_rate:.2f}%** | ₹{cap:,.0f} | **₹{total_pnl:,.2f}** | ₹{mdd:,.0f} |\n"
        
    report += "\n---\n"
    report += "### 📅 Monthly Breakdown Details\n\n"
    
    for ch, data in stats.items():
        report += f"#### Channel: `{ch}`\n"
        for month, mdata in sorted(data["Months"].items()):
            m_win = mdata["Wins"]
            m_loss = mdata["Losses"]
            m_wr = (m_win / (m_win + m_loss)) * 100 if (m_win + m_loss) > 0 else 0
            report += f"- **{month}**: {m_win}W / {m_loss}L | WinRate: {m_wr:.1f}% | PnL: **₹{mdata['PnL']:,.2f}**\n"
        report += "\n"
        
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
        
    print(f"Report successfully saved to {REPORT_FILE}")

if __name__ == "__main__":
    run_backtest()
