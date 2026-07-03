import os
import sys
import json
import math
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

sys.path.append(r'C:\cursor\options\niftyopt')
sys.path.append(r'C:\cursor\options\niftyopt\Lib\site-packages')
from dhanhq import dhanhq

# Configuration Paths
CONFIG_PATH = r"C:\25stragy\config_hybrid_aggressive.json"
STRATEGY_DNA_PATH = r"C:\25stragy\strategy_dna.json"
TRADES_CSV_PATH = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
LOG_PATH = r"C:\cursor\options\niftyopt\data\live_portfolio_trader.log"
TOKEN_FILE = r"C:\cursor\options\niftyopt\config\dhan_tokens.json"
CLIENT_ID = "1101936133"

# Load initial config
import logging
DASHBOARD_LOG_FILE = r"C:\cursor\options\niftyopt\data\dashboard_server.log"
os.makedirs(os.path.dirname(DASHBOARD_LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(DASHBOARD_LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DashboardServer")

with open(CONFIG_PATH, "r") as f:
    config_db = json.load(f)

CAPITAL_BASE = config_db["system"].get("capital_base", 500000)
CAPITAL_PER_INDEX = config_db["system"].get("capital_per_index", 100000)

# Initialize Dhan Client via GlobalDataFetcher
sys.path.append(r'C:\cursor\options\niftyopt\united_Indian_market1.0')
from global_data_fetcher import get_global_data_fetcher
fetcher = get_global_data_fetcher()
client = fetcher.client
logger.info("Centralized Dhan API fetcher integrated with the dashboard.")

# Start fetcher if not already running (runs only if dashboard is run independently)
if not fetcher.running:
    try:
        fetcher.perform_data_warmup()
        fetcher.start()
        logger.info("Background GlobalDataFetcher threads started for dashboard.")
    except Exception as e:
        logger.warning(f"Could not initialize GlobalDataFetcher background loops: {e}")

app = FastAPI(title="Live Trading Portfolio Dashboard")

# Caching layer for index spot prices to prevent rate limit blocks
LAST_SPOT_PRICES = {
    'NIFTY': 23622.90,
    'BANKNIFTY': 56814.80,
    'FINNIFTY': 25943.35,
    'MIDCPNIFTY': 14245.60,
    'SENSEX': 75527.95,
    'VIX': 14.72
}
LAST_OPTION_PRICES = {}
dhan_connected = True

# Helper function to parse V3 and V4 modular trades CSV format
def load_modular_trades(csv_path: str, fetcher_inst, cfg_db):
    active_list = []
    completed_list = []
    if not csv_path or not os.path.exists(csv_path):
        return active_list, completed_list
        
    trades_map = {}
    try:
        df = pd.read_csv(csv_path)
        df = df.where(pd.notnull(df), None)
        
        # Determine lot size for NIFTY
        lot_size = int(cfg_db['index_profiles'].get('NIFTY', {}).get('lot_size', 75))
        
        for _, row in df.iterrows():
            tid = row.get('trade_id')
            if not tid:
                continue
                
            event = row.get('event')
            strike = row.get('strike')
            if strike is not None:
                strike = float(strike)
            direction = str(row.get('direction') or 'CE').upper()
            
            entry_px = row.get('entry')
            if entry_px is not None:
                entry_px = float(entry_px)
            else:
                entry_px = 0.0
                
            exit_px = row.get('exit')
            if exit_px is not None and exit_px != '' and str(exit_px).strip() != '':
                exit_px = float(exit_px)
            else:
                exit_px = None
                
            pnl = row.get('pnl')
            if pnl is not None and pnl != '' and str(pnl).strip() != '':
                pnl = float(pnl)
            else:
                pnl = None
                
            unreal = row.get('unreal_pnl')
            if unreal is not None and unreal != '' and str(unreal).strip() != '':
                unreal = float(unreal)
            else:
                unreal = 0.0
                
            if tid not in trades_map:
                trades_map[tid] = {
                    'index': 'NIFTY',
                    'strategy': row.get('strategy') or row.get('module') or 'Unknown',
                    'direction': direction,
                    'strike': strike,
                    'option_name': f"NIFTY {direction} {int(strike) if strike else 0}",
                    'lots': 1,
                    'entry_time': row.get('timestamp'),
                    'entry_price': entry_px,
                    'entry_spot': 0.0,
                    'highest_premium': entry_px,
                    'spot_sl_level': float(row.get('sl') or 0.0),
                    'exit_price': exit_px,
                    'exit_time': None,
                    'exit_reason': row.get('exit_reason'),
                    'pnl_rs': pnl,
                    'status': 'OPEN' if event == 'ENTER' else 'CLOSED',
                    'regime': 'NORMAL',
                    'option_security_id': None,
                    'unrealized_pnl': unreal,
                    'current_price': entry_px,
                    'greeks': {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0, 'iv': 0.0}
                }
            else:
                if event == 'EXIT':
                    trades_map[tid]['status'] = 'CLOSED'
                    trades_map[tid]['exit_price'] = exit_px if exit_px is not None else trades_map[tid]['exit_price']
                    trades_map[tid]['exit_time'] = row.get('timestamp')
                    trades_map[tid]['exit_reason'] = row.get('exit_reason') or trades_map[tid]['exit_reason']
                    trades_map[tid]['pnl_rs'] = pnl if pnl is not None else trades_map[tid]['pnl_rs']
                elif event == 'UPDATE':
                    trades_map[tid]['unrealized_pnl'] = unreal
                    
        # Update live data for open trades
        md = fetcher_inst.get_market_data('NIFTY')
        spot = md.spot
        
        for tid, t in trades_map.items():
            if t['status'] == 'OPEN':
                direction = t['direction']
                strike = t['strike']
                entry_px = t['entry_price']
                lots = t['lots']
                
                current_ltp = entry_px
                # Lookup contract in NIFTY chain
                if md.chain and strike in md.chain and direction in md.chain[strike]:
                    contract = md.chain[strike][direction]
                    current_ltp = contract.get('ltp', entry_px)
                    
                t['current_price'] = current_ltp
                t_pnl = (current_ltp - entry_px) * lot_size * lots
                t['unrealized_pnl'] = round(t_pnl, 2)
                
                # Calculate greeks
                days_to_expiry = 4.0
                t['greeks'] = calculate_greeks(spot or entry_px * 100, strike or 1.0, days_to_expiry, direction == 'CE')
                
            if t['status'] == 'OPEN':
                active_list.append(t)
            else:
                # If exit price and entry price are set and pnl is None, calculate pnl
                if t['pnl_rs'] is None and t['exit_price'] is not None:
                    t['pnl_rs'] = round((t['exit_price'] - t['entry_price']) * lot_size * t['lots'], 2)
                completed_list.append(t)
                
    except Exception as e:
        logger.error(f"Error parsing modular trades CSV {csv_path}: {e}")
        
    return active_list, completed_list

# ─────────────────────────────────────────────────────────────────────────────
# GREEKS CALCULATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def normal_cdf(x: float) -> float:
    """Cumulative standard normal distribution function (numerical approximation)."""
    if x < -6.0: return 0.0
    if x > 6.0: return 1.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989422804 * math.exp(-x * x / 2.0)
    p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - p if x > 0 else p

def normal_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)

def calculate_greeks(spot: float, strike: float, days_to_expiry: float, is_call: bool, iv: float = 0.20, r: float = 0.07):
    """Calculate option Greeks using Black-Scholes model."""
    t = max(0.0001, days_to_expiry / 365.0)
    sigma = max(0.01, iv)
    
    try:
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        
        # Delta
        delta = normal_cdf(d1) if is_call else (normal_cdf(d1) - 1.0)
        
        # Gamma
        gamma = normal_pdf(d1) / (spot * sigma * math.sqrt(t))
        
        # Vega (per 1% volatility change)
        vega = (spot * math.sqrt(t) * normal_pdf(d1)) / 100.0
        
        # Theta (per day change)
        term1 = -(spot * normal_pdf(d1) * sigma) / (2.0 * math.sqrt(t))
        if is_call:
            term2 = -r * strike * math.exp(-r * t) * normal_cdf(d2)
            theta = (term1 + term2) / 365.0
        else:
            term2 = r * strike * math.exp(-r * t) * normal_cdf(-d2)
            theta = (term1 + term2) / 365.0
            
        return {
            "delta": round(delta, 3),
            "gamma": round(gamma, 5),
            "vega": round(vega, 3),
            "theta": round(theta, 3),
            "iv": round(sigma * 100, 1)
        }
    except Exception:
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "iv": 0.0}

# ─────────────────────────────────────────────────────────────────────────────
# DATA RETRIEVAL SERVICE
# ─────────────────────────────────────────────────────────────────────────────
def get_days_between(date_str: str) -> float:
    """Calculate fractional days to expiry from a YYYY-MM-DD string."""
    try:
        exp = datetime.strptime(date_str, "%Y-%m-%d")
        now = datetime.now()
        diff = (exp - now).total_seconds() / 86400.0
        return max(0.0, diff)
    except Exception:
        return 5.0 # fallback

def load_trades_from_csv():
    active_list = []
    completed_list = []
    
    if not os.path.exists(TRADES_CSV_PATH):
        return active_list, completed_list
        
    try:
        df = pd.read_csv(TRADES_CSV_PATH)
        df = df.where(pd.notnull(df), None)
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        for _, row in df.iterrows():
            trade_dict = row.to_dict()
            entry_time = trade_dict.get('entry_time', '')
            if entry_time and not str(entry_time).startswith(today_str):
                continue
            if trade_dict.get('status') == 'OPEN':
                active_list.append(trade_dict)
            else:
                completed_list.append(trade_dict)
    except Exception as e:
        print("Error reading trades CSV:", e)
        
    return active_list, completed_list

def load_recent_logs(lines_count: int = 40) -> List[str]:
    if not os.path.exists(LOG_PATH):
        return ["No logs available."]
    try:
        with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            return [line.strip() for line in lines[-lines_count:]]
    except Exception as e:
        return [f"Error reading logs: {e}"]

def clean_nans(obj):
    if isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(x) for x in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj

# ─────────────────────────────────────────────────────────────────────────────
# MAIN API DATA ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/data")
def get_dashboard_data():
    # 1. Load trades from all three engines
    import glob
    
    # Engine V15 trades (Standard)
    active_v15, completed_v15 = load_trades_from_csv()
    
    # Engine V3 and V4 CSV paths
    today_ymd1 = datetime.now().strftime("%Y%m%d")
    today_ymd2 = datetime.now().strftime("%Y-%m-%d")
    
    v3_csv = None
    v4_csv = None
    
    base_dirs = [
        r"C:\cursor\options\niftyopt",
        r"C:\cursor\options\niftyopt\united_Indian_market1.0",
        "."
    ]
    
    for base in base_dirs:
        for fmt in [today_ymd1, today_ymd2]:
            v3_glob = glob.glob(os.path.join(base, "daily_data", f"v3_trades_*{fmt}*.csv"))
            if v3_glob:
                v3_csv = v3_glob[0]
                break
        if v3_csv:
            break
            
    for base in base_dirs:
        for fmt in [today_ymd1, today_ymd2]:
            v4_glob = glob.glob(os.path.join(base, "daily_data", f"modular_trades_*{fmt}*.csv"))
            if v4_glob:
                v4_csv = v4_glob[0]
                break
        if v4_csv:
            break
            
    active_v3, completed_v3 = load_modular_trades(v3_csv, fetcher, config_db)
    active_v4, completed_v4 = load_modular_trades(v4_csv, fetcher, config_db)
    
    # 2. Get spot and option prices from GlobalDataFetcher (0 API calls to Dhan during requests!)
    global LAST_SPOT_PRICES, LAST_OPTION_PRICES, dhan_connected
    
    dhan_connected = fetcher.client is not None
    
    for idx_name in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
        md = fetcher.get_market_data(idx_name)
        if md.spot > 0:
            LAST_SPOT_PRICES[idx_name] = md.spot
            
    LAST_SPOT_PRICES["VIX"] = fetcher.vix_value
    
    # Register active option security IDs from V15 to fetcher
    for t in active_v15:
        sec_id_str = t.get('option_security_id')
        if sec_id_str:
            fetcher.register_active_option_id(str(sec_id_str))
            
    spot_prices = LAST_SPOT_PRICES.copy()
    option_prices = fetcher.option_prices.copy()
    
    # 3. Process V15 Active Trades (Unrealized PnL & Greeks calculations)
    margin_v15 = 0.0
    unreal_pnl_v15 = 0.0
    for t in active_v15:
        idx_name = t['index']
        lot_size = int(config_db['index_profiles'].get(idx_name, {}).get('lot_size', 10))
        entry_px = float(t['entry_price'])
        lots = int(t['lots'])
        
        trade_margin = entry_px * lot_size * lots
        margin_v15 += trade_margin
        
        sec_id_str = t.get('option_security_id')
        current_ltp = entry_px
        if sec_id_str:
            current_ltp = option_prices.get(str(sec_id_str), entry_px)
            if current_ltp <= 0.0:
                current_ltp = entry_px
                
        t['current_price'] = current_ltp
        t_pnl = (current_ltp - entry_px) * lot_size * lots
        t['unrealized_pnl'] = round(t_pnl, 2)
        unreal_pnl_v15 += t_pnl
        
        spot = spot_prices.get(idx_name, float(t['entry_spot']))
        strike = float(t['strike'])
        is_call = t['direction'] == 'CE'
        days_to_expiry = 4.0
        try:
            parts = t['option_name'].split(' ')
            for part in parts:
                if '-' in part and len(part) == 10:
                    days_to_expiry = get_days_between(part)
                    break
        except Exception:
            pass
            
        t['greeks'] = calculate_greeks(spot, strike, days_to_expiry, is_call)
        
    realized_pnl_v15 = sum(float(t.get('pnl_rs', 0.0) or 0.0) for t in completed_v15)
    
    # 4. Process V4 Active Trades Summary
    margin_v4 = 0.0
    unreal_pnl_v4 = sum(float(t.get('unrealized_pnl', 0.0) or 0.0) for t in active_v4)
    # Estimate margin for V4 (standard lot size * entry_price)
    lot_size_nifty = int(config_db['index_profiles'].get('NIFTY', {}).get('lot_size', 75))
    for t in active_v4:
        margin_v4 += float(t['entry_price']) * lot_size_nifty * int(t['lots'])
    realized_pnl_v4 = sum(float(t.get('pnl_rs', 0.0) or 0.0) for t in completed_v4)
    
    # 5. Process V3 Active Trades Summary
    margin_v3 = 0.0
    unreal_pnl_v3 = sum(float(t.get('unrealized_pnl', 0.0) or 0.0) for t in active_v3)
    for t in active_v3:
        margin_v3 += float(t['entry_price']) * lot_size_nifty * int(t['lots'])
    realized_pnl_v3 = sum(float(t.get('pnl_rs', 0.0) or 0.0) for t in completed_v3)
    
    # Calculate margins per index (V15 + V4 + V3 combined or V15 only?)
    idx_margins = {k: 0.0 for k in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']}
    for t in active_v15:
        idx_name = t['index']
        lot_size = int(config_db['index_profiles'].get(idx_name, {}).get('lot_size', 10))
        idx_margins[idx_name] += float(t['entry_price']) * lot_size * int(t['lots'])
        
    # Load index states saved by the bot (regime, pcr, expiry)
    bot_index_states = {}
    if os.path.exists(r"C:\cursor\options\niftyopt\data\live_index_states.json"):
        try:
            with open(r"C:\cursor\options\niftyopt\data\live_index_states.json", "r") as f_json:
                bot_index_states = json.load(f_json)
        except Exception as e:
            logger.error(f"Error reading live_index_states.json: {e}")
            
    indices_status = []
    for idx_name in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
        bot_state = bot_index_states.get(idx_name, {})
        regime = bot_state.get("regime", "NORMAL")
        pcr = bot_state.get("pcr", 1.0)
        expiry = bot_state.get("expiry_date", "N/A")
        
        spot = spot_prices[idx_name]
        if spot <= 0.0 and bot_state.get("spot", 0.0) > 0.0:
            spot = float(bot_state["spot"])
            
        indices_status.append({
            "name": idx_name,
            "spot": spot,
            "margin_used": idx_margins[idx_name],
            "margin_limit": CAPITAL_PER_INDEX,
            "regime": regime,
            "pcr": pcr,
            "expiry": expiry
        })
        
    logs = load_recent_logs()
    
    # Calculate market open/closed status
    market_status = "CLOSED"
    now_dt = datetime.now()
    if now_dt.weekday() < 5:  # Monday to Friday
        current_time = now_dt.time()
        start_time = datetime.strptime("09:15:00", "%H:%M:%S").time()
        end_time = datetime.strptime("15:30:00", "%H:%M:%S").time()
        if start_time <= current_time <= end_time:
            market_status = "OPEN"
            
    # Load latest EOD report if available
    eod_report = None
    try:
        eod_files = glob.glob(r"C:\cursor\options\niftyopt\data\daily_analysis_*.log")
        if eod_files:
            eod_files.sort()
            latest_eod_path = eod_files[-1]
            with open(latest_eod_path, 'r', encoding='utf-8', errors='ignore') as f_eod:
                eod_report = f_eod.read()
    except Exception as e:
        logger.error(f"Error reading latest daily EOD report: {e}")
        
    self_learning_audit = []
    try:
        sl_path = r"C:\cursor\options\niftyopt\data\self_learning_audit.json"
        if os.path.exists(sl_path):
            with open(sl_path, 'r', encoding='utf-8') as f_sl:
                import json
                self_learning_audit = json.load(f_sl)
    except Exception as e:
        logger.error(f"Error loading self_learning_audit: {e}")
        
    # Telegram Integration
    telegram_connected = False
    try:
        if os.path.exists(r"C:\25stragy\telegram_status.json"):
            with open(r"C:\25stragy\telegram_status.json", "r") as f:
                telegram_connected = json.load(f).get("status") == "CONNECTED"
    except Exception:
        pass
        
    telegram_trades = []
    try:
        if os.path.exists(r"C:\25stragy\telegram_signals.xlsx"):
            tdf = pd.read_excel(r"C:\25stragy\telegram_signals.xlsx")
            for _, r in tdf.iterrows():
                # Map to frontend UI format
                telegram_trades.append({
                    "index": str(r.get("channel_id", "VENDOR")),
                    "option_name": str(r.get("instrument", "Unknown")),
                    "direction": str(r.get("action", "CE")),
                    "lots": 1,
                    "entry_price": str(r.get("entry_range", "0")),
                    "current_price": str(r.get("target", "0")),
                    "greeks": {"delta": 0, "theta": 0, "iv": 0},
                    "unrealized_pnl": 0.0,
                    "status": r.get("status", "NEW_SIGNAL")
                })
    except Exception:
        pass
            
    res_payload = {
        "telegram_connected": telegram_connected,
        "telegram_trades": telegram_trades,
        "self_learning_audit": self_learning_audit,
        "summary": {
            "capital_base": CAPITAL_BASE,
            "margin_used": margin_v15,
            "available_capital": max(0.0, CAPITAL_BASE - margin_v15),
            "realized_pnl": round(realized_pnl_v15, 2),
            "unrealized_pnl": round(unreal_pnl_v15, 2),
            "net_pnl": round(realized_pnl_v15 + unreal_pnl_v15, 2),
            "market_status": market_status,
            "api_connected": dhan_connected,
            "vix": spot_prices.get("VIX", 14.72)
        },
        "indices": indices_status,
        "active_trades": active_v15,
        "completed_trades": completed_v15[-40:],
        "logs": logs,
        "eod_report": eod_report,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        
        # Specific Engine Data Blocks
        "v15": {
            "summary": {
                "capital_base": CAPITAL_BASE,
                "margin_used": margin_v15,
                "available_capital": max(0.0, CAPITAL_BASE - margin_v15),
                "realized_pnl": round(realized_pnl_v15, 2),
                "unrealized_pnl": round(unreal_pnl_v15, 2),
                "net_pnl": round(realized_pnl_v15 + unreal_pnl_v15, 2)
            },
            "active_trades": active_v15,
            "completed_trades": completed_v15[-40:]
        },
        "v4": {
            "summary": {
                "capital_base": CAPITAL_BASE,
                "margin_used": margin_v4,
                "available_capital": max(0.0, CAPITAL_BASE - margin_v4),
                "realized_pnl": round(realized_pnl_v4, 2),
                "unrealized_pnl": round(unreal_pnl_v4, 2),
                "net_pnl": round(realized_pnl_v4 + unreal_pnl_v4, 2)
            },
            "active_trades": active_v4,
            "completed_trades": completed_v4[-40:]
        },
        "v3": {
            "summary": {
                "capital_base": CAPITAL_BASE,
                "margin_used": margin_v3,
                "available_capital": max(0.0, CAPITAL_BASE - margin_v3),
                "realized_pnl": round(realized_pnl_v3, 2),
                "unrealized_pnl": round(unreal_pnl_v3, 2),
                "net_pnl": round(realized_pnl_v3 + unreal_pnl_v3, 2)
            },
            "active_trades": active_v3,
            "completed_trades": completed_v3[-40:]
        },
        "telegram": {
            "summary": {
                "capital_base": CAPITAL_BASE,
                "margin_used": 0.0,
                "available_capital": CAPITAL_BASE,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0
            },
            "active_trades": telegram_trades,
            "completed_trades": []
        }
    }
    return clean_nans(res_payload)

# ─────────────────────────────────────────────────────────────────────────────
# STUNNING WEB DASHBOARD HTML INTERFACE
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def get_dashboard_ui():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>25 Strategy Nifty Options Workstation</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-main: #06070d;
                --bg-card: rgba(13, 16, 28, 0.7);
                --bg-card-border: rgba(255, 255, 255, 0.06);
                --text-main: #f1f5f9;
                --text-muted: #64748b;
                --accent-green: #10b981;
                --accent-red: #ef4444;
                --accent-blue: #3b82f6;
                --accent-yellow: #f59e0b;
                --neon-green-glow: 0 0 15px rgba(16, 185, 129, 0.3);
                --neon-red-glow: 0 0 15px rgba(239, 44, 68, 0.3);
                --neon-blue-glow: 0 0 15px rgba(59, 130, 246, 0.3);
                --neon-yellow-glow: 0 0 15px rgba(245, 158, 11, 0.3);
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                font-family: 'Outfit', sans-serif;
                background-color: var(--bg-main);
                color: var(--text-main);
                min-height: 100vh;
                padding: 24px;
                overflow-x: hidden;
            }

            body::before {
                content: '';
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                background-image: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.03) 0%, transparent 40%),
                                  radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.03) 0%, transparent 40%);
                z-index: -2;
                pointer-events: none;
            }

            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 24px;
                padding: 16px 24px;
                background: var(--bg-card);
                border: 1px solid var(--bg-card-border);
                backdrop-filter: blur(12px);
                border-radius: 16px;
            }

            .logo-section h1 {
                font-size: 24px;
                font-weight: 700;
                background: linear-gradient(135deg, #3b82f6, #10b981);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .logo-section span {
                font-size: 11px;
                color: var(--text-muted);
                border: 1px solid var(--bg-card-border);
                padding: 2px 8px;
                border-radius: 20px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            .status-panel {
                display: flex;
                align-items: center;
                gap: 16px;
            }

            .status-badge {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 30px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                transition: all 0.3s ease;
            }

            .status-badge.open {
                background: rgba(16, 185, 129, 0.08);
                color: var(--accent-green);
                border: 1px solid rgba(16, 185, 129, 0.2);
            }
            .status-badge.closed {
                background: rgba(100, 116, 139, 0.08);
                color: var(--text-muted);
                border: 1px solid rgba(100, 116, 139, 0.2);
            }
            .status-badge.connected {
                background: rgba(59, 130, 246, 0.08);
                color: var(--accent-blue);
                border: 1px solid rgba(59, 130, 246, 0.2);
            }
            .status-badge.disconnected {
                background: rgba(239, 68, 68, 0.08);
                color: var(--accent-red);
                border: 1px solid rgba(239, 68, 68, 0.2);
            }

            .status-badge::before {
                content: '';
                display: inline-block;
                width: 7px; height: 7px;
                border-radius: 50%;
            }

            .status-badge.open::before {
                background-color: var(--accent-green);
                box-shadow: 0 0 8px var(--accent-green);
                animation: pulse 1.5s infinite;
            }
            .status-badge.closed::before {
                background-color: var(--text-muted);
            }
            .status-badge.connected::before {
                background-color: var(--accent-blue);
                box-shadow: 0 0 8px var(--accent-blue);
                animation: pulse 1.5s infinite;
            }
            .status-badge.disconnected::before {
                background-color: var(--accent-red);
                box-shadow: 0 0 8px var(--accent-red);
                animation: pulse 1.5s infinite;
            }

            @keyframes pulse {
                0% { transform: scale(0.9); opacity: 0.6; }
                50% { transform: scale(1.25); opacity: 1; }
                100% { transform: scale(0.9); opacity: 0.6; }
            }

            /* Metrics Grid */
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-bottom: 24px;
            }

            .metric-card {
                background: var(--bg-card);
                border: 1px solid var(--bg-card-border);
                backdrop-filter: blur(12px);
                border-radius: 16px;
                padding: 18px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                position: relative;
                overflow: hidden;
                transition: transform 0.2s, border-color 0.2s;
            }

            .metric-card:hover {
                transform: translateY(-2px);
                border-color: rgba(255, 255, 255, 0.12);
            }

            .metric-title {
                font-size: 12px;
                font-weight: 600;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
            }

            .metric-value {
                font-size: 26px;
                font-weight: 700;
                margin-bottom: 6px;
                letter-spacing: -0.5px;
            }

            .metric-sub {
                font-size: 11px;
                color: var(--text-muted);
            }

            /* Glow borders for specific cards */
            .metric-card.profit { border-left: 4px solid var(--accent-green); }
            .metric-card.loss { border-left: 4px solid var(--accent-red); }
            .metric-card.info { border-left: 4px solid var(--accent-blue); }
            .metric-card.warning { border-left: 4px solid var(--accent-yellow); }

            /* Index Grid */
            .index-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
                gap: 16px;
                margin-bottom: 24px;
            }

            .index-card {
                background: var(--bg-card);
                border: 1px solid var(--bg-card-border);
                backdrop-filter: blur(12px);
                border-radius: 16px;
                padding: 16px;
                transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
            }

            .index-card:hover {
                transform: translateY(-2px);
                border-color: rgba(255, 255, 255, 0.12);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
            }

            .index-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }

            .index-name {
                font-size: 14px;
                font-weight: 700;
                color: var(--text-muted);
            }

            .index-regime {
                font-size: 10px;
                font-weight: 600;
                background: rgba(59, 130, 246, 0.12);
                color: #60a5fa;
                padding: 2px 6px;
                border-radius: 4px;
                text-transform: uppercase;
            }

            .index-price {
                font-size: 22px;
                font-weight: 700;
                margin-bottom: 8px;
                transition: color 0.3s;
            }

            .price-up { color: var(--accent-green); text-shadow: 0 0 10px rgba(16, 185, 129, 0.15); }
            .price-down { color: var(--accent-red); text-shadow: 0 0 10px rgba(239, 68, 68, 0.15); }

            .index-meta {
                font-size: 11px;
                color: var(--text-muted);
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                background: rgba(255, 255, 255, 0.02);
                padding: 4px 8px;
                border-radius: 6px;
            }

            .index-meta-val {
                color: var(--text-main);
                font-weight: 600;
            }

            .index-progress-container {
                width: 100%;
                background: rgba(255, 255, 255, 0.04);
                height: 5px;
                border-radius: 10px;
                overflow: hidden;
                margin-bottom: 8px;
            }

            .index-progress-bar {
                height: 100%;
                background: var(--accent-blue);
                width: 0%;
                transition: width 0.4s ease-in-out;
            }

            .index-margin-desc {
                font-size: 11px;
                color: var(--text-muted);
                display: flex;
                justify-content: space-between;
            }

            /* Dashboard Layout split */
            .main-content {
                display: grid;
                grid-template-columns: 1.8fr 1.2fr;
                gap: 24px;
                margin-bottom: 24px;
            }

            @media (max-width: 1024px) {
                .main-content {
                    grid-template-columns: 1fr;
                }
            }

            .panel-card {
                background: var(--bg-card);
                border: 1px solid var(--bg-card-border);
                backdrop-filter: blur(12px);
                border-radius: 16px;
                padding: 20px;
                display: flex;
                flex-direction: column;
                height: 100%;
            }

            .panel-title {
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--bg-card-border);
                padding-bottom: 10px;
            }

            /* Tables styling */
            .table-container {
                overflow-x: auto;
                width: 100%;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                text-align: left;
                font-size: 14px;
            }

            th {
                color: var(--text-muted);
                font-weight: 500;
                padding: 10px 12px;
                border-bottom: 1px solid var(--bg-card-border);
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            td {
                padding: 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            }

            tr:last-child td {
                border-bottom: none;
            }

            .badge {
                padding: 3px 6px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
            }

            .badge.ce {
                background: rgba(16, 185, 129, 0.12);
                color: var(--accent-green);
                border: 1px solid rgba(16, 185, 129, 0.15);
            }

            .badge.pe {
                background: rgba(239, 68, 68, 0.12);
                color: var(--accent-red);
                border: 1px solid rgba(239, 68, 68, 0.15);
            }

            .greeks-display {
                display: flex;
                gap: 6px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 10.5px;
            }

            .greek-val {
                background: rgba(255, 255, 255, 0.03);
                padding: 1px 4px;
                border-radius: 3px;
                color: var(--text-main);
            }

            .pnl-cell {
                font-weight: 600;
            }

            /* Log terminal style */
            .terminal {
                font-family: 'JetBrains Mono', monospace;
                background-color: #040509;
                border: 1px solid var(--bg-card-border);
                border-radius: 12px;
                padding: 16px;
                height: 320px;
                overflow-y: auto;
                font-size: 11.5px;
                line-height: 1.6;
                color: #94a3b8;
            }

            .log-line {
                margin-bottom: 4px;
                white-space: pre-wrap;
            }

            .log-line.info { color: #cbd5e1; }
            .log-line.warning { color: var(--accent-yellow); }
            .log-line.error { color: var(--accent-red); }

            /* Scrollbars */
            ::-webkit-scrollbar {
                width: 6px;
                height: 6px;
            }
            ::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.1);
            }
            ::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.08);
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: rgba(255, 255, 255, 0.16);
            }
            #eodReportBtn:hover {
                background: rgba(245, 158, 11, 0.22) !important;
                border-color: rgba(245, 158, 11, 0.45) !important;
                box-shadow: 0 0 10px rgba(245, 158, 11, 0.25);
            }

            /* Tabs Styling */
            .tabs-container {
                display: flex;
                gap: 12px;
                margin-bottom: 24px;
                background: rgba(13, 16, 28, 0.5);
                border: 1px solid var(--bg-card-border);
                padding: 6px;
                border-radius: 12px;
                width: fit-content;
            }
            .tab-btn {
                font-family: 'Outfit', sans-serif;
                font-size: 13px;
                font-weight: 600;
                color: var(--text-muted);
                background: transparent;
                border: none;
                padding: 8px 20px;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .tab-btn:hover {
                background: rgba(255, 255, 255, 0.04);
                color: var(--text-main);
            }
            .tab-btn.active {
                background: rgba(59, 130, 246, 0.12);
                color: var(--accent-blue);
                border: 1px solid rgba(59, 130, 246, 0.25);
                box-shadow: var(--neon-blue-glow);
            }
        </style>
    </head>
    <body>

        <header>
            <div class="logo-section">
                <h1>25 Strategy Nifty Options <span>Production</span></h1>
            </div>
            <div class="status-panel">
                <button id="eodReportBtn" style="display: none; background: rgba(245, 158, 11, 0.1); color: var(--accent-yellow); border: 1px solid rgba(245, 158, 11, 0.25); font-family: 'Outfit', sans-serif; font-weight: 600; font-size: 13px; padding: 6px 14px; border-radius: 30px; cursor: pointer; transition: all 0.2s; text-transform: uppercase; letter-spacing: 0.5px;" onclick="viewEodReport()">EOD Report</button>
                <div id="marketStatusBadge" class="status-badge closed">Market Closed</div>
                <div id="dhanStatusBadge" class="status-badge disconnected">Dhan Disconnected</div>
                <div id="telegramStatusBadge" class="status-badge disconnected">Telegram Offline</div>
                <div id="liveClock" style="font-family: 'JetBrains Mono', monospace; font-size: 15px; color: var(--text-muted);">00:00:00</div>
            </div>
        </header>



        <!-- Metric Summary Cards -->
        <div class="metrics-grid">
            <div class="metric-card info">
                <div class="metric-title">Capital Base</div>
                <div class="metric-value" id="capitalBase">Rs. 0.00</div>
                <div class="metric-sub">Shared Portfolio Base</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Used Margin</div>
                <div class="metric-value" id="marginUsed">Rs. 0.00</div>
                <div class="metric-sub" id="marginPct">0.0% Allocation</div>
            </div>
            <div class="metric-card warning" id="vixCard">
                <div class="metric-title">India VIX</div>
                <div class="metric-value" id="indiaVix" style="color: var(--accent-yellow);">14.72</div>
                <div class="metric-sub">Volatility Index</div>
            </div>
            <div class="metric-card info" id="tradesCard">
                <div class="metric-title">Total Trades</div>
                <div class="metric-value" id="totalTrades">0</div>
                <div class="metric-sub" id="tradesBreakdown">0 Active / 0 Closed</div>
            </div>
            <div class="metric-card" id="winRateCard">
                <div class="metric-title">Win Rate</div>
                <div class="metric-value" id="winRate">0.0%</div>
                <div class="metric-sub" id="winLossRatio">0 W / 0 L</div>
            </div>
            <div class="metric-card profit" id="realizedCard">
                <div class="metric-title">Today's Realized PnL</div>
                <div class="metric-value" id="realizedPnl">Rs. 0.00</div>
                <div class="metric-sub">Booked Trades</div>
            </div>
            <div class="metric-card" id="unrealizedCard">
                <div class="metric-title">Live Unrealized PnL</div>
                <div class="metric-value" id="unrealizedPnl">Rs. 0.00</div>
                <div class="metric-sub">Open Positions</div>
            </div>
        </div>

        <!-- 5 Indices Tracker -->
        <div class="index-grid" id="indexContainer" style="margin-bottom: 24px;">
            <!-- Dynamic index cards populated by JS -->
        </div>

        <div class="tabs-container" style="margin-left: auto; margin-right: auto; margin-top: 12px; margin-bottom: 24px; padding: 4px; background: rgba(0,0,0,0.2); border-radius: 12px; display: flex; justify-content: center; gap: 8px;">
            <button class="tab-btn active" id="tab-v15" onclick="switchEngine('v15')" style="padding: 10px 30px; font-size: 15px;">15 Ultimate Strategies</button>
            <button class="tab-btn" id="tab-telegram" onclick="switchEngine('telegram')" style="padding: 10px 30px; font-size: 15px; border-left: 2px solid var(--accent-blue);">Telegram Signals</button>
        </div>

        <!-- Main Dashboard Split Layout -->
        <div class="main-content">
            <!-- Active Positions Panel -->
            <div class="panel-card">
                <div class="panel-title">
                    <span>Active Positions</span>
                    <span id="activeCount" style="font-size: 11px; font-weight: 700; color: var(--text-muted); background: rgba(255, 255, 255, 0.04); padding: 2px 8px; border-radius: 10px;">0</span>
                </div>
                <div class="table-container">
                    <table>
                        <thead id="activeTradesHead">
                            <tr>
                                <th>Index</th>
                                <th>Option Name</th>
                                <th>Dir</th>
                                <th>Lots</th>
                                <th>Entry Px</th>
                                <th>Live Px</th>
                                <th>Greeks (Delta / Theta / IV)</th>
                                <th>Unrealized PnL</th>
                            </tr>
                        </thead>
                        <tbody id="activeTradesTable">
                            <tr>
                                <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px 0;">No active positions currently.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Terminal / Logs Panel -->
            <div class="panel-card">
                <div class="panel-title">Engine Audit Logs Terminal</div>
                <div class="terminal" id="terminalLog">
                    <!-- Logs stream -->
                </div>
            </div>
        </div>

        <!-- Completed Trades Table -->
        <div class="panel-card" style="margin-bottom: 24px;">
            <div class="panel-title">Today's Completed Trades History</div>
            <div class="table-container">
                <table>
                    <thead id="completedTradesHead">
                        <tr>
                            <th>Exit Time</th>
                            <th>Index</th>
                            <th>Strategy</th>
                            <th>Dir</th>
                            <th>Lots</th>
                            <th>Entry Px</th>
                            <th>Exit Px</th>
                            <th>Exit Reason</th>
                            <th>Realized PnL</th>
                        </tr>
                    </thead>
                    <tbody id="completedTradesTable">
                        <tr>
                            <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 40px 0;">No completed trades logged today.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- AI Self-Tuning Optimizer & Performance Matrix Panel -->
        <div class="panel-card" style="margin-bottom: 24px;">
            <div class="panel-title" style="display: flex; justify-content: space-between; align-items: center;">
                <span>🤖 AI Self-Tuning Optimizer & Performance Matrix Logs</span>
                <span id="tuningScoreBadge" style="font-size: 11px; font-weight: 700; color: var(--accent-green); background: rgba(16, 185, 129, 0.1); padding: 2px 10px; border-radius: 10px;">Self-Learning Active</span>
            </div>
            
            <!-- Optimizer stats boxes -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px;">
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.04); padding: 16px; border-radius: 8px;">
                    <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase;">Optimization Improvement</div>
                    <div style="font-size: 24px; font-weight: 700; color: var(--accent-green);" id="tuningImprovementPct">0.0%</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">P&L Recovery Factor</div>
                </div>
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.04); padding: 16px; border-radius: 8px;">
                    <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase;">Estimated Improved P&L</div>
                    <div style="font-size: 24px; font-weight: 700; color: var(--text-blue);" id="tuningImprovedPnl">Rs. 0.00</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">After Risk-Sizing Tuning</div>
                </div>
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.04); padding: 16px; border-radius: 8px;">
                    <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase;">Total Tuning Actions</div>
                    <div style="font-size: 24px; font-weight: 700; color: var(--accent-yellow);" id="tuningActionsCount">0</div>
                    <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Auto-applied adjustments</div>
                </div>
            </div>

            <!-- Tuning Actions Table -->
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Adjustment Type</th>
                            <th>Target / Index</th>
                            <th>Parameter Changed</th>
                            <th>Prev Value</th>
                            <th>New Value</th>
                            <th>Reason / Insight</th>
                        </tr>
                    </thead>
                    <tbody id="tuningLogsTable">
                        <tr>
                            <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 40px 0;">No self-tuning logs parsed yet. Run EOD reports to seed audit database.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            // Cache spot prices to detect tick direction
            const spotCache = {};
            let cachedEodReport = null;
            let currentEngine = 'v15';
            let globalData = null;

            function viewEodReport() {
                if (!cachedEodReport) return;
                const reportWindow = window.open("", "EODReportWindow", "width=850,height=650,scrollbars=yes,resizable=yes");
                reportWindow.document.write(`
                    <!DOCTYPE html>
                    <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                        <title>All-Star - EOD Report</title>
                        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
                        <style>
                            body {
                                font-family: 'Outfit', sans-serif;
                                background-color: #06070d;
                                color: #f1f5f9;
                                padding: 24px;
                                margin: 0;
                            }
                            .header {
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                                margin-bottom: 20px;
                                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                                padding-bottom: 12px;
                            }
                            h1 {
                                font-size: 20px;
                                font-weight: 700;
                                color: #f59e0b;
                                margin: 0;
                            }
                            pre {
                                font-family: 'JetBrains Mono', monospace;
                                font-size: 13.5px;
                                line-height: 1.6;
                                color: #cbd5e1;
                                background: #0d101c;
                                border: 1px solid rgba(255, 255, 255, 0.06);
                                padding: 20px;
                                border-radius: 12px;
                                overflow-x: auto;
                                white-space: pre-wrap;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="header">
                            <h1>EOD Performance & Actionable Learning Audit</h1>
                            <span style="font-size: 11px; font-weight: 600; background: rgba(245, 158, 11, 0.15); color: #f59e0b; padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(245, 158, 11, 0.25);">SWOT Learning Log</span>
                        </div>
                        <pre>${cachedEodReport}</pre>
                    </body>
                    </html>
                `);
                reportWindow.document.close();
            }

            function formatCurrency(val) {
                return new Intl.NumberFormat('en-IN', {
                    style: 'currency',
                    currency: 'INR',
                    maximumFractionDigits: 2
                }).format(val);
            }

            function updateClock() {
                const now = new Date();
                document.getElementById('liveClock').innerText = now.toLocaleTimeString();
            }
            setInterval(updateClock, 1000);
            updateClock();

            function switchEngine(engineId) {
                currentEngine = engineId;
                document.querySelectorAll('.tab-btn').forEach(btn => {
                    btn.classList.remove('active');
                });
                document.getElementById(`tab-${engineId}`).classList.add('active');
                
                if (globalData) {
                    renderDashboard(globalData);
                }
            }

            function renderDashboard(data) {
                // 1. Update Header Status Badges
                const marketBadge = document.getElementById('marketStatusBadge');
                if (data.summary.market_status === "OPEN") {
                    marketBadge.innerText = "Market Open";
                    marketBadge.className = "status-badge open";
                } else {
                    marketBadge.innerText = "Market Closed";
                    marketBadge.className = "status-badge closed";
                }

                const dhanBadge = document.getElementById('dhanStatusBadge');
                if (data.summary.api_connected) {
                    dhanBadge.innerText = "Dhan Connected";
                    dhanBadge.className = "status-badge connected";
                } else {
                    dhanBadge.className = 'status-badge disconnected';
                    dhanBadge.innerText = 'Dhan Offline';
                }
                
                const teleBadge = document.getElementById('telegramStatusBadge');
                if (data.telegram_connected) {
                    teleBadge.className = 'status-badge connected';
                    teleBadge.innerText = 'Telegram Live';
                } else {
                    teleBadge.className = 'status-badge disconnected';
                    teleBadge.innerText = 'Telegram Offline';
                }
                
                // Extract active engine block
                const engineData = data[currentEngine];
                const summary = engineData.summary;
                const completedTrades = engineData.completed_trades || [];
                const activeTrades = engineData.active_trades || [];
                const totalActive = activeTrades.length;
                const totalCompleted = completedTrades.length;
                const totalTradesCount = totalActive + totalCompleted;
                
                let wins = 0;
                let losses = 0;
                completedTrades.forEach(t => {
                    const pnlVal = parseFloat(t.pnl_rs || 0);
                    if (pnlVal > 0) wins++;
                    else if (pnlVal < 0) losses++;
                });
                const winRateVal = totalCompleted > 0 ? ((wins / totalCompleted) * 100) : 0.0;
                
                // 2. Update Metrics based on selected engine
                document.getElementById('capitalBase').innerText = formatCurrency(summary.capital_base);
                document.getElementById('marginUsed').innerText = formatCurrency(summary.margin_used);
                document.getElementById('indiaVix').innerText = data.summary.vix.toFixed(2);
                
                const pct = ((summary.margin_used / summary.capital_base) * 100).toFixed(1);
                document.getElementById('marginPct').innerText = `${pct}% Allocation`;
                
                // Update new cards
                document.getElementById('totalTrades').innerText = totalTradesCount;
                document.getElementById('tradesBreakdown').innerText = `${totalActive} Active / ${totalCompleted} Closed`;
                
                const winRateEl = document.getElementById('winRate');
                winRateEl.innerText = `${winRateVal.toFixed(1)}%`;
                document.getElementById('winLossRatio').innerText = `${wins} W / ${losses} L`;
                
                const winRateCard = document.getElementById('winRateCard');
                if (totalCompleted === 0) {
                    winRateEl.style.color = 'var(--text-muted)';
                    winRateCard.className = 'metric-card';
                } else if (winRateVal >= 50) {
                    winRateEl.style.color = 'var(--accent-green)';
                    winRateCard.className = 'metric-card profit';
                } else {
                    winRateEl.style.color = 'var(--accent-red)';
                    winRateCard.className = 'metric-card loss';
                }
                
                const rPnl = summary.realized_pnl;
                const realizedEl = document.getElementById('realizedPnl');
                realizedEl.innerText = formatCurrency(rPnl);
                
                const realizedCard = document.getElementById('realizedCard');
                if (rPnl >= 0) {
                    realizedEl.style.color = 'var(--accent-green)';
                    realizedCard.className = 'metric-card profit';
                } else {
                    realizedEl.style.color = 'var(--accent-red)';
                    realizedCard.className = 'metric-card loss';
                }
                
                const uPnl = summary.unrealized_pnl;
                const unrealizedEl = document.getElementById('unrealizedPnl');
                unrealizedEl.innerText = formatCurrency(uPnl);
                
                const unrealizedCard = document.getElementById('unrealizedCard');
                if (uPnl >= 0) {
                    unrealizedEl.style.color = 'var(--accent-green)';
                    unrealizedCard.className = 'metric-card profit';
                } else {
                    unrealizedEl.style.color = 'var(--accent-red)';
                    unrealizedCard.className = 'metric-card loss';
                }

                // 3. Update EOD Report Button visibility
                const eodBtn = document.getElementById('eodReportBtn');
                if (data.eod_report) {
                    cachedEodReport = data.eod_report;
                    eodBtn.style.display = 'block';
                } else {
                    cachedEodReport = null;
                    eodBtn.style.display = 'none';
                }
                
                // 4. Update Indices Grid
                const indexContainer = document.getElementById('indexContainer');
                indexContainer.innerHTML = '';
                
                data.indices.forEach(idx => {
                    const prevPrice = spotCache[idx.name] || idx.spot;
                    let directionClass = '';
                    if (idx.spot > prevPrice) directionClass = 'price-up';
                    else if (idx.spot < prevPrice) directionClass = 'price-down';
                    spotCache[idx.name] = idx.spot;
                    
                    const idxMarginUsed = currentEngine === 'v15' ? idx.margin_used : (idx.name === 'NIFTY' ? summary.margin_used : 0.0);
                    const marginPct = ((idxMarginUsed / idx.margin_limit) * 100).toFixed(0);
                    
                    const cardHtml = `
                        <div class="index-card">
                            <div class="index-header">
                                <span class="index-name">${idx.name}</span>
                                <span class="index-regime">${idx.regime}</span>
                            </div>
                            <div class="index-price ${directionClass}">${idx.spot.toFixed(2)}</div>
                            <div class="index-meta">
                                <span>PCR: <span class="index-meta-val">${idx.pcr.toFixed(2)}</span></span>
                                <span>Expiry: <span class="index-meta-val">${idx.expiry}</span></span>
                            </div>
                            <div class="index-progress-container">
                                <div class="index-progress-bar" style="width: ${marginPct}%"></div>
                            </div>
                            <div class="index-margin-desc">
                                <span>Margin: ${formatCurrency(idxMarginUsed)}</span>
                                <span>${marginPct}%</span>
                            </div>
                        </div>
                    `;
                    indexContainer.insertAdjacentHTML('beforeend', cardHtml);
                });
                
                // Remove color transition classes
                setTimeout(() => {
                    document.querySelectorAll('.index-price').forEach(el => {
                        el.className = 'index-price';
                    });
                }, 500);

                                // 5. Update Active Trades
                const activeHead = document.getElementById('activeTradesHead');
                if (activeHead) {
                    if (currentEngine === 'telegram') {
                        activeHead.innerHTML = `<tr><th>Channel ID</th><th>Instrument</th><th>Action</th><th>Lots</th><th>Entry Range</th><th>Target / SL</th><th>Status</th><th>AI Inference</th></tr>`;
                    } else {
                        activeHead.innerHTML = `<tr><th>Index</th><th>Option Name</th><th>Dir</th><th>Lots</th><th>Entry Px</th><th>Live Px</th><th>Greeks (Delta/Theta)</th><th>Unrealized PnL</th></tr>`;
                    }
                }
                
                const completedHead = document.getElementById('completedTradesHead');
                if (completedHead) {
                    if (currentEngine === 'telegram') {
                        completedHead.innerHTML = `<tr><th>Exit Time</th><th>Channel ID</th><th>Instrument</th><th>Action</th><th>Lots</th><th>Entry Px</th><th>Exit Px</th><th>Reason</th><th>Realized PnL</th></tr>`;
                    } else {
                        completedHead.innerHTML = `<tr><th>Exit Time</th><th>Index</th><th>Strategy</th><th>Dir</th><th>Lots</th><th>Entry Px</th><th>Exit Px</th><th>Exit Reason</th><th>Realized PnL</th></tr>`;
                    }
                }

                // Update Active Trades Count
                const activeCount = document.getElementById('activeCount');
                activeCount.innerText = activeTrades.length;
                
                const activeTable = document.getElementById('activeTradesTable');
                if (activeTrades.length === 0) {
                    activeTable.innerHTML = `
                        <tr>
                            <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px 0;">No active positions currently.</td>
                        </tr>
                    `;
                } else {
                    activeTable.innerHTML = '';
                    activeTrades.forEach(t => {
                        let row = '';
                        if (currentEngine === 'telegram') {
                            row = `
                                <tr>
                                    <td><strong style="color: var(--accent-blue); font-size: 11px;">${t.index}</strong></td>
                                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">${t.option_name}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td style="color: var(--accent-yellow);">${t.entry_price}</td>
                                    <td><strong style="color: var(--accent-green);">${t.current_price}</strong></td>
                                    <td><span class="badge" style="background: rgba(245, 158, 11, 0.1); color: var(--accent-yellow); font-size: 10px;">${t.status}</span></td>
                                    <td style="color: var(--text-muted); font-size: 12px; font-style: italic;">Monitoring Momentum & TP</td>
                                </tr>
                            `;
                        } else {
                            const pnlClass = t.unrealized_pnl >= 0 ? 'price-up' : 'price-down';
                            row = `
                                <tr>
                                    <td><strong style="color: var(--accent-blue);">${t.index}</strong></td>
                                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">${t.option_name}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td>${formatCurrency(t.entry_price)}</td>
                                    <td><strong>${formatCurrency(t.current_price)}</strong></td>
                                    <td>
                                        <div class="greeks-display">
                                            <span>&Delta;: <span class="greek-val">${t.greeks.delta}</span></span>
                                            <span>&theta;: <span class="greek-val">${t.greeks.theta}</span></span>
                                            <span>IV: <span class="greek-val">${t.greeks.iv}%</span></span>
                                        </div>
                                    </td>
                                    <td class="pnl-cell ${pnlClass}">${formatCurrency(t.unrealized_pnl)}</td>
                                </tr>
                            `;
                        }
                        activeTable.insertAdjacentHTML('beforeend', row);
                    });
                }

                // 6. Update Completed Trades Table
                const completedTable = document.getElementById('completedTradesTable');
                if (completedTrades.length === 0) {
                    completedTable.innerHTML = `
                        <tr>
                            <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 40px 0;">No completed trades logged today.</td>
                        </tr>
                    `;
                } else {
                    completedTable.innerHTML = '';
                    completedTrades.slice().reverse().forEach(t => {
                        const pnlClass = t.pnl_rs >= 0 ? 'price-up' : 'price-down';
                        let row = '';
                        if (currentEngine === 'telegram') {
                            row = `
                                <tr>
                                    <td style="color: var(--text-muted); font-size: 12.5px;">${t.exit_time || t.timestamp}</td>
                                    <td><strong style="color: var(--accent-blue); font-size: 11px;">${t.index}</strong></td>
                                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">${t.option_name}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td>${t.entry_price}</td>
                                    <td>${t.exit_price}</td>
                                    <td><span style="font-size: 12px; font-weight: 500; color: var(--accent-yellow);">${t.exit_reason || 'BOOKED'}</span></td>
                                    <td class="pnl-cell ${pnlClass}">${formatCurrency(t.pnl_rs)}</td>
                                </tr>
                            `;
                        } else {
                            row = `
                                <tr>
                                    <td style="color: var(--text-muted); font-size: 12.5px;">${t.exit_time || t.timestamp}</td>
                                    <td><strong>${t.index}</strong></td>
                                    <td style="font-size: 12.5px; color: var(--text-muted);">${t.strategy}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td>${formatCurrency(t.entry_price)}</td>
                                    <td>${formatCurrency(t.exit_price)}</td>
                                    <td><span style="font-size: 12px; font-weight: 500; color: var(--accent-yellow);">${t.exit_reason || 'EXIT'}</span></td>
                                    <td class="pnl-cell ${pnlClass}">${formatCurrency(t.pnl_rs)}</td>
                                </tr>
                            `;
                        }
                        completedTable.insertAdjacentHTML('beforeend', row);
                    });
                }

                // 7. Update Logs
                const terminal = document.getElementById('terminalLog');
                const atBottom = terminal.scrollHeight - terminal.scrollTop <= terminal.clientHeight + 40;
                
                terminal.innerHTML = '';
                data.logs.forEach(log => {
                    let typeClass = 'info';
                    if (log.includes('[WARNING]')) typeClass = 'warning';
                    else if (log.includes('[ERROR]')) typeClass = 'error';
                    
                    const line = `<div class="log-line ${typeClass}">${log}</div>`;
                    terminal.insertAdjacentHTML('beforeend', line);
                });
                
                if (atBottom) {
                    terminal.scrollTop = terminal.scrollHeight;
                }

                // 8. Update AI Self-Tuning Optimizer panel
                const tuningTable = document.getElementById('tuningLogsTable');
                if (data.self_learning_audit && data.self_learning_audit.length > 0) {
                    tuningTable.innerHTML = '';
                    let totalActions = 0;
                    let latestAudit = data.self_learning_audit[data.self_learning_audit.length - 1];
                    
                    // Update stats cards
                    document.getElementById('tuningImprovementPct').innerText = `${latestAudit.metrics.improvement_pct.toFixed(1)}%`;
                    document.getElementById('tuningImprovedPnl').innerText = formatCurrency(latestAudit.metrics.estimated_improved_pnl);
                    
                    // Render all adjustments across history
                    data.self_learning_audit.slice().reverse().forEach(audit => {
                        audit.adjustments.forEach(adj => {
                            totalActions++;
                            const row = `
                                <tr>
                                    <td style="color: var(--text-muted); font-size: 12.5px;">${audit.timestamp}</td>
                                    <td><span class="badge" style="background: rgba(59, 130, 246, 0.1); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.2);">${adj.type}</span></td>
                                    <td><strong>${adj.index}</strong></td>
                                    <td style="font-size: 12.5px; color: var(--text-muted);">${adj.parameter}</td>
                                    <td style="color: var(--accent-red);">${adj.old_value}</td>
                                    <td style="color: var(--accent-green);">${adj.new_value}</td>
                                    <td style="font-size: 12px; color: var(--text-muted); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${adj.reason}">${adj.reason}</td>
                                </tr>
                            `;
                            tuningTable.insertAdjacentHTML('beforeend', row);
                        });
                    });
                    document.getElementById('tuningActionsCount').innerText = totalActions;
                } else {
                    tuningTable.innerHTML = `
                        <tr>
                            <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 40px 0;">No self-tuning logs parsed yet. Run EOD reports to seed audit database.</td>
                        </tr>
                    `;
                }
            }

            async function fetchDashboardData() {
                try {
                    const res = await fetch('/api/data');
                    const data = await res.json();
                    globalData = data;
                    renderDashboard(data);
                } catch (err) {
                    console.error("Error loading dashboard data:", err);
                    document.getElementById('marketStatusBadge').innerText = "System Offline";
                    document.getElementById('marketStatusBadge').className = "status-badge closed";
                    document.getElementById('dhanStatusBadge').innerText = "Dhan Offline";
                    document.getElementById('dhanStatusBadge').className = "status-badge disconnected";
                }
            }

            // Polling interval 1.5 seconds
            setInterval(fetchDashboardData, 1500);
            fetchDashboardData();
        </script>
    </body>
    </html>
    """
    return html_content

if __name__ == "__main__":
    import uvicorn
    # Runs on local port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
