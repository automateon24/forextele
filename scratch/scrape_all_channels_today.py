"""
FULL TELEGRAM CHANNEL SCRAPER & SIGNAL BACKTEST
Scrapes ALL channels from both accounts (1 & 2),
parses trade signals, and compares with MT5 executed trades.
"""
import asyncio
import json
import re
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpIntermediate
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import Channel, Chat, InputPeerEmpty

BASE_DIR = Path(__file__).parent.parent  # forextele/

# Account credentials from telegram_signal_engine.py
ACC1_API_ID = 15598350
ACC1_API_HASH = "8cb282656e09b0983a9b71365b0813f4"
ACC1_SESSION = BASE_DIR / "scratch" / "scrape_session1"

ACC2_API_ID = 36022932
ACC2_API_HASH = "b9d59de22c25223f94f0e513c04279df"
ACC2_SESSION = BASE_DIR / "scratch" / "scrape_session2"

# Gold/Forex signal keywords
SIGNAL_KEYWORDS = [
    "buy", "sell", "gold", "xauusd", "xau/usd", "tp", "sl", "take profit",
    "stop loss", "entry", "pending", "limit", "stop", "close", "exit",
    "book profit", "btcusd", "gbpjpy", "usdjpy", "eurusd", "gbpusd",
    "gbpnzd", "audjpy", "nzdusd", "usdcad", "gbpcad", "eurcad",
    "us30", "nasdaq", "silver", "xagusd"
]

# Patterns to detect trade signals
def parse_signal(text):
    """Try to extract a trade signal from message text"""
    if not text:
        return None
    
    text_lower = text.lower().strip()
    
    # Skip very short or very long messages (likely not signals)
    if len(text_lower) < 8 or len(text_lower) > 2000:
        return None
    
    # Must have at least one signal keyword
    has_keyword = any(kw in text_lower for kw in ["buy", "sell", "long", "short"])
    if not has_keyword:
        return None
    
    # Must relate to a tradeable asset
    symbols = []
    if any(g in text_lower for g in ["gold", "xauusd", "xau/usd", "xau "]):
        symbols.append("GOLD")
    if "btcusd" in text_lower or "bitcoin" in text_lower:
        symbols.append("BTCUSD")
    if "silver" in text_lower or "xagusd" in text_lower:
        symbols.append("SILVER")
    
    forex_pairs = {
        "eurusd": "EURUSD", "gbpusd": "GBPUSD", "usdjpy": "USDJPY",
        "gbpjpy": "GBPJPY", "audjpy": "AUDJPY", "gbpnzd": "GBPNZD",
        "eurcad": "EURCAD", "gbpcad": "GBPCAD", "nzdusd": "NZDUSD",
        "usdcad": "USDCAD", "audusd": "AUDUSD", "usdchf": "USDCHF",
        "eurjpy": "EURJPY", "eurgbp": "EURGBP"
    }
    for pair_lower, pair_upper in forex_pairs.items():
        if pair_lower in text_lower.replace("/", "").replace(" ", ""):
            symbols.append(pair_upper)
    
    if "us30" in text_lower or "dow" in text_lower:
        symbols.append("US30Cash")
    if "nas" in text_lower and ("100" in text_lower or "daq" in text_lower):
        symbols.append("NASDAQ")
    
    if not symbols:
        # If it says buy/sell but no recognized symbol, check for price patterns
        price_match = re.search(r'(\d{3,4}[\.\d]*)', text_lower)
        if price_match:
            price = float(price_match.group(1))
            if 1800 < price < 6000:
                symbols.append("GOLD")
    
    if not symbols:
        return None
    
    # Determine direction
    action = None
    if re.search(r'\bbuy\b|\blong\b', text_lower):
        action = "BUY"
    elif re.search(r'\bsell\b|\bshort\b', text_lower):
        action = "SELL"
    
    if not action:
        return None
    
    # Extract entry price
    entry = None
    entry_match = re.search(r'(?:@|entry|price|from|at)\s*[:\-]?\s*(\d+\.?\d*)', text_lower)
    if entry_match:
        entry = float(entry_match.group(1))
    else:
        # Fallback: first number near buy/sell that looks like a price
        prices = re.findall(r'(\d{3,5}\.\d{1,2})', text)
        if prices:
            entry = float(prices[0])
    
    # Extract SL
    sl = None
    sl_match = re.search(r'(?:sl|stop\s*loss)[:\s]*(\d+\.?\d*)', text_lower)
    if sl_match:
        sl = float(sl_match.group(1))
    
    # Extract TPs
    tps = []
    tp_matches = re.findall(r'(?:tp\d?|take\s*profit\d?)[:\s]*(\d+\.?\d*)', text_lower)
    for tp_val in tp_matches:
        tps.append(float(tp_val))
    
    return {
        "action": action,
        "symbols": symbols,
        "entry": entry,
        "sl": sl,
        "tps": tps
    }


