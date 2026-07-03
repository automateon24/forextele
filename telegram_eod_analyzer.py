import os
import json
import pandas as pd
from datetime import datetime
from openai import OpenAI

CONFIG_PATH = r"C:\anlyzeforex\forextele\config_telegram.json"
EXCEL_LOG_PATH = r"C:\anlyzeforex\forextele\telegram_signals.xlsx"
DAILY_REPORT_PATH = r"C:\anlyzeforex\forextele\telegram_daily_pnl.md"
AUDIT_REPORT_PATH = r"C:\anlyzeforex\forextele\telegram_eod_audit.json"

CHANNEL_NAMES = {
    -1002871728862: "ZERO TO HERO",
    -1002902210804: "Sensex360",
    -1002231238486: "MCX Commodities",
    -1002626583811: "BTST VIP+",
    -1002115753582: "Premium DIL SE TRADER",
    -1002412774015: "Equity Stocks",
    -1002264960458: "VIP Stock Options"
}

def run_daily_telegram_analysis():
    print("📈 Starting Telegram EOD Quantitative Analyzer...")
    
    if not os.path.exists(EXCEL_LOG_PATH):
        print("No telegram trades logged today.")
        return
        
    df = pd.read_excel(EXCEL_LOG_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    df_today = df[df['timestamp'].str.startswith(today)]
    
    if df_today.empty:
        print("No new trades today to analyze.")
        return
        
    stats = {}
    for index, row in df_today.iterrows():
        ch = row.get('channel_id', 0)
        status = row.get('status', '')
        pnl = float(row.get('pnl', 0.0))
        cap = float(row.get('capital_utilized', 0.0))
        
        if ch not in stats:
            stats[ch] = {"Total": 0, "Wins": 0, "Losses": 0, "Breakeven": 0, "Capital": 0.0, "PnL": 0.0}
            
        if status in ["NEW_SIGNAL", "IGNORE", "ERROR"]:
            continue # Only evaluate closed or partially closed trades
            
        stats[ch]["Total"] += 1
        stats[ch]["Capital"] += cap
        stats[ch]["PnL"] += pnl
        
        if status in ["T1_HIT", "T2_HIT", "T3_HIT", "MANUAL_BOOK", "TSL_HIT_AT_T1"]:
            stats[ch]["Wins"] += 1
        elif status in ["SL_HIT", "CLOSED_SL"]:
            stats[ch]["Losses"] += 1
        elif status in ["TSL_HIT_AT_COST"]:
            stats[ch]["Breakeven"] += 1
            
    report = f"# 📊 Daily Telegram PnL Report ({today})\n\n"
    report += "This report calculates the **strict 1-Lot PnL** and Capital Returns for all generated signals today.\n\n"
    report += "| Channel | Trades | Win Rate | Capital Utilized | Net PnL (1 Lot) | % Return |\n"
    report += "|---|---|---|---|---|---|\n"
    
    daily_audit = {
        "date": today,
        "channels": {}
    }
    
    for ch, data in stats.items():
        if data["Total"] == 0:
            continue
            
        ch_name = CHANNEL_NAMES.get(ch, str(ch))
        total = data["Total"]
        wins = data["Wins"]
        losses = data["Losses"]
        cap = data["Capital"]
        pnl = data["PnL"]
        
        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        pct_return = (pnl / cap) * 100 if cap > 0 else 0
        
        report += f"| **{ch_name}** | {total} | {win_rate:.1f}% | ₹{cap:,.0f} | **₹{pnl:,.2f}** | {pct_return:.2f}% |\n"
        
        daily_audit["channels"][ch_name] = {
            "total_trades": total,
            "win_rate": win_rate,
            "capital_utilized": cap,
            "net_pnl": pnl,
            "pct_return": pct_return
        }
        
    with open(DAILY_REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
        
    audit_history = []
    if os.path.exists(AUDIT_REPORT_PATH):
        with open(AUDIT_REPORT_PATH, 'r') as f:
            try:
                audit_history = json.load(f)
            except:
                pass
                
    audit_history.append(daily_audit)
    
    with open(AUDIT_REPORT_PATH, 'w') as f:
        json.dump(audit_history, f, indent=4)
        
    print(f"✅ Telegram EOD Analysis Complete. Saved to {DAILY_REPORT_PATH}")
    
    # Try AI Inference if API key has quota
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        client = OpenAI(api_key=config['openai_api_key'])
        
        prompt = f"Here is today's Telegram PnL data: {json.dumps(daily_audit['channels'])}. Give a 2 sentence summary on which channel performed best and why."
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        print("\n🧠 AI Insight:")
        print(response.choices[0].message.content.strip())
    except Exception as e:
        print("\n⚠️ AI Insight skipped (Quota/Key issue).")

if __name__ == "__main__":
    run_daily_telegram_analysis()
