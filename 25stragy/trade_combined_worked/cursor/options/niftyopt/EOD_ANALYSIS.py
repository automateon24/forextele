import sys
import os
import csv
from datetime import datetime
from collections import defaultdict

def load_trades(dt):
    """Load from modular_trades + v3_trades, deduplicate by trade_id."""
    rows = []
    seen = set()
    for prefix in ["modular_trades", "v3_trades"]:
        path = f"daily_data/{prefix}_{dt}.csv"
        if not os.path.exists(path):
            continue
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = row.get("trade_id", "")
                event = row.get("event", "")
                key = f"{tid}_{event}"
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
    return rows

def analyze(dt):
    rows = load_trades(dt)
    if not rows:
        print(f"  No trade files found for {dt}")
        return

    # Build completed trades: match ENTER → EXIT by trade_id (skip ORPHAN)
    enters = {}
    exits  = {}
    for r in rows:
        tid = r["trade_id"]
        if r["event"] == "ENTER":
            enters[tid] = r
        elif r["event"] == "EXIT" and r.get("exit_reason","") != "EOD_ORPHAN_CLOSE":
            exits[tid] = r

    completed = []
    for tid, ex in exits.items():
        en = enters.get(tid)
        if en:
            completed.append({"enter": en, "exit": ex})

    # ── OVERALL SUMMARY ────────────────────────────────────────────────────
    total_pnl   = sum(float(t["exit"].get("pnl") or 0) for t in completed)
    wins        = [t for t in completed if float(t["exit"].get("pnl") or 0) > 0]
    losses      = [t for t in completed if float(t["exit"].get("pnl") or 0) < 0]
    total_trades = len(completed)
    win_rate    = (len(wins) / total_trades * 100) if total_trades else 0

    status = "PROFIT" if total_pnl >= 0 else "LOSS"
    color_line = "=" * 80

    print()
    print(color_line)
    print(f"  OVERALL RESULT : {status}")
    print(f"  TOTAL NET P&L  : Rs {total_pnl:+,.2f}")
    print(f"  TOTAL TRADES   : {total_trades}  |  WINS: {len(wins)}  LOSSES: {len(losses)}  WIN RATE: {win_rate:.0f}%")
    print(f"  BEST TRADE     : Rs {max((float(t['exit'].get('pnl') or 0) for t in completed), default=0):+,.2f}")
    print(f"  WORST TRADE    : Rs {min((float(t['exit'].get('pnl') or 0) for t in completed), default=0):+,.2f}")
    print(color_line)

    # ── STRATEGY BREAKDOWN ─────────────────────────────────────────────────
    print()
    print("  STRATEGY BREAKDOWN")

    by_strategy = defaultdict(list)
    for t in completed:
        by_strategy[t["enter"]["strategy"]].append(t)

    strategy_totals = []
    for strat, trades in by_strategy.items():
        spnl  = sum(float(t["exit"].get("pnl") or 0) for t in trades)
        swins = sum(1 for t in trades if float(t["exit"].get("pnl") or 0) > 0)
        dirs  = set(t["enter"]["direction"] for t in trades)
        strategy_totals.append((strat, trades, spnl, swins, dirs))

    strategy_totals.sort(key=lambda x: x[2], reverse=True)

    print(f"  {'Strategy':<30} {'Dir':<5} {'Tr':>3} {'W':>3} {'WR%':>5} {'AvgEntry':>9} {'AvgExit':>8} {'P&L':>12}  Result")
    print("  " + "-" * 90)
    for strat, trades, spnl, swins, dirs in strategy_totals:
        reasons = ", ".join(set(t["exit"].get("exit_reason","?") for t in trades))
        dir_str = "/".join(dirs)
        wr = (swins / len(trades) * 100) if trades else 0
        avg_entry = sum(float(t["enter"].get("entry") or 0) for t in trades) / len(trades)
        avg_exit  = sum(float(t["exit"].get("exit") or 0) for t in trades) / len(trades)
        flag = "PROFIT" if spnl > 0 else "LOSS"
        print(f"  {strat:<30} {dir_str:<5} {len(trades):>3} {swins:>3} {wr:>4.0f}%  {avg_entry:>9.2f} {avg_exit:>8.2f} {spnl:>+12,.2f}  {flag} ({reasons})")

    # ── TRADE-BY-TRADE DETAIL ──────────────────────────────────────────────
    print()
    print("  TRADE-BY-TRADE DETAIL")
    print(f"  {'Time':<8} {'Strategy':<28} {'Dir':<3} {'Strike':>7} {'Entry':>7} {'Exit':>7} {'Premium%':>8} {'P&L':>10}  Result")
    print("  " + "-" * 95)

    for t in sorted(completed, key=lambda x: x["enter"]["timestamp"]):
        en     = t["enter"]
        ex     = t["exit"]
        time_s = en["timestamp"][11:19]
        strat  = en["strategy"][:27]
        dirn   = en["direction"]
        strike = en["strike"]
        entry  = float(en["entry"] or 0)
        exit_p = float(ex.get("exit") or 0)
        pnl    = float(ex.get("pnl") or 0)
        reason = ex.get("exit_reason", "?")
        # Premium move %
        pct = ((exit_p - entry) / entry * 100) if entry else 0
        sign = "W" if pnl > 0 else "L"
        print(f"  {time_s:<8} {strat:<28} {dirn:<3} {strike:>7} {entry:>7.2f} {exit_p:>7.2f} {pct:>+7.1f}%  {pnl:>+10,.2f}  {sign} {reason}")

    # ── DATA FOR NEXT PROGRAM ─────────────────────────────────────────────
    print()
    print("  DATA FOR NEXT PROGRAM / STRATEGY TUNING")
    print("  " + "-" * 76)
    print(f"  {'Strategy':<30} {'Dir':<3} {'Strike':>7} {'Entry':>7} {'Exit':>7} {'SL':>7} {'Target':>8} {'Conf':>6}")
    print("  " + "-" * 76)
    for t in sorted(completed, key=lambda x: x["enter"]["timestamp"]):
        en     = t["enter"]
        ex     = t["exit"]
        strat  = en["strategy"][:29]
        dirn   = en["direction"]
        strike = en["strike"]
        entry  = float(en["entry"] or 0)
        exit_p = float(ex.get("exit") or 0)
        sl     = float(en.get("sl") or 0)
        target = float(en.get("target") or 0)
        conf   = en.get("confidence","?")
        pnl    = float(ex.get("pnl") or 0)
        flag   = "+" if pnl > 0 else "X"
        print(f"  {flag} {strat:<29} {dirn:<3} {strike:>7} {entry:>7.2f} {exit_p:>7.2f} {sl:>7.2f} {target:>8.2f} {conf:>6}")

    # ── WINNING PATTERNS (for learning) ───────────────────────────────────
    if wins:
        print()
        print("  WINNING PATTERNS — USE THESE TOMORROW")
        print("  " + "-" * 76)
        for t in wins:
            en    = t["enter"]
            ex    = t["exit"]
            entry = float(en["entry"] or 0)
            exit_p= float(ex.get("exit") or 0)
            pnl   = float(ex.get("pnl") or 0)
            move  = ((exit_p - entry) / entry * 100) if entry else 0
            print(f"  Strategy : {en['strategy']}")
            print(f"  Direction: {en['direction']}  Strike: {en['strike']}  Entry Premium: {entry:.2f}  Exit: {exit_p:.2f}  Move: {move:+.1f}%")
            print(f"  Reason   : {en.get('reason','')}")
            print(f"  P&L      : Rs {pnl:+,.2f}")
            print()

    # ── LOSING PATTERNS (avoid tomorrow) ──────────────────────────────────
    if losses:
        print()
        print("  LOSING PATTERNS — AVOID TOMORROW")
        print("  " + "-" * 76)
        for t in losses:
            en    = t["enter"]
            ex    = t["exit"]
            entry = float(en["entry"] or 0)
            exit_p= float(ex.get("exit") or 0)
            pnl   = float(ex.get("pnl") or 0)
            print(f"  Strategy : {en['strategy']}")
            print(f"  Direction: {en['direction']}  Strike: {en['strike']}  Entry Premium: {entry:.2f}  Exit: {exit_p:.2f}")
            print(f"  Reason   : {en.get('reason','')}")
            print(f"  P&L      : Rs {pnl:+,.2f}  (stopped at {ex.get('exit_reason','')})")
            print()

    print()

if __name__ == "__main__":
    dt = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    analyze(dt)
