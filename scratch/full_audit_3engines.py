import MetaTrader5 as mt5, json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(r'C:\anlyzeforex\forextele')
mt5.initialize()
acc = mt5.account_info()
from_date = datetime(2026, 9, 29, 0, 0, 0, tzinfo=timezone.utc)
to_date = datetime.now(timezone.utc) + timedelta(days=1)
deals = mt5.history_deals_get(from_date, to_date) or []
closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT and d.symbol]

BB_MAGICS   = {555000, 555001, 555002, 555003, 555004, 555555}
SMC_MAGICS  = {999001}
TELE_MAGICS = {777777, 888888}

bb   = [d for d in closed_deals if d.magic in BB_MAGICS]
smc  = [d for d in closed_deals if d.magic in SMC_MAGICS]
tele = [d for d in closed_deals if d.magic in TELE_MAGICS]

def stats(ds, alloc):
    if not ds:
        return dict(t=0, w=0, l=0, wr=0, net=0.0, pf=0.0, roi=0.0)
    w = [d for d in ds if (d.profit+d.swap) > 0]
    l = [d for d in ds if (d.profit+d.swap) <= 0]
    net = sum(d.profit+d.swap+d.commission for d in ds)
    gp  = sum(d.profit+d.swap for d in ds if (d.profit+d.swap) > 0)
    gl  = abs(sum(d.profit+d.swap for d in ds if (d.profit+d.swap) <= 0))
    pf  = gp/gl if gl > 0 else 99.0
    return dict(t=len(ds), w=len(w), l=len(l), wr=(len(w)/len(ds))*100, net=net, pf=pf, roi=(net/alloc)*100)

bb_s   = stats(bb,   5000)
smc_s  = stats(smc,  1000)
tele_s = stats(tele, 1000)
all_net = bb_s['net'] + smc_s['net'] + tele_s['net']

SEP = "=" * 80

print()
print(SEP)
print("  FOREXTELE 3-ENGINE FULL PERFORMANCE AUDIT")
print(SEP)
print(f"  Account Balance (Final) : ${acc.balance:.2f}")
print(f"  Starting Capital        : $7,000.00")
print(f"  Net P&L                 : {acc.balance-7000:+.2f} USD")
print(f"  Overall ROI             : {((acc.balance-7000)/7000)*100:+.2f}%")
print(f"  Total Closed Trades     : {len(closed_deals)}")
print(SEP)

# ─── BreakoutBoss ──────────────────────────────────────────────────────────────
print()
print("  ENGINE 1: BREAKOUTBOSS (5-MODEL MULTI-SESSION SUITE)")
print("-" * 60)
print(f"  Total Trades  : {bb_s['t']}")
print(f"  Wins / Losses : {bb_s['w']}W / {bb_s['l']}L  ({bb_s['wr']:.1f}% Win Rate)")
print(f"  Net PnL       : {bb_s['net']:+.2f} USD")
print(f"  Profit Factor : {bb_s['pf']:.2f}")
print(f"  Alloc $5,000  : ROI {bb_s['roi']:+.1f}%")

# per model
BB_NAMES = {555000:'M0-Fixed 0.02', 555001:'M1-Step-Ladder', 555002:'M2-Linear',
            555003:'M3-AI Kelly', 555004:'M4-Half-Kelly', 555555:'Legacy'}
by_model = defaultdict(list)
for d in bb:
    by_model[d.magic].append(d)

print()
print("  Per-Model Breakdown:")
for m in [555000,555001,555002,555003,555004,555555]:
    ds = by_model[m]
    if not ds:
        continue
    s = stats(ds, 1000)
    name = BB_NAMES[m]
    print(f"    {name:<18} | {s['t']:>3} trades | {s['w']}W/{s['l']}L | WR:{s['wr']:>5.1f}% | Net:{s['net']:>+8.2f} | PF:{s['pf']:.2f}")

# per session from comment
sess_map = defaultdict(lambda: dict(pnl=0.0, t=0, w=0))
for d in bb:
    c = (d.comment or '').upper()
    for sx in ['GANN','FRA','LON','NYC','NYP','LNC','ASIA']:
        if sx in c:
            sess_map[sx]['pnl'] += d.profit + d.swap
            sess_map[sx]['t']   += 1
            if (d.profit+d.swap) > 0:
                sess_map[sx]['w'] += 1
            break

print()
print("  Per-Session Breakdown:")
for sx, sv in sorted(sess_map.items(), key=lambda x: -x[1]['pnl']):
    if sv['t'] == 0:
        continue
    swr = sv['w']/sv['t']*100
    print(f"    {sx:<8} | {sv['t']:>3} trades | {sv['w']}W | WR:{swr:>5.1f}% | Net:{sv['pnl']:>+8.2f}")

