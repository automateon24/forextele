"""
FULL DAY TRADE AUDIT — Sep 21, 2026
Pulls ALL deals from MT5, cross-references with Telegram channel logs,
and produces a detailed per-channel P&L breakdown.
"""
import MetaTrader5 as mt5
import json
import re
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent  # forextele/
MT5_CFG = BASE_DIR / "mt5_config.json"
AI_LOG = BASE_DIR / "message_ai_log.json"
MT5_LOG = BASE_DIR / "mt5_orders.log"
OUTPUT_FILE = BASE_DIR / "scratch" / "full_day_audit_report.json"

# ─── MT5 Connection ───
def connect_mt5():
    if mt5.initialize():
        return True
    cfg = json.load(open(MT5_CFG)) if MT5_CFG.exists() else {}
    if not cfg:
        print("ERROR: mt5_config.json not found")
        return False
    if mt5.initialize(login=int(cfg.get("login",0)), server=cfg.get("server",""), password=cfg.get("password","")):
        return True
    print(f"MT5 connection failed: {mt5.last_error()}")
    return False

# ─── Fetch ALL deals for today ───
def fetch_today_deals():
    """Fetch all deals (entries + exits) from today's market open"""
    # Use a wide window: from midnight UTC today to now
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    # Go back 24h to be safe
    from_time = today_start - timedelta(hours=6)
    to_time = now + timedelta(hours=1)
    
    deals = mt5.history_deals_get(from_time, to_time)
    if deals is None:
        print(f"No deals found. Error: {mt5.last_error()}")
        return []
    return list(deals)

def fetch_today_orders():
    """Fetch all orders (including pending) from today"""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    from_time = today_start - timedelta(hours=6)
    to_time = now + timedelta(hours=1)
    
    orders = mt5.history_orders_get(from_time, to_time)
    if orders is None:
        return []
    return list(orders)

def fetch_open_positions():
    """Get currently open positions"""
    positions = mt5.positions_get()
    if positions is None:
        return []
    return list(positions)

def fetch_open_orders():
    """Get pending orders"""
    orders = mt5.orders_get()
    if orders is None:
        return []
    return list(orders)

# ─── Load AI log for channel mapping ───
def load_ai_log():
    if not AI_LOG.exists():
        return []
    with open(AI_LOG, 'r', encoding='utf-8') as f:
        return json.load(f)

