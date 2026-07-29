import MetaTrader5 as mt5
import json
import os
import csv
from datetime import datetime, timedelta
import pandas as pd

BASE_DIR = r"c:\anlyzeforex\forextele"
CONFIG_PATH = os.path.join(BASE_DIR, "mt5_config.json")
AUDIT_CSV = os.path.join(BASE_DIR, "signals_audit.csv")
THREAD_STATUS_JSON = os.path.join(BASE_DIR, "thread_status.json")

def generate_report():
    report = {}
    
    # 1. MT5 Connection & Account Info
    if not mt5.initialize():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f: cfg = json.load(f)
            mt5.initialize(login=cfg.get('login'), server=cfg.get('server'), password=cfg.get('password'))

    mt5_online = mt5.terminal_info() is not None
    report['mt5_online'] = mt5_online
    
    if mt5_online:
        acc = mt5.account_info()
        if acc:
            report['account'] = {
                'login': acc.login,
                'server': acc.server,
                'balance': acc.balance,
                'equity': acc.equity,
                'profit': acc.profit,
                'margin_free': acc.margin_free,
                'leverage': acc.leverage
            }
            
        # Fetch Deals History
        now = datetime.now()
        start_time = datetime(2026, 7, 1) # Full July 2026 window
        deals = mt5.history_deals_get(start_time, now)
        
        strat_deals = []
        tele_deals = []
        manual_deals = []
        
        if deals:
            for d in deals:
                if d.entry == mt5.DEAL_ENTRY_OUT: # Only closed trade out entries
                    comment = d.comment or ""
                    magic = d.magic
                    pnl = d.profit + d.swap + d.commission
                    
                    deal_info = {
                        'ticket': d.ticket,
                        'symbol': d.symbol,
                        'type': 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL',
                        'volume': d.volume,
                        'price': d.price,
                        'profit': pnl,
                        'comment': comment,
                        'magic': magic,
                        'time': datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    if magic == 777777 or "Tele:" in comment or "telegram" in comment.lower():
                        tele_deals.append(deal_info)
                    elif magic > 0 or "Strategy" in comment or "DNA" in comment or "AI" in comment:
                        strat_deals.append(deal_info)
                    else:
                        manual_deals.append(deal_info)

        report['deals_summary'] = {
            'strategy': {
                'count': len(strat_deals),
                'pnl': sum(d['profit'] for d in strat_deals),
                'wins': sum(1 for d in strat_deals if d['profit'] > 0),
                'losses': sum(1 for d in strat_deals if d['profit'] < 0),
                'trades': strat_deals
            },
            'telegram': {
                'count': len(tele_deals),
                'pnl': sum(d['profit'] for d in tele_deals),
                'wins': sum(1 for d in tele_deals if d['profit'] > 0),
                'losses': sum(1 for d in tele_deals if d['profit'] < 0),
                'trades': tele_deals
            },
            'other_manual': {
                'count': len(manual_deals),
                'pnl': sum(d['profit'] for d in manual_deals),
                'wins': sum(1 for d in manual_deals if d['profit'] > 0),
                'losses': sum(1 for d in manual_deals if d['profit'] < 0),
                'trades': manual_deals
            }
        }
        
        # Open Positions
        open_pos = mt5.positions_get()
        open_list = []
        if open_pos:
            for p in open_pos:
                open_list.append({
                    'ticket': p.ticket,
                    'symbol': p.symbol,
                    'type': 'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL',
                    'volume': p.volume,
                    'price_open': p.price_open,
                    'price_current': p.price_current,
                    'profit': p.profit + p.swap,
                    'comment': p.comment,
                    'magic': p.magic
                })
        report['open_positions'] = open_list

    # 2. Audit CSV Telegram Parsing Summary
    audit_summary = {'total_signals': 0, 'status_counts': {}, 'channel_counts': {}}
    if os.path.exists(AUDIT_CSV):
        try:
            df = pd.read_csv(AUDIT_CSV)
            audit_summary['total_signals'] = len(df)
            if 'Status' in df.columns:
                audit_summary['status_counts'] = df['Status'].value_counts().to_dict()
            if 'Channel' in df.columns:
                audit_summary['channel_counts'] = df['Channel'].value_counts().to_dict()
        except Exception as e:
            audit_summary['error'] = str(e)
    report['audit_summary'] = audit_summary

    # 3. Thread Status
    if os.path.exists(THREAD_STATUS_JSON):
        try:
            with open(THREAD_STATUS_JSON) as f:
                report['thread_status'] = json.load(f)
        except:
            report['thread_status'] = {}
            
    print(json.dumps(report, indent=2))
    
    with open(os.path.join(BASE_DIR, "performance_report_output.json"), "w") as f:
        json.dump(report, f, indent=2)

if __name__ == '__main__':
    generate_report()