# ─── SMC ──────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  ENGINE 2: AUTONOMOUS AI MARKET SCANNER (SMC)")
print("-" * 60)
if smc:
    print(f"  Total Trades  : {smc_s['t']}")
    print(f"  Wins / Losses : {smc_s['w']}W / {smc_s['l']}L  ({smc_s['wr']:.1f}% Win Rate)")
    print(f"  Net PnL       : {smc_s['net']:+.2f} USD")
    print(f"  Profit Factor : {smc_s['pf']:.2f}")
    print(f"  Alloc $1,000  : ROI {smc_s['roi']:+.1f}%")

    day_map = defaultdict(lambda: dict(pnl=0.0, t=0, w=0))
    for d in smc:
        dt = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%Y-%m-%d")
        day_map[dt]['pnl'] += d.profit + d.swap
        day_map[dt]['t']   += 1
        if (d.profit+d.swap) > 0:
            day_map[dt]['w'] += 1
    print()
    print("  Day-by-Day SMC:")
    for dt in sorted(day_map):
        sv = day_map[dt]
        dwr = sv['w']/sv['t']*100
        print(f"    {dt} | {sv['t']:>3} trades | {sv['w']}W | WR:{dwr:>5.1f}% | Net:{sv['pnl']:>+8.2f}")
else:
    print("  No SMC trades found.")

# ─── Telegram ─────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  ENGINE 3: TELEGRAM VIP SIGNAL ENGINE")
print("-" * 60)
if tele:
    print(f"  Total Trades  : {tele_s['t']}")
    print(f"  Wins / Losses : {tele_s['w']}W / {tele_s['l']}L  ({tele_s['wr']:.1f}% Win Rate)")
    print(f"  Net PnL       : {tele_s['net']:+.2f} USD")
    print(f"  Profit Factor : {tele_s['pf']:.2f}")
    print(f"  Alloc $1,000  : ROI {tele_s['roi']:+.1f}%")

    ch_map = defaultdict(lambda: dict(pnl=0.0, t=0, w=0))
    for d in tele:
        c = d.comment or 'UNKNOWN'
        m = re.search(r'(\d{4,})', c)
        key = m.group(1) if m else c[:28].strip()
        ch_map[key]['pnl'] += d.profit + d.swap
        ch_map[key]['t']   += 1
        if (d.profit+d.swap) > 0:
            ch_map[key]['w'] += 1

    all_chan = sorted(ch_map.items(), key=lambda x: -x[1]['pnl'])
    print()
    print(f"  {'CHANNEL/COMMENT':<28} | {'TRADES':>6} | {'W/L':<7} | {'WIN%':>5} | {'NET PNL':>10}")
    print("  " + "-"*68)
    for ch, cv in all_chan:
        if cv['t'] == 0:
            continue
        cwr = cv['w']/cv['t']*100
        wl = f"{cv['w']}W/{cv['t']-cv['w']}L"
        print(f"  {ch[:28]:<28} | {cv['t']:>6} | {wl:<7} | {cwr:>5.1f}% | {cv['pnl']:>+10.2f}")
else:
    print("  No Telegram trades found.")

# ─── Grand Summary ─────────────────────────────────────────────────────────────
print()
print(SEP)
print("  GRAND PORTFOLIO SUMMARY")
print("-" * 60)
print(f"  {'Engine':<35} | {'Alloc':>7} | {'Trades':>6} | {'Net PnL':>10} | {'ROI':>7}")
print("  " + "-"*70)
print(f"  {'BreakoutBoss (5 Models)':<35} | {'$5,000':>7} | {bb_s['t']:>6} | {bb_s['net']:>+10.2f} | {bb_s['roi']:>+6.1f}%")
print(f"  {'Autonomous SMC Scanner':<35} | {'$1,000':>7} | {smc_s['t']:>6} | {smc_s['net']:>+10.2f} | {smc_s['roi']:>+6.1f}%")
print(f"  {'Telegram VIP Signals':<35} | {'$1,000':>7} | {tele_s['t']:>6} | {tele_s['net']:>+10.2f} | {tele_s['roi']:>+6.1f}%")
print("  " + "-"*70)
print(f"  {'TOTAL PORTFOLIO':<35} | {'$7,000':>7} | {len(closed_deals):>6} | {all_net:>+10.2f} | {(all_net/7000)*100:>+6.1f}%")
print()
print(f"  Account Start: $7,000.00  ->  Final: ${acc.balance:.2f}  ->  Net: {acc.balance-7000:+.2f}")
print(SEP)

# AI KB
kb_path = BASE_DIR / "data" / "trade_learning_knowledge_base.jsonl"
if kb_path.exists():
    entries = [json.loads(l) for l in kb_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    closed_kb = [e for e in entries if e.get('status') in ['CLOSED_WIN','CLOSED_LOSS','CLOSED_BE','closed']]
    wins_kb   = [e for e in closed_kb if e.get('status') == 'CLOSED_WIN']
    print()
    print("  AI LEARNING ENGINE KNOWLEDGE BASE:")
    print(f"    Total signals ingested : {len(entries)}")
    print(f"    Closed & analyzed      : {len(closed_kb)}")
    if closed_kb:
        print(f"    Win Rate (KB)          : {(len(wins_kb)/len(closed_kb))*100:.1f}%")
    print(f"    Open / Monitoring      : {len(entries) - len(closed_kb)}")
    print(SEP)

mt5.shutdown()