async def scrape_account(api_id, api_hash, session_path, account_name):
    """Scrape all channels from one Telegram account for today's messages"""
    print(f"\n{'='*60}")
    print(f"  Scraping {account_name}...")
    print(f"{'='*60}")
    
    client = TelegramClient(
        str(session_path), api_id, api_hash,
        connection=ConnectionTcpIntermediate,
        timeout=15,
        request_retries=3,
        auto_reconnect=True
    )
    
    await client.connect()
    if not await client.is_user_authorized():
        print(f"  ❌ {account_name} not authorized! Skipping.")
        await client.disconnect()
        return {}
    
    me = await client.get_me()
    print(f"  ✅ Logged in as: {me.phone} ({me.first_name or ''} {me.last_name or ''})")
    
    # Get all dialogs (channels, groups, etc.)
    dialogs = await client.get_dialogs(limit=None)
    print(f"  📋 Total dialogs: {len(dialogs)}")
    
    # Filter for channels/groups with gold/forex/trading keywords
    target_channels = []
    for d in dialogs:
        entity = d.entity
        if not isinstance(entity, (Channel, Chat)):
            continue
        title = getattr(entity, 'title', '') or ''
        username = getattr(entity, 'username', '') or ''
        title_lower = title.encode('ascii', 'ignore').decode('ascii').lower()
        username_lower = username.lower()
        
        # Include all channels - we want a full picture
        target_channels.append({
            'entity': entity,
            'title': title,
            'username': username,
            'id': entity.id,
            'title_lower': title_lower,
        })
    
    print(f"  📡 Total channels/groups: {len(target_channels)}")
    
    # Today's time window (IST is UTC+5:30, market opens at 5:30 AM IST = 00:00 UTC Monday)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    channel_data = {}
    signal_count = 0
    
    for i, ch_info in enumerate(target_channels):
        entity = ch_info['entity']
        title = ch_info['title']
        title_ascii = title.encode('ascii', 'ignore').decode('ascii').strip() or f"[ID:{entity.id}]"
        
        try:
            messages = []
            async for msg in client.iter_messages(entity, offset_date=now, limit=200):
                if msg.date < today_start:
                    break
                if msg.text:
                    messages.append({
                        'time': msg.date.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        'text': msg.text[:500],  # Cap length
                        'id': msg.id,
                    })
            
            if not messages:
                continue
            
            # Parse signals from messages
            signals = []
            non_signal_count = 0
            for m in messages:
                parsed = parse_signal(m['text'])
                if parsed:
                    signal_count += 1
                    signals.append({
                        **m,
                        'signal': parsed
                    })
                else:
                    non_signal_count += 1
            
            channel_data[title_ascii] = {
                'id': entity.id,
                'username': ch_info['username'],
                'total_messages_today': len(messages),
                'signals_detected': len(signals),
                'non_signal_messages': non_signal_count,
                'signals': signals,
                'sample_messages': [m['text'][:200] for m in messages[:5]],  # First 5 messages for context
            }
            
            sig_str = f" | 🎯 {len(signals)} signals" if signals else ""
            if len(messages) > 0:
                print(f"  [{i+1}/{len(target_channels)}] {title_ascii[:40]:<40} | {len(messages):>3} msgs{sig_str}")
            
        except Exception as e:
            err_str = str(e)
            if "CHANNEL_PRIVATE" in err_str or "ChatAdminRequired" in err_str:
                continue
            if "Could not find the input entity" in err_str:
                continue
            # Only print unexpected errors
            if "FloodWaitError" in err_str:
                wait_match = re.search(r'(\d+)', err_str)
                wait_secs = int(wait_match.group(1)) if wait_match else 30
                print(f"  ⚠️ Rate limited! Waiting {wait_secs}s...")
                await asyncio.sleep(wait_secs)
            else:
                pass  # Silently skip problematic channels
    
    await client.disconnect()
    print(f"\n  📊 {account_name} Summary: {len(channel_data)} active channels, {signal_count} signals detected")
    return channel_data


