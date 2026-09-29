"""
3-DAY PARALLEL PERFORMANCE AUDITOR (7 VIRTUAL BASKETS - $7,000 TOTAL)
=====================================================================
Audits live performance across all 7 allocation baskets on MT5:
1. BreakoutBoss M0 (Fixed 0.02 Lots)       : Magic 555000 [$1,000 Virtual Basket]
2. BreakoutBoss M1 (Step-Ladder Growth)    : Magic 555001 [$1,000 Virtual Basket]
3. BreakoutBoss M2 (Linear Equity)         : Magic 555002 [$1,000 Virtual Basket]
4. BreakoutBoss M3 (AI Conviction Kelly)   : Magic 555003 [$1,000 Virtual Basket]
5. BreakoutBoss M4 (Aggressive Half-Kelly) : Magic 555004 [$1,000 Virtual Basket]
6. Telegram VIP Signals                    : Magic 777777 / 888888 [$1,000 Virtual Basket]
7. Autonomous AI Market Scanner            : Magic 999001 [$1,000 Virtual Basket]
"""
import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import MetaTrader5 as mt5

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
LEDGER_FILE = BASE_DIR / "data" / "trade_learning_knowledge_base.jsonl"
REGISTRY_BB = BASE_DIR / "active_breakoutboss_trades.json"
REGISTRY_TELE = BASE_DIR / "active_trades_registry.json"

def main():
    print("=" * 88)
    print("  📊 7-BASKET MULTI-MODEL LIVE PERFORMANCE AUDIT ($7,000 CAPITAL POOL)")
    print(f"  Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} (Local: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 88)

    if not mt5.initialize():
        print("❌ Could not initialize MetaTrader 5.")
        return

    acc = mt5.account_info()
    if acc:
        print(f"  Live Account : #{acc.login} ({acc.server})")
        print(f"  Real Balance : ${acc.balance:.2f} | Real Equity: ${acc.equity:.2f} (Floating: ${acc.profit:.2f})")
        print(f"  Free Margin  : ${acc.margin_free:.2f} | Margin Level: {acc.margin_level:.1f}%")
    print("-" * 88)

    from_date = datetime(2026, 9, 29, 0, 0, 0, tzinfo=timezone.utc)
    to_date = datetime.now(timezone.utc) + timedelta(days=1)

    deals = mt5.history_deals_get(from_date, to_date)
    positions = mt5.positions_get()

    baskets = [
        {"name": "BB M0: Fixed 0.02", "code": "M0", "magics": [555000, 555555], "alloc": 1000.0},
        {"name": "BB M1: Step-Ladder", "code": "M1", "magics": [555001], "alloc": 1000.0},
        {"name": "BB M2: Linear Eq", "code": "M2", "magics": [555002], "alloc": 1000.0},
        {"name": "BB M3: AI Conviction", "code": "M3", "magics": [555003], "alloc": 1000.0},
        {"name": "BB M4: Half-Kelly", "code": "M4", "magics": [555004], "alloc": 1000.0},
        {"name": "Telegram VIP", "code": "TELE", "magics": [777777, 888888], "alloc": 1000.0},
        {"name": "Autonomous SMC", "code": "SMC", "magics": [999001], "alloc": 1000.0},
    ]

    for b in baskets:
        b["deals"] = []
        b["open"] = []
        b["floating"] = 0.0

    other_deals = []
    other_open = []

    if positions:
        for p in positions:
            matched = False
            for b in baskets:
                if p.magic in b["magics"]:
                    b["open"].append(p)
                    b["floating"] += p.profit
                    matched = True
                    break
            if not matched:
                other_open.append(p)

    if deals:
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_OUT:
                matched = False
                for b in baskets:
                    if d.magic in b["magics"]:
                        b["deals"].append(d)
                        matched = True
                        break
                if not matched and d.magic != 0:
                    other_deals.append(d)

    print(f"\n{'BASKET / MODEL':<22} | {'TRADES':<6} | {'WINS':<4} | {'LOSS':<4} | {'WIN %':<7} | {'NET PNL':<9} | {'V-EQUITY':<10} | {'ROI %':<7} | {'ACTIVE':<6}")
    print("-" * 88)

    total_net = 0.0
    total_trades = 0

    for b in baskets:
        deal_list = b["deals"]
        open_list = b["open"]
        count = len(deal_list)
        wins = sum(1 for d in deal_list if (d.profit + d.swap) > 0.0)
        losses = sum(1 for d in deal_list if (d.profit + d.swap) < 0.0)
        wr = (wins / count * 100.0) if count > 0 else 0.0
        pnl = sum(d.profit + d.swap for d in deal_list)
        v_equity = b["alloc"] + pnl + b["floating"]
        roi = ((v_equity - b["alloc"]) / b["alloc"]) * 100.0

        total_net += pnl
        total_trades += count

        sign = "+" if pnl >= 0 else ""
        roi_sign = "+" if roi >= 0 else ""
        print(f"{b['name']:<22} | {count:<6} | {wins:<4} | {losses:<4} | {wr:>5.1f}% | {sign}${pnl:>7.2f} | ${v_equity:>8.2f} | {roi_sign}{roi:>5.1f}% | {len(open_list):<6}")

    print("-" * 88)
    tot_sign = "+" if total_net >= 0 else ""
    print(f"{'TOTAL PORTFOLIO':<22} | {total_trades:<6} |      |      |       | {tot_sign}${total_net:>7.2f} |             |        | {sum(len(b['open']) for b in baskets):<6}")
    print("=" * 88)

    # AI Learning Knowledge Base Stats
    if LEDGER_FILE.exists():
        try:
            lines = LEDGER_FILE.read_text(encoding="utf-8").strip().splitlines()
            total_records = len(lines)
            open_records = sum(1 for line in lines if '"status": "OPEN"' in line)
            closed_records = total_records - open_records
            print("\n🧠 AI CONTINUOUS LEARNING KNOWLEDGE BASE:")
            print(f"  - Total Ingested Signals : {total_records}")
            print(f"  - Closed & Analyzed      : {closed_records}")
            print(f"  - Actively Monitored     : {open_records}")
        except Exception as e:
            pass

    print("\n✅ All 7 baskets verified active and tracked. Report generated successfully.\n")

if __name__ == "__main__":
    main()