# ─── Parse mt5_orders.log for ticket-to-channel mapping ───
def parse_mt5_log_for_channels():
    """Extract ticket -> order details from mt5_orders.log"""
    ticket_map = {}
    if not MT5_LOG.exists():
        return ticket_map
    
    current_order = {}
    with open(MT5_LOG, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '2026-09-21' not in line:
                continue
            
            # Parse order placement lines
            send_match = re.search(r'Sending Order to Broker: (BUY|SELL) ([\d.]+) (\w+) @ ([\d.]+) \| SL: ([\d.]+) \| TP: ([\d.]+)', line)
            if send_match:
                current_order = {
                    'action': send_match.group(1),
                    'volume': float(send_match.group(2)),
                    'symbol': send_match.group(3),
                    'price': float(send_match.group(4)),
                    'sl': float(send_match.group(5)),
                    'tp': float(send_match.group(6)),
                    'time': line[:23]
                }
            
            # Match SUCCESS line to get ticket
            success_match = re.search(r'SUCCESS! Trade (\d+) opened', line)
            if success_match and current_order:
                ticket = int(success_match.group(1))
                current_order['ticket'] = ticket
                ticket_map[ticket] = current_order.copy()
                current_order = {}
            
            # Parse errors
            error_match = re.search(r'Order failed definitively.*Symbol: (\w+).*Price: ([\d.]+)', line)
            if error_match:
                pass  # We'll count these separately
    
    return ticket_map

# ─── Build ticket-to-channel mapping from AI log ───
def build_channel_map(ai_log):
    """Map ticket numbers to channel names"""
    ticket_to_channel = {}
    for entry in ai_log:
        ticket = entry.get('ticket')
        channel = entry.get('channel_name', 'Unknown')
        if ticket:
            ticket_to_channel[ticket] = channel
        # Also try to extract from ai_reply
        if not ticket and entry.get('ai_reply'):
            try:
                reply = json.loads(entry['ai_reply'])
                if reply.get('ticket'):
                    ticket_to_channel[reply['ticket']] = channel
            except:
                pass
    return ticket_to_channel

# ─── Main Analysis ───
def main():
    print("=" * 70)
    print("  FULL DAY TRADE AUDIT — September 21, 2026")
    print("=" * 70)
    
    if not connect_mt5():
        sys.exit(1)
    
    account = mt5.account_info()
    print(f"\nAccount: {account.login} | Balance: ${account.balance:.2f} | Equity: ${account.equity:.2f}")
    print(f"Profit (floating): ${account.profit:.2f}")
    print(f"Margin Used: ${account.margin:.2f} | Free: ${account.margin_free:.2f}")
    
    # 1. Fetch all data
    print("\n[1] Fetching today's deals from MT5...")
    deals = fetch_today_deals()
    print(f"    Found {len(deals)} deals")
    
    print("[2] Fetching today's orders from MT5...")
    orders = fetch_today_orders()
    print(f"    Found {len(orders)} orders")
    
    print("[3] Fetching open positions...")
    open_pos = fetch_open_positions()
    print(f"    Found {len(open_pos)} open positions")
    
    print("[4] Fetching pending orders...")
    pending = fetch_open_orders()
    print(f"    Found {len(pending)} pending orders")
    
    print("[5] Loading AI message log...")
    ai_log = load_ai_log()
    print(f"    Found {len(ai_log)} AI log entries")
    
    print("[6] Parsing mt5_orders.log...")
    ticket_map = parse_mt5_log_for_channels()
    print(f"    Mapped {len(ticket_map)} tickets from log")
    
    print("[7] Building channel map...")
    channel_map = build_channel_map(ai_log)
    print(f"    Mapped {len(channel_map)} tickets to channels")
    
    # 2. Organize deals by position
    # Deal types: 0=BUY, 1=SELL, 2=BALANCE, 3=CREDIT
    # Deal entry: 0=IN, 1=OUT, 2=INOUT, 3=OUT_BY
    
    # Build position groups (entry deal + exit deal = closed trade)
    position_deals = defaultdict(list)
    balance_deals = []
    
    for d in deals:
        if d.type in (2, 3):  # Balance/Credit operations
            balance_deals.append(d)
            continue
        position_deals[d.position_id].append(d)
    
    # 3. Reconstruct closed trades
    closed_trades = []
    partially_closed = []
    
    for pos_id, pos_deals in position_deals.items():
        entries = [d for d in pos_deals if d.entry == 0]  # IN
        exits = [d for d in pos_deals if d.entry == 1]    # OUT
        
        if not entries:
            continue
        
        entry_deal = entries[0]
        total_entry_volume = sum(d.volume for d in entries)
        total_exit_volume = sum(d.volume for d in exits)
        total_exit_profit = sum(d.profit for d in exits)
        total_commission = sum(d.commission for d in entries) + sum(d.commission for d in exits)
        total_swap = sum(d.swap for d in exits)
        total_fee = sum(d.fee for d in entries) + sum(d.fee for d in exits)
        
        # Get channel from comment or ticket map
        comment = entry_deal.comment or ""
        channel = "Unknown"
        
        # Try channel_map first (from AI log)
        if entry_deal.order in channel_map:
            channel = channel_map[entry_deal.order]
        elif entry_deal.position_id in channel_map:
            channel = channel_map[entry_deal.position_id]
        
        # Try to extract from comment
        if channel == "Unknown" and comment:
            bracket_match = re.search(r'\[(.+?)\]', comment)
            if bracket_match:
                channel = bracket_match.group(1)
            elif 'AI:' in comment:
                channel = f"Swarm AI ({comment.strip()})"
            elif comment.strip():
                channel = f"Comment: {comment.strip()}"
        
        # Try ticket_map (from mt5_orders.log)
        if channel == "Unknown":
            for d in entries:
                if d.order in ticket_map:
                    log_entry = ticket_map[d.order]
                    channel = f"Log: {log_entry.get('symbol', '?')} {log_entry.get('action', '?')}"
                    break
        
        entry_time = datetime.fromtimestamp(entry_deal.time)
        
        trade = {
            'position_id': pos_id,
            'ticket': entry_deal.order,
            'symbol': entry_deal.symbol,
            'type': 'BUY' if entry_deal.type == 0 else 'SELL',
            'entry_price': entry_deal.price,
            'entry_volume': total_entry_volume,
            'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'channel': channel,
            'comment': comment,
            'status': 'CLOSED' if abs(total_exit_volume - total_entry_volume) < 0.001 else 'PARTIAL',
            'exit_volume': total_exit_volume,
            'exit_profit': total_exit_profit,
            'commission': total_commission,
            'swap': total_swap,
            'fee': total_fee,
            'net_pnl': total_exit_profit + total_commission + total_swap + total_fee,
            'exit_count': len(exits),
        }
        
        if exits:
            trade['exit_price'] = exits[-1].price
            trade['exit_time'] = datetime.fromtimestamp(exits[-1].time).strftime('%Y-%m-%d %H:%M:%S')
        
        if trade['status'] == 'CLOSED':
            closed_trades.append(trade)
        else:
            partially_closed.append(trade)
    
    # 4. Open positions detail
    open_trades = []
    for p in open_pos:
        comment = p.comment or ""
        channel = "Unknown"
        
        if p.ticket in channel_map:
            channel = channel_map[p.ticket]
        elif comment:
            bracket_match = re.search(r'\[(.+?)\]', comment)
            if bracket_match:
                channel = bracket_match.group(1)
            elif 'AI:' in comment:
                channel = f"Swarm AI ({comment.strip()})"
            elif comment.strip():
                channel = f"Comment: {comment.strip()}"
        
        if channel == "Unknown" and p.ticket in ticket_map:
            log_entry = ticket_map[p.ticket]
            channel = f"Log: {log_entry.get('symbol', '?')} {log_entry.get('action', '?')}"
        
        open_trades.append({
            'ticket': p.ticket,
            'symbol': p.symbol,
            'type': 'BUY' if p.type == 0 else 'SELL',
            'volume': p.volume,
            'entry_price': p.price_open,
            'current_price': p.price_current,
            'sl': p.sl,
            'tp': p.tp,
            'profit': p.profit,
            'swap': p.swap,
            'commission': getattr(p, 'commission', 0),
            'comment': comment,
            'channel': channel,
            'open_time': datetime.fromtimestamp(p.time).strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    # ═══════════════════════════════════════════════════════
    # 5. ANALYSIS & REPORTING
    # ═══════════════════════════════════════════════════════
    
    print("\n" + "=" * 70)
    print("  CLOSED TRADES ANALYSIS")
    print("=" * 70)
    
    # Sort by time
    closed_trades.sort(key=lambda x: x['entry_time'])
    
    total_gross = sum(t['exit_profit'] for t in closed_trades)
    total_commission = sum(t['commission'] for t in closed_trades)
    total_swap = sum(t['swap'] for t in closed_trades)
    total_fee = sum(t['fee'] for t in closed_trades)
    total_net = sum(t['net_pnl'] for t in closed_trades)
    
    wins = [t for t in closed_trades if t['net_pnl'] > 0]
    losses = [t for t in closed_trades if t['net_pnl'] <= 0]
    
    print(f"\nTotal Closed Trades: {len(closed_trades)}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)} | Win Rate: {len(wins)/max(len(closed_trades),1)*100:.1f}%")
    print(f"Gross Profit: ${total_gross:.2f}")
    print(f"Commission: ${total_commission:.2f}")
    print(f"Swap: ${total_swap:.2f}")
    print(f"Fee: ${total_fee:.2f}")
    print(f"═══ NET P&L (Closed): ${total_net:.2f} ═══")
    
    # Per-trade listing
    print(f"\n{'#':>3} {'Time':>19} {'Symbol':>8} {'Dir':>4} {'Vol':>5} {'Entry':>10} {'Exit':>10} {'Gross':>8} {'Net':>8} {'Channel'}")
    print("-" * 120)
    for i, t in enumerate(closed_trades, 1):
        exit_price = t.get('exit_price', '?')
        print(f"{i:>3} {t['entry_time']:>19} {t['symbol']:>8} {t['type']:>4} {t['entry_volume']:>5.2f} {t['entry_price']:>10.5f} {exit_price:>10} ${t['exit_profit']:>7.2f} ${t['net_pnl']:>7.2f} {t['channel']}")
    
    # ═══ CHANNEL BREAKDOWN ═══
    print("\n" + "=" * 70)
    print("  CHANNEL-BY-CHANNEL P&L BREAKDOWN")
    print("=" * 70)
    
    channel_stats = defaultdict(lambda: {
        'trades': 0, 'wins': 0, 'losses': 0,
        'gross_pnl': 0, 'net_pnl': 0, 'commission': 0,
        'biggest_win': 0, 'biggest_loss': 0,
        'symbols': set(), 'trade_list': []
    })
    
    for t in closed_trades:
        ch = t['channel']
        s = channel_stats[ch]
        s['trades'] += 1
        if t['net_pnl'] > 0:
            s['wins'] += 1
            s['biggest_win'] = max(s['biggest_win'], t['net_pnl'])
        else:
            s['losses'] += 1
            s['biggest_loss'] = min(s['biggest_loss'], t['net_pnl'])
        s['gross_pnl'] += t['exit_profit']
        s['net_pnl'] += t['net_pnl']
        s['commission'] += t['commission']
        s['symbols'].add(t['symbol'])
        s['trade_list'].append({
            'time': t['entry_time'],
            'symbol': t['symbol'],
            'type': t['type'],
            'volume': t['entry_volume'],
            'net_pnl': t['net_pnl']
        })
    
    # Sort by net PnL (worst first to highlight problem channels)
    sorted_channels = sorted(channel_stats.items(), key=lambda x: x[1]['net_pnl'])
    
    print(f"\n{'Rank':>4} {'Channel':<35} {'Trades':>6} {'Wins':>5} {'WR%':>5} {'Gross':>9} {'Net P&L':>9} {'BigWin':>8} {'BigLoss':>9}")
    print("-" * 120)
    for rank, (ch, s) in enumerate(sorted_channels, 1):
        wr = s['wins'] / max(s['trades'], 1) * 100
        print(f"{rank:>4} {ch:<35} {s['trades']:>6} {s['wins']:>5} {wr:>4.0f}% ${s['gross_pnl']:>8.2f} ${s['net_pnl']:>8.2f} ${s['biggest_win']:>7.2f} ${s['biggest_loss']:>8.2f}")
    
    # ═══ OPEN POSITIONS ═══
    print("\n" + "=" * 70)
    print("  CURRENTLY OPEN POSITIONS")
    print("=" * 70)
    
    total_open_pnl = sum(p['profit'] for p in open_trades)
    print(f"\n{'Ticket':>12} {'Time':>19} {'Symbol':>8} {'Dir':>4} {'Vol':>5} {'Entry':>10} {'Current':>10} {'SL':>10} {'TP':>10} {'P&L':>8} {'Channel'}")
    print("-" * 140)
    for p in open_trades:
        print(f"{p['ticket']:>12} {p['open_time']:>19} {p['symbol']:>8} {p['type']:>4} {p['volume']:>5.2f} {p['entry_price']:>10.5f} {p['current_price']:>10.5f} {p['sl']:>10.5f} {p['tp']:>10.5f} ${p['profit']:>7.2f} {p['channel']}")
    print(f"\nTotal Open P&L: ${total_open_pnl:.2f}")
    
    # ═══ PENDING ORDERS ═══
    if pending:
        print(f"\n{'=' * 70}")
        print("  PENDING ORDERS")
        print(f"{'=' * 70}")
        for o in pending:
            otype = {2:'BUY_LIMIT', 3:'SELL_LIMIT', 4:'BUY_STOP', 5:'SELL_STOP'}.get(o.type, str(o.type))
            print(f"  Ticket {o.ticket} | {o.symbol} {otype} {o.volume_current} @ {o.price_open} | SL: {o.sl} | TP: {o.tp} | {o.comment}")
    
    # ═══ GRAND TOTAL ═══
    print("\n" + "=" * 70)
    print("  GRAND TOTAL — DAY SUMMARY")
    print("=" * 70)
    print(f"  Closed P&L (Net):    ${total_net:>10.2f}")
    print(f"  Open P&L (Float):    ${total_open_pnl:>10.2f}")
    print(f"  ─────────────────────────────────")
    print(f"  COMBINED DAY P&L:    ${total_net + total_open_pnl:>10.2f}")
    print(f"  Account Balance:     ${account.balance:>10.2f}")
    print(f"  Account Equity:      ${account.equity:>10.2f}")
    print("=" * 70)
    
    # ═══ WORST CHANNEL ANALYSIS ═══
    print("\n" + "=" * 70)
    print("  PROBLEM CHANNELS — DETAILED ANALYSIS")
    print("=" * 70)
    
    for ch, s in sorted_channels:
        if s['net_pnl'] >= 0:
            continue
        print(f"\n  ❌ {ch} — Net Loss: ${s['net_pnl']:.2f}")
        print(f"     Trades: {s['trades']} | Wins: {s['wins']} | Losses: {s['losses']} | WR: {s['wins']/max(s['trades'],1)*100:.0f}%")
        print(f"     Symbols: {', '.join(s['symbols'])}")
        print(f"     Biggest Win: ${s['biggest_win']:.2f} | Biggest Loss: ${s['biggest_loss']:.2f}")
        print(f"     Individual trades:")
        for tr in s['trade_list']:
            status = "✅" if tr['net_pnl'] > 0 else "❌"
            print(f"       {status} {tr['time']} | {tr['type']} {tr['volume']} {tr['symbol']} | P&L: ${tr['net_pnl']:.2f}")
    
    # ═══ BEST CHANNEL ANALYSIS ═══
    print("\n" + "=" * 70)
    print("  PROFITABLE CHANNELS — DETAILED ANALYSIS")
    print("=" * 70)
    
    for ch, s in reversed(sorted_channels):
        if s['net_pnl'] <= 0:
            continue
        print(f"\n  ✅ {ch} — Net Profit: ${s['net_pnl']:.2f}")
        print(f"     Trades: {s['trades']} | Wins: {s['wins']} | WR: {s['wins']/max(s['trades'],1)*100:.0f}%")
        print(f"     Individual trades:")
        for tr in s['trade_list']:
            status = "✅" if tr['net_pnl'] > 0 else "❌"
            print(f"       {status} {tr['time']} | {tr['type']} {tr['volume']} {tr['symbol']} | P&L: ${tr['net_pnl']:.2f}")
    
    # ═══ Save to JSON for artifact ═══
    report = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'account': {
            'login': account.login,
            'balance': account.balance,
            'equity': account.equity,
            'profit': account.profit,
        },
        'summary': {
            'total_closed_trades': len(closed_trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': f"{len(wins)/max(len(closed_trades),1)*100:.1f}%",
            'gross_pnl': round(total_gross, 2),
            'net_closed_pnl': round(total_net, 2),
            'commission': round(total_commission, 2),
            'swap': round(total_swap, 2),
            'open_pnl': round(total_open_pnl, 2),
            'combined_day_pnl': round(total_net + total_open_pnl, 2),
        },
        'channel_breakdown': {
            ch: {
                'trades': s['trades'],
                'wins': s['wins'],
                'losses': s['losses'],
                'win_rate': f"{s['wins']/max(s['trades'],1)*100:.0f}%",
                'net_pnl': round(s['net_pnl'], 2),
                'gross_pnl': round(s['gross_pnl'], 2),
                'biggest_win': round(s['biggest_win'], 2),
                'biggest_loss': round(s['biggest_loss'], 2),
                'symbols': list(s['symbols']),
                'trades_detail': s['trade_list']
            }
            for ch, s in sorted_channels
        },
        'closed_trades': closed_trades,
        'open_positions': open_trades,
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to: {OUTPUT_FILE}")
    
    mt5.shutdown()

if __name__ == '__main__':
    main()
