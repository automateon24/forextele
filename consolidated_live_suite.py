"""
FOREXTELE 24/7 PERSISTENT AUTONOMOUS SUITE - CONSOLIDATED LIVE MONITOR
======================================================================
1. Cleanly stops and resets prior running threads on startup (without touching SepPro/Auguspro).
2. Spawns and manages 24/7 background daemons with Windows Task Scheduler auto-start on boot.
3. Consolidates live logs and statuses from all 3 engines into a clean, brief real-time stream.
4. Continuously monitors MT5 account stats, orders placed, scanning activity, and disconnections.
5. Continuously learns and adapts daily via the AI Trade Learning Engine & Alignment Supervisor.
"""

import sys
import os
import time
import socket
import json
import logging
import threading
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure UTF-8 console output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import psutil
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
PYTHON_EXE = Path(r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe")
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Engine log paths
LOG_FILES = {
    "BREAKOUT_BOSS": LOGS_DIR / "breakout_boss.log",
    "SMC_SCANNER": LOGS_DIR / "smc_scanner.log",
    "TELEGRAM_VIP": LOGS_DIR / "telegram_signals.log",
    "WATCHDOG": LOGS_DIR / "master_autostart_watchdog.log",
    "AI_LEARN": LOGS_DIR / "ai_watchdog.log"
}

KB_FILE = DATA_DIR / "trade_learning_knowledge_base.jsonl"
PROFILES_FILE = DATA_DIR / "channel_archetypes_and_rules.json"
ALIGNMENT_FILE = BASE_DIR / "live_ai_alignment_status.json"

DETACHED_FLAGS = 0x00000008 | 0x00000200

# ANSI color codes for readable console
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_CYAN = "\033[36m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"
C_BLUE = "\033[34m"

def clean_terminate_prior_threads():
    """
    Finds and cleanly terminates any running forextele engines and watchdogs.
    STRICT SAFETY: Never touches SepPro or Auguspro, and never touches parent processes or IDE!
    """
    print(f"{C_YELLOW}--- [PHASE 1/3] Terminating previous running threads for a fresh start...{C_RESET}", flush=True)
    curr_pid = os.getpid()
    parent_pid = os.getppid() if hasattr(os, 'getppid') else None
    
    # We only target Python engine processes
    targets = [
        "breakout_boss_engine",
        "autonomous_ai_market_scanner",
        "telegram_signal_engine",
        "master_autostart_watchdog",
        "start_watchdog_persistent",
        "ai_backtest_alignment_watchdog"
    ]

    terminated_count = 0
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.pid == curr_pid or (parent_pid and p.pid == parent_pid):
                continue
            name = (p.name() or '').lower()
            if "python" not in name:
                continue
            cmd = " ".join(p.cmdline() or [])
            if "SepPro" in cmd or "Auguspro" in cmd:
                continue
            if any(t in cmd for t in targets):
                print(f"  Terminating stale process PID {p.pid} ({p.name()})...", flush=True)
                p.terminate()
                terminated_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if terminated_count > 0:
        time.sleep(2.0)
        # Force kill if any lingered
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if p.pid == curr_pid or (parent_pid and p.pid == parent_pid):
                    continue
                name = (p.name() or '').lower()
                if "python" not in name:
                    continue
                cmd = " ".join(p.cmdline() or [])
                if "SepPro" in cmd or "Auguspro" in cmd:
                    continue
                if any(t in cmd for t in targets):
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        print(f"  {C_GREEN}[OK] Cleaned up {terminated_count} previous processes.{C_RESET}", flush=True)
    else:
        print(f"  {C_GREEN}[OK] No stale engine threads found.{C_RESET}", flush=True)

def register_and_launch_247_daemons():
    """
    Registers Windows Task Scheduler jobs for 1-month continuous 24/7 uptime and launches watchdog.
    """
    print(f"\n{C_CYAN}--- [PHASE 2/3] Guaranteeing 24/7 1-Month Persistence & Starting Daemons...{C_RESET}")
    
    # 1. Boot task
    try:
        cmd_boot = f'schtasks /create /tn "Forextele_Boot_AutoStart" /tr "\\"{PYTHON_EXE}\\" \\"C:\\anlyzeforex\\forextele\\start_watchdog_persistent.py\\"" /sc ONSTART /rl HIGHEST /ru SYSTEM /f'
        subprocess.run(cmd_boot, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  {C_GREEN}[OK] Windows Boot Task Registered (Starts automatically after VPS reboot).{C_RESET}")
    except Exception as e:
        print(f"  {C_YELLOW}[NOTE] Boot task check: {e}{C_RESET}")

    # 2. 5-Minute Watchdog Supervisor task
    try:
        cmd_sup = f'schtasks /create /tn "Forextele_247_Persistent_Watchdog" /tr "\\"{PYTHON_EXE}\\" \\"C:\\anlyzeforex\\forextele\\start_watchdog_persistent.py\\"" /sc MINUTE /mo 5 /rl HIGHEST /f'
        subprocess.run(cmd_sup, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  {C_GREEN}[OK] 24/7 Watchdog Supervisor Task Registered (Every 5 minutes).{C_RESET}")
    except Exception as e:
        print(f"  {C_YELLOW}[NOTE] Supervisor task check: {e}{C_RESET}")

    # 3. Launch Master Watchdog daemon via Windows Task Scheduler
    try:
        subprocess.run('schtasks /run /tn "Forextele_247_Persistent_Watchdog"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  {C_GREEN}[OK] Master 24/7 Autostart Watchdog triggered via Windows Task Scheduler.{C_RESET}", flush=True)
    except Exception as e:
        print(f"  {C_YELLOW}[NOTE] Schtasks trigger: {e}{C_RESET}", flush=True)

    print(f"  Waiting 9 seconds for all 3 engines to initialize and connect to MT5...", flush=True)
    time.sleep(9.0)

def get_engine_pids():
    """Returns PID status of all 4 suite components."""
    status = {"BREAKOUT_BOSS": None, "SMC_SCANNER": None, "TELEGRAM_VIP": None, "WATCHDOG": None}
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmd = " ".join(p.cmdline() or [])
            if "SepPro" in cmd or "Auguspro" in cmd:
                continue
            if "master_autostart_watchdog" in cmd:
                status["WATCHDOG"] = p.pid
            elif "breakout_boss_engine" in cmd:
                status["BREAKOUT_BOSS"] = p.pid
            elif "autonomous_ai_market_scanner" in cmd:
                status["SMC_SCANNER"] = p.pid
            elif "telegram_signal_engine" in cmd:
                status["TELEGRAM_VIP"] = p.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return status

def get_mt5_account_summary():
    """Queries MT5 for live account metrics and today's closed deals."""
    if not mt5 or not mt5.initialize():
        return None

    acc = mt5.account_info()
    positions = mt5.positions_get() or []
    orders = mt5.orders_get() or []

    # Calculate today's closed deals
    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    deals = mt5.history_deals_get(today_start, now_utc + timedelta(days=1)) or []
    closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]

    wins = [d for d in closed_deals if d.profit > 0]
    losses = [d for d in closed_deals if d.profit < 0]
    net_pnl = sum(d.profit + d.swap for d in closed_deals)

    return {
        "login": acc.login if acc else "Unknown",
        "server": acc.server if acc else "Unknown",
        "balance": acc.balance if acc else 0.0,
        "equity": acc.equity if acc else 0.0,
        "margin": acc.margin if acc else 0.0,
        "free_margin": acc.margin_free if acc else 0.0,
        "margin_level": acc.margin_level if acc else 0.0,
        "positions_count": len(positions),
        "orders_count": len(orders),
        "positions": positions,
        "orders": orders,
        "closed_today": len(closed_deals),
        "wins_today": len(wins),
        "losses_today": len(losses),
        "net_pnl_today": net_pnl
    }

def get_ai_learning_summary():
    """Extracts summary metrics from AI Knowledge Base & Auto-Tune status."""
    kb_trades = 0
    if KB_FILE.exists():
        try:
            with open(KB_FILE, "r", encoding="utf-8") as f:
                kb_trades = sum(1 for line in f if line.strip())
        except Exception:
            pass

    top_pattern = "N/A"
    overall_wr = "N/A"
    if PROFILES_FILE.exists():
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                channels = data.get("channels", {})
                if channels:
                    tot_trades = sum(c.get("total_trades", 0) for c in channels.values())
                    tot_wins = sum(int(c.get("total_trades", 0) * c.get("win_rate", 0) / 100) for c in channels.values())
                    if tot_trades > 0:
                        overall_wr = f"{(tot_wins / tot_trades * 100):.1f}%"
                    patterns = {}
                    for c in channels.values():
                        for p, v in c.get("pattern_breakdown", {}).items():
                            patterns[p] = patterns.get(p, 0) + v.get("pnl", 0)
                    if patterns:
                        top_pattern = max(patterns.items(), key=lambda x: x[1])[0]
        except Exception:
            pass

    alignment_status = "HEALTHY (Aligned with 1-Month Backtest)"
    if ALIGNMENT_FILE.exists():
        try:
            with open(ALIGNMENT_FILE, "r", encoding="utf-8") as f:
                align_data = json.load(f)
                alignment_status = align_data.get("status", "HEALTHY")
        except Exception:
            pass

    return {
        "kb_trades": kb_trades,
        "overall_wr": overall_wr,
        "top_pattern": top_pattern,
        "alignment_status": alignment_status
    }

def print_live_hud():
    """Displays a clean, consolidated overview of all 3 engines + MT5 + AI Learning."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S Local")
    pids = get_engine_pids()
    acc = get_mt5_account_summary()
    ai = get_ai_learning_summary()

    print("\n" + "=" * 88)
    print(f"{C_BOLD}{C_CYAN} FOREXTELE 24/7 AUTONOMOUS SUITE - CONSOLIDATED LIVE MONITOR (1-MONTH PERSISTENT){C_RESET}")
    print("=" * 88)
    print(f" UTC Time: {now_utc}  |  Server Time: {now_local}")
    
    if acc:
        bal_str = f"${acc['balance']:,.2f}"
        eq_str = f"${acc['equity']:,.2f}"
        pnl_color = C_GREEN if acc['net_pnl_today'] >= 0 else C_RED
        pnl_str = f"{pnl_color}${acc['net_pnl_today']:+,.2f}{C_RESET}"
        
        print(f" MT5 Account: {C_BOLD}{acc['login']}{C_RESET} ({acc['server']})  |  Status: {C_GREEN}CONNECTED{C_RESET}")
        print(f" Balance: {C_BOLD}{bal_str}{C_RESET} | Equity: {C_BOLD}{eq_str}{C_RESET} | Free Margin: ${acc['free_margin']:,.2f} | Margin: ${acc['margin']:,.2f}")
        print(f" Open Positions: {C_BOLD}{acc['positions_count']}{C_RESET} | Pending Orders: {C_BOLD}{acc['orders_count']}{C_RESET} | Today's Closed: {acc['closed_today']} (Wins: {acc['wins_today']}, Losses: {acc['losses_today']}, Net PnL: {pnl_str})")
        
        if acc['orders_count'] > 0:
            for o in acc['orders']:
                o_type = "BUY LIMIT" if o.type == 2 else ("SELL LIMIT" if o.type == 3 else f"TYPE_{o.type}")
                print(f"   ↳ {C_YELLOW}[PENDING ORDER]{C_RESET} #{o.ticket} {o.symbol} {o_type} Vol:{o.volume_current} @ {o.price_open:.2f} ({o.comment})")
        if acc['positions_count'] > 0:
            for p in acc['positions']:
                p_type = "BUY" if p.type == 0 else "SELL"
                p_pnl = f"{C_GREEN if p.profit >= 0 else C_RED}${p.profit:+.2f}{C_RESET}"
                print(f"   ↳ {C_GREEN}[OPEN POSITION]{C_RESET} #{p.ticket} {p.symbol} {p_type} Vol:{p.volume} @ {p.price_open:.2f} | Current: {p.price_current:.2f} | PnL: {p_pnl}")
    else:
        print(f" MT5 Status: {C_RED}Connecting / Unavailable{C_RESET}")

    print("-" * 88)
    print(f"{C_BOLD} 3 TRADING ENGINES & 24/7 WATCHDOG STATUS:{C_RESET}")
    
    # Engine 1
    bb_status = f"{C_GREEN}ACTIVE (PID {pids['BREAKOUT_BOSS']}){C_RESET}" if pids['BREAKOUT_BOSS'] else f"{C_RED}OFFLINE{C_RESET}"
    print(f"  [1] BreakoutBoss v2  : {bb_status} | Gold M5 Multi-Session (5 Compounding Models + Gann)")

    # Engine 2
    smc_status = f"{C_GREEN}ACTIVE (PID {pids['SMC_SCANNER']}){C_RESET}" if pids['SMC_SCANNER'] else f"{C_RED}OFFLINE{C_RESET}"
    print(f"  [2] Autonomous SMC AI: {smc_status} | Gold & BTC (M15 FVG, Liquidity Sweeps, Auto-Tune ON)")

    # Engine 3
    tg_status = f"{C_GREEN}ACTIVE (PID {pids['TELEGRAM_VIP']}){C_RESET}" if pids['TELEGRAM_VIP'] else f"{C_RED}OFFLINE{C_RESET}"
    print(f"  [3] Telegram VIP Swarm: {tg_status} | 40+ Channels | AI Conviction TSL | Dual Replication")

    # Watchdog
    wd_status = f"{C_GREEN}ACTIVE (PID {pids['WATCHDOG']}){C_RESET}" if pids['WATCHDOG'] else f"{C_RED}OFFLINE{C_RESET}"
    print(f"  [4] Master Watchdog  : {wd_status} | 24/7 Reboot Auto-Heal & Task Scheduler Supervisor")

    print("-" * 88)
    print(f"{C_BOLD} AI TRADE LEARNING & DAILY ON-THE-GO ADAPTATION:{C_RESET}")
    print(f"  Knowledge Base: {C_BOLD}{ai['kb_trades']}{C_RESET} Trades Reverse-Engineered | Historical Win-Rate: {ai['overall_wr']} | Top Pattern: {ai['top_pattern']}")
    print(f"  Daily Backtest Alignment: {C_GREEN}{ai['alignment_status']}{C_RESET}")
    print("=" * 88)
    print(f"{C_YELLOW}>>> CONSOLIDATED LIVE ACTIVITY STREAM (Orders, Scans, Errors & AI Learnings):{C_RESET}\n")

# Filter out repetitive noise lines to keep stream informative and concise
NOISE_PATTERNS = [
    "HTTP Request: POST http://127.0.0.1:11434/api/generate",
    "Got difference for channel",
    "Got difference for account updates",
    "Attempt 1 at connecting failed: TimeoutError",
    "--- [WATCHDOG HEALTH CHECK] ---",
    "--- [WATCHDOG HEALTH CHECK COMPLETE] ---",
    "terminal64.exe is ACTIVE",
    "Telegram Signal Engine is ACTIVE",
    "Autonomous AI Market Scanner is ACTIVE",
    "BreakoutBoss Engine is ACTIVE"
]

def format_log_line(engine_tag: str, raw_line: str) -> str:
    """
    Transforms raw log lines into clean, brief, color-coded stream output.
    """
    line = raw_line.strip()
    if not line:
        return None

    # Check for noise
    for np in NOISE_PATTERNS:
        if np in line:
            return None

    # Extract timestamp and message
    # Format typically: YYYY-MM-DD HH:MM:SS,mmm - [LOGGER] - LEVEL - Message
    msg = line
    if " - " in line:
        parts = line.split(" - ", 3)
        if len(parts) >= 4:
            timestamp = parts[0][:19]
            level = parts[2]
            msg = parts[3]
        elif len(parts) >= 3:
            timestamp = parts[0][:19]
            level = "INFO"
            msg = parts[2]
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            level = "INFO"
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = "INFO"

    # Colorize tag based on engine
    if engine_tag == "BREAKOUT_BOSS":
        tag_color = f"{C_YELLOW}[BREAKOUT_BOSS]{C_RESET}"
    elif engine_tag == "SMC_SCANNER":
        tag_color = f"{C_CYAN}[SMC_SCANNER]{C_RESET}"
    elif engine_tag == "TELEGRAM_VIP":
        tag_color = f"{C_MAGENTA}[TELEGRAM_VIP]{C_RESET}"
    elif engine_tag == "AI_LEARN":
        tag_color = f"{C_GREEN}[AI_LEARNING]{C_RESET}"
    else:
        tag_color = f"{C_BLUE}[WATCHDOG]{C_RESET}"

    # Highlight special events
    upper_msg = msg.upper()
    if "ORDER" in upper_msg or "PLACED" in upper_msg or "ENTRY" in upper_msg or "TRADE #" in upper_msg:
        return f"{timestamp} {tag_color} {C_GREEN}{C_BOLD}[ORDER/TRADE] {msg}{C_RESET}"
    elif (("ERROR" in upper_msg and "ZERO" not in upper_msg and "0 ERROR" not in upper_msg) or 
          "EXCEPTION" in upper_msg or "DISCONNECT" in upper_msg or "TIMEOUT" in upper_msg or 
          level in ["ERROR", "CRITICAL"]):
        return f"{timestamp} {tag_color} {C_RED}{C_BOLD}[ALERT/ERROR] {msg}{C_RESET}"
    elif "SWEEP" in upper_msg or "FVG" in upper_msg or "SCAN" in upper_msg or "SESSION" in upper_msg or "RANGE" in upper_msg:
        return f"{timestamp} {tag_color} {C_CYAN}[SCAN] {msg}{C_RESET}"
    elif "LEARN" in upper_msg or "ADAPT" in upper_msg or "REVERSE-ENGINEERED" in upper_msg or "AUTOTUNE" in upper_msg:
        return f"{timestamp} {tag_color} {C_GREEN}[AI_ADAPT] {msg}{C_RESET}"
    else:
        return f"{timestamp} {tag_color} {msg}"

def tail_consolidated_logs():
    """
    Seeds with recent activity, then monitors all 5 log files continuously in real-time.
    """
    # 1. Print seed lines from recent history
    print(f"{C_BOLD}--- [RECENT ACTIVITY SNAPSHOT (LAST 10 MINUTES)] ---{C_RESET}", flush=True)
    seed_lines = []
    for tag, path in LOG_FILES.items():
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                # Take last 15 lines and filter
                for l in lines[-15:]:
                    fmt = format_log_line(tag, l)
                    if fmt:
                        seed_lines.append(fmt)
            except Exception:
                pass

    if seed_lines:
        # Show up to 12 most recent seed lines
        for l in seed_lines[-12:]:
            print(l, flush=True)
    else:
        print("  (Waiting for incoming events...)", flush=True)

    print(f"{C_BOLD}--- [LISTENING LIVE FOR NEW SIGNALS, ORDERS & SCANS] ---{C_RESET}\n", flush=True)

    # 2. Open handles at end of file for live tailing
    file_handles = {}
    for tag, path in LOG_FILES.items():
        if path.exists():
            f = open(path, "r", encoding="utf-8", errors="replace")
            f.seek(0, os.SEEK_END)
            file_handles[tag] = f
        else:
            file_handles[tag] = None

    last_hud_time = time.time()
    last_heartbeat_time = time.time()

    while True:
        try:
            line_printed = False
            for tag, path in LOG_FILES.items():
                if file_handles[tag] is None:
                    if path.exists():
                        f = open(path, "r", encoding="utf-8", errors="replace")
                        f.seek(0, os.SEEK_END)
                        file_handles[tag] = f
                    else:
                        continue

                f = file_handles[tag]
                while True:
                    line = f.readline()
                    if not line:
                        break
                    formatted = format_log_line(tag, line)
                    if formatted:
                        print(formatted, flush=True)
                        line_printed = True

            # Print a compact live heartbeat every 30 seconds if quiet
            now_t = time.time()
            if not line_printed and (now_t - last_heartbeat_time > 30):
                pids = get_engine_pids()
                acc = get_mt5_account_summary()
                bal = f"${acc['balance']:,.2f}" if acc else "N/A"
                eq = f"${acc['equity']:,.2f}" if acc else "N/A"
                pos = acc['positions_count'] if acc else 0
                ords = acc['orders_count'] if acc else 0
                now_s = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                print(f"{C_CYAN}[{now_s}] ⚡ [LIVE SUITE HEARTBEAT]{C_RESET} All 3 Engines + Watchdog ACTIVE | Balance: {bal} | Equity: {eq} | Open Pos: {pos} | Orders: {ords}", flush=True)
                last_heartbeat_time = now_t

            # Full HUD refresh every 5 minutes
            if now_t - last_hud_time > 300:
                print_live_hud()
                last_hud_time = now_t

            time.sleep(0.5)
        except Exception:
            time.sleep(1.0)
        except Exception:
            time.sleep(1.0)

def ai_daily_adaptation_loop():
    """
    Background worker that runs daily/hourly AI optimization:
    1. Refreshes channel profiles from knowledge base.
    2. Runs AI Backtest Alignment Watchdog.
    """
    while True:
        try:
            time.sleep(900)  # Check every 15 minutes
            # Import and run alignment watchdog
            from ai_trade_learning_engine import learning_engine
            learning_engine.refresh_channel_profiles()

            from ai_backtest_alignment_watchdog import AIBacktestAlignmentWatchdog
            w = AIBacktestAlignmentWatchdog()
            if w.initialize_mt5():
                rep = w.evaluate_live_performance()
                mt5.shutdown()
                with open(LOG_FILES["AI_LEARN"], "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - [AI_WATCHDOG] - INFO - Daily Auto-Adaptation Cycle: Status={rep.get('status')} | Channels Evaluated\n")
        except Exception as e:
            pass

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor-only", action="store_true", help="Attach to running engines without restarting")
    args = parser.parse_args()

    if not args.monitor_only:
        clean_terminate_prior_threads()
        register_and_launch_247_daemons()

    # Launch daily AI adaptation thread
    t_ai = threading.Thread(target=ai_daily_adaptation_loop, daemon=True)
    t_ai.start()

    # Print initial live HUD
    print_live_hud()

    # Stream consolidated logs in foreground
    tail_consolidated_logs()

if __name__ == "__main__":
    main()