async def main():
    print("=" * 70)
    print("  FULL TELEGRAM CHANNEL SCRAPE & SIGNAL BACKTEST")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST")
    print("=" * 70)
    
    all_channels = {}
    
    # Scrape Account 1
    try:
        acc1_data = await scrape_account(ACC1_API_ID, ACC1_API_HASH, ACC1_SESSION, "Account 1 (+919901990117)")
        for ch, data in acc1_data.items():
            data['account'] = 'Account 1'
        all_channels.update(acc1_data)
    except Exception as e:
        print(f"  ❌ Account 1 error: {e}")
    
    # Scrape Account 2
    try:
        acc2_data = await scrape_account(ACC2_API_ID, ACC2_API_HASH, ACC2_SESSION, "Account 2 (+919008400869)")
        for ch, data in acc2_data.items():
            if ch in all_channels:
                ch = f"{ch} (Acc2)"
            data['account'] = 'Account 2'
            all_channels[ch] = data
    except Exception as e:
        print(f"  ❌ Account 2 error: {e}")
    
    # ═══ COMPREHENSIVE REPORT ═══
    print("\n" + "=" * 70)
    print("  FULL CHANNEL ACTIVITY REPORT — TODAY")
    print("=" * 70)
    
    # Sort by signal count descending
    sorted_channels = sorted(all_channels.items(), key=lambda x: x[1]['signals_detected'], reverse=True)
    
    total_signals = sum(d['signals_detected'] for _, d in sorted_channels)
    total_messages = sum(d['total_messages_today'] for _, d in sorted_channels)
    channels_with_signals = sum(1 for _, d in sorted_channels if d['signals_detected'] > 0)
    
    print(f"\n  Total Active Channels: {len(sorted_channels)}")
    print(f"  Channels with Trade Signals: {channels_with_signals}")
    print(f"  Total Messages Today: {total_messages}")
    print(f"  Total Trade Signals Detected: {total_signals}")
    
    print(f"\n{'Rank':>4} {'Channel':<45} {'Account':<12} {'Msgs':>5} {'Signals':>8} {'Actions'}")
    print("-" * 120)
    
    for rank, (ch, d) in enumerate(sorted_channels, 1):
        if d['total_messages_today'] == 0:
            continue
        
        # Summarize signal actions
        actions = defaultdict(int)
        symbols = set()
        for sig in d['signals']:
            actions[sig['signal']['action']] += 1
            symbols.update(sig['signal']['symbols'])
        
        action_str = ", ".join(f"{a}:{c}" for a, c in actions.items()) if actions else "-"
        sym_str = f" [{', '.join(symbols)}]" if symbols else ""
        
        print(f"{rank:>4} {ch[:44]:<45} {d['account']:<12} {d['total_messages_today']:>5} {d['signals_detected']:>8} {action_str}{sym_str}")
    
    # ═══ DETAILED SIGNALS FROM EACH CHANNEL ═══
    print("\n" + "=" * 70)
    print("  DETAILED SIGNALS BY CHANNEL")
    print("=" * 70)
    
    for ch, d in sorted_channels:
        if d['signals_detected'] == 0:
            continue
        
        print(f"\n  📡 {ch} ({d['account']}) — {d['signals_detected']} signals / {d['total_messages_today']} messages")
        print(f"  {'─' * 60}")
        
        for sig in d['signals']:
            s = sig['signal']
            entry_str = f" @ {s['entry']}" if s['entry'] else ""
            sl_str = f" | SL: {s['sl']}" if s['sl'] else ""
            tp_str = f" | TPs: {s['tps']}" if s['tps'] else ""
            time_str = sig['time']
            
            print(f"    {time_str} | {s['action']} {', '.join(s['symbols'])}{entry_str}{sl_str}{tp_str}")
            # Show first 150 chars of raw message for context
            msg_preview = sig['text'][:150].replace('\n', ' ↵ ')
            print(f"      └─ \"{msg_preview}\"")
    
    # ═══ Save full data ═══
    output = {
        'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'total_channels': len(sorted_channels),
            'channels_with_signals': channels_with_signals,
            'total_messages': total_messages,
            'total_signals': total_signals,
        },
        'channels': {ch: {k: v for k, v in d.items() if k != 'signals' or True} for ch, d in sorted_channels}
    }
    
    output_file = BASE_DIR / "scratch" / "full_telegram_scrape_today.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str, ensure_ascii=False)
    print(f"\n  📄 Full data saved to: {output_file}")

if __name__ == '__main__':
    asyncio.run(main())
