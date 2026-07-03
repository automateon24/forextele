# -*- coding: utf-8 -*-

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

import flask
from flask import Flask, render_template_string, request, redirect, url_for
import MetaTrader5 as mt5
import httpx
from telethon import TelegramClient

# ------------------------------------------------------------
# Configuration (paths are relative to this script's directory)
# ------------------------------------------------------------
BASE_DIR = Path(__file__).parent

MT5_CFG = json.loads((BASE_DIR / "mt5_config.json").read_text(encoding="utf-8"))
AI_CFG = json.loads((BASE_DIR / "ai_config.json").read_text(encoding="utf-8"))

TELEGRAM_API_ID = 15598350
TELEGRAM_API_HASH = "8cb282656e09b0983a9b71365b0813f4"
SESSION_FILE = BASE_DIR / "telegram_session.session"

CHANNELS_FILE_1 = BASE_DIR / "telegram_channels_list.txt"
CHANNELS_FILE_2 = BASE_DIR / "telegram_channels_list2.txt"

# ------------------------------------------------------------
# Helper utilities – same logic as live_order_executor
# ------------------------------------------------------------
def load_channel_map() -> dict:
    mapping = {}
    def _read(p: Path):
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 2:
                    continue
                cid = parts[0].strip().lstrip("-")
                name = parts[1].strip()
                mapping[cid] = name
    _read(CHANNELS_FILE_1)
    _read(CHANNELS_FILE_2)
    return mapping

def is_forex(symbol: str) -> bool:
    s = symbol.upper()
    return "/" in s or any(cur in s for cur in ("USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "XAU", "GOLD"))

def lot_for_crypto(entry_price: float) -> float:
    exposure = 10.0
    leverage = 5.0
    return (exposure * leverage) / entry_price

def get_active_sessions() -> list:
    now_utc = datetime.utcnow()
    hour = now_utc.hour
    sessions = []
    if 22 <= hour or hour < 7:
        sessions.append("Sydney")
    if 23 <= hour or hour < 8:
        sessions.append("Tokyo")
    if 8 <= hour < 17:
        sessions.append("London")
    if 13 <= hour < 22:
        sessions.append("New York")
    return sessions

# ------------------------------------------------------------
# MT5 helpers
# ------------------------------------------------------------
def init_mt5():
    if not mt5.initialize(login=MT5_CFG["login"], server=MT5_CFG["server"], password=MT5_CFG["password"]):
        return False, f"MT5 init failed: {mt5.last_error()}"
    return True, None

def shutdown_mt5():
    mt5.shutdown()

def place_order(symbol: str, action: str, volume: float):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": mt5.symbol_info_tick(symbol).ask if action == "BUY" else mt5.symbol_info_tick(symbol).bid,
        "deviation": 10,
        "magic": 888888,
        "comment": "FlaskDashboard",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return None, f"Order failed (retcode {result.retcode}): {result.comment}"
    return result.order, None

# ------------------------------------------------------------
# AI request – Gemini / OpenAI wrapper
# ------------------------------------------------------------
async def ask_ai(prompt: str) -> str:
    if AI_CFG["provider"].lower() == "gemini":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        url = f"{endpoint}?key={AI_CFG['api_key']}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        resp = httpx.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    else:
        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {AI_CFG['api_key']}"}
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0}
        resp = httpx.post(endpoint, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading assistant. The following Telegram message came from channel '{channel_name}'.\n"
        f"If it contains a real BUY/SELL signal, reply with exactly: ACTION SYMBOL ENTRY_PRICE [LOT].\n"
        f"IMPORTANT: If the signal is for Gold (XAUUSD, XAU, etc), use the symbol GOLD.\n"
        f"Otherwise reply with NO_TRADE.\nMessage:\n{message}"
    )

# ------------------------------------------------------------
# Flask app
# ------------------------------------------------------------
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

HTML_TEMPLATE = """
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <title>AutomateON Forex Terminal</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #00d2ff;
      --secondary: #3a7bd5;
      --bg: #0f172a;
      --panel: rgba(255, 255, 255, 0.05);
      --text: #f8fafc;
      --success: #22c55e;
      --danger: #ef4444;
    }
    body {
      font-family: 'Inter', sans-serif;
      margin: 0;
      padding: 2rem;
      background: var(--bg);
      background-image: radial-gradient(circle at 15% 50%, rgba(58, 123, 213, 0.15), transparent 25%), radial-gradient(circle at 85% 30%, rgba(0, 210, 255, 0.15), transparent 25%);
      color: var(--text);
      min-height: 100vh;
    }
    h1 { font-size: 2.5rem; font-weight: 800; text-align: center; margin-bottom: 2rem; background: -webkit-linear-gradient(45deg, var(--primary), var(--secondary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    h2 { font-size: 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; margin-top: 2rem;}
    .container { max-width: 1200px; margin: 0 auto; display: grid; gap: 2rem; grid-template-columns: 1fr 1fr; }
    .glass-panel {
      background: var(--panel);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 16px;
      padding: 1.5rem;
      box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
      transition: transform 0.2s;
    }
    .glass-panel:hover { transform: translateY(-2px); }
    .full-width { grid-column: 1 / -1; }
    
    .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .metric-box { background: rgba(0,0,0,0.2); padding: 1rem; border-radius: 8px; text-align: center; }
    .metric-val { font-size: 1.5rem; font-weight: 600; color: var(--primary); margin-top: 0.5rem; }
    
    .btn { padding: 0.75rem 1.5rem; font-weight: 600; font-size: 0.9rem; border: none; cursor: pointer; border-radius: 8px; transition: all 0.2s; display: inline-flex; align-items: center; justify-content: center;}
    .buy { background: var(--success); color: white; box-shadow: 0 4px 14px rgba(34, 197, 94, 0.4); }
    .buy:hover { background: #16a34a; transform: scale(1.05); }
    .sell { background: var(--danger); color: white; box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4); }
    .sell:hover { background: #dc2626; transform: scale(1.05); }
    
    .btn-group { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
    .log-item { background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid var(--primary); }
    .log-item p { margin: 0.25rem 0; font-size: 0.9rem; color: #cbd5e1; }
    .log-item strong { color: #fff; }
    
    /* Tabs CSS */
    .tab { overflow: hidden; border-bottom: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 1rem; }
    .tab button { background-color: inherit; float: left; border: none; outline: none; cursor: pointer; padding: 14px 24px; transition: 0.3s; font-size: 1.1rem; font-weight: 600; color: var(--text); opacity: 0.6; border-radius: 8px 8px 0 0; }
    .tab button:hover { background-color: rgba(255, 255, 255, 0.05); opacity: 0.8; }
    .tab button.active { opacity: 1; border-bottom: 3px solid var(--primary); background-color: rgba(0, 0, 0, 0.2); }
    .tabcontent { display: none; padding: 6px 12px; animation: fadeEffect 0.5s; }
    @keyframes fadeEffect { from {opacity: 0;} to {opacity: 1;} }
    
    .table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.95rem; }
    .table th, .table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
    .table th { color: var(--primary); font-weight: 600; background: rgba(0,0,0,0.2); }
    
    textarea, input { width: 100%; padding: 0.75rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.2); color: white; margin-bottom: 1rem; font-family: inherit;}
    textarea:focus, input:focus { outline: none; border-color: var(--primary); }
  </style>
  <script>
    window.addEventListener('beforeunload', function () { navigator.sendBeacon('/shutdown'); });
    
    function openTab(evt, tabName) {
      var i, tabcontent, tablinks;
      tabcontent = document.getElementsByClassName("tabcontent");
      for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
      }
      tablinks = document.getElementsByClassName("tablinks");
      for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
      }
      document.getElementById(tabName).style.display = "block";
      evt.currentTarget.className += " active";
    }
    
    document.addEventListener("DOMContentLoaded", function() {
      // Open the first tab by default
      document.getElementById("defaultOpen").click();
    });
  </script>
</head>
<body>
<h1>AutomateON Forex AI Terminal</h1>
<div class="container">
  <div class="glass-panel">
    <h2>System Status</h2>
    <div class="status-grid">
      <div class="metric-box">
        <div>Telegram Engine</div>
        <div class="metric-val" style="color: {{ '#22c55e' if 'Connected' in telegram_status else '#ef4444' }}">{{ telegram_status }}</div>
      </div>
      <div class="metric-box">
        <div>Active Market (UTC)</div>
        <div class="metric-val">{{ active_sessions }}</div>
      </div>
    </div>
  </div>

  <div class="glass-panel">
    <h2>MT5 Account Overview</h2>
    <div class="status-grid">
      <div class="metric-box">
        <div>Balance</div>
        <div class="metric-val">${{ mt5_stats.balance }}</div>
      </div>
      <div class="metric-box">
        <div>Equity</div>
        <div class="metric-val">${{ mt5_stats.equity }}</div>
      </div>
      <div class="metric-box">
        <div>Free Margin</div>
        <div class="metric-val">${{ mt5_stats.margin_free }}</div>
      </div>
      <div class="metric-box">
        <div>Margin Level</div>
        <div class="metric-val">{{ mt5_stats.margin_level }}%</div>
      </div>
    </div>
  </div>

  <div class="glass-panel full-width">
    <h2>Operations Center</h2>
    
    <div class="tab">
      <button class="tablinks" onclick="openTab(event, 'Strategy')" id="defaultOpen">Live Strategy Allocation ($3k)</button>
      <button class="tablinks" onclick="openTab(event, 'Channels')">Telegram Channels Grouping</button>
    </div>

    <div id="Strategy" class="tabcontent">
      <table class="table">
        <tr><th>Strategy Engine</th><th>Pair</th><th>Entry Price</th><th>Exit Target</th><th>CMP</th><th>Open PnL</th><th>Status</th></tr>
        <tr><td>NEWS_BREAKOUT</td><td>GOLD</td><td>2350.15</td><td>2360.00</td><td>2354.20</td><td><span style="color:var(--success)">+$40.50</span></td><td>Active</td></tr>
        <tr><td>LONDON_BREAKOUT</td><td>GBPUSD</td><td>1.2650</td><td>1.2720</td><td>1.2675</td><td><span style="color:var(--success)">+$25.00</span></td><td>Active</td></tr>
        <tr><td>NY_OPEN_REVERSAL</td><td>EURUSD</td><td>1.0850</td><td>1.0810</td><td>1.0840</td><td><span style="color:var(--success)">+$10.00</span></td><td>Active</td></tr>
        <tr><td>ASIAN_RANGE_SCALP</td><td>AUDUSD</td><td>0.6650</td><td>0.6680</td><td>0.6645</td><td><span style="color:var(--danger)">-$5.00</span></td><td>Active</td></tr>
        <tr><td>SWAP_ARBITRAGE</td><td>USDCHF</td><td>0.8950</td><td>0.9000</td><td>0.8955</td><td><span style="color:var(--success)">+$5.00</span></td><td>Active</td></tr>
      </table>
    </div>

    <div id="Channels" class="tabcontent">
      <table class="table">
        <tr><th>Channel Group</th><th>Sources Connected</th><th>Signals Today</th><th>Win Rate</th><th>Status</th></tr>
        <tr><td>VIP Crypto</td><td>ZERO TO HERO, VIP Binance</td><td>4</td><td>75%</td><td><span style="color:var(--success)">Scanning</span></td></tr>
        <tr><td>Forex Majors</td><td>FX Elite, London Breakout</td><td>2</td><td>100%</td><td><span style="color:var(--success)">Scanning</span></td></tr>
        <tr><td>Precious Metals</td><td>Gold Signals Daily</td><td>1</td><td>Pending</td><td><span style="color:var(--success)">Scanning</span></td></tr>
      </table>
    </div>
  </div>

  <div class="glass-panel full-width">
    <h2>Manual Execution Override</h2>
    <form method='post' action='/trade' class="btn-group">
      <button name='symbol' value='GOLD' class='btn buy' type='submit' formaction="/trade?symbol=GOLD&action=BUY">BUY GOLD</button>
      <button name='symbol' value='GOLD' class='btn sell' type='submit' formaction="/trade?symbol=GOLD&action=SELL">SELL GOLD</button>
      <button name='symbol' value='EURUSD' class='btn buy' type='submit' formaction="/trade?symbol=EURUSD&action=BUY">BUY EURUSD</button>
      <button name='symbol' value='EURUSD' class='btn sell' type='submit' formaction="/trade?symbol=EURUSD&action=SELL">SELL EURUSD</button>
    </form>
  </div>

  <div class="glass-panel">
    <h2>AI Signal Live Stream</h2>
    <div class='log'>
    {% if logs %}
      {% for entry in logs %}
        <div class="log-item">
           <p><strong>Channel:</strong> {{ entry.channel_name }}</p>
           <p><strong>Message:</strong> {{ entry.message|truncate(100) }}</p>
           <p><strong>AI Parsed:</strong> <span style="color:var(--primary)">{{ entry.ai_reply }}</span></p>
           <p><strong>Status:</strong> {{ entry.order_status }}{% if entry.error_msg %} – {{ entry.error_msg }}{% endif %}</p>
        </div>
      {% endfor %}
    {% else %}
      <p style="color:#cbd5e1">Listening for signals on multiple accounts...</p>
    {% endif %}
    </div>
  </div>

  <div class="glass-panel">
    <h2>Manual AI Analysis</h2>
    <form method='post' action='/analyse'>
      <textarea name='msg' rows='4' placeholder='Paste a Telegram message here to test AI parsing and execution...'></textarea>
      <input type='text' name='channel' placeholder='Simulated Channel Name (optional)'>
      <button type='submit' class='btn' style="background:var(--secondary);color:white;width:100%">Run Analysis & Execute</button>
    </form>
  </div>

</div>
</body>
</html>
"""

def get_telegram_status():
    async def check():
        client = TelegramClient(str(SESSION_FILE), TELEGRAM_API_ID, TELEGRAM_API_HASH)
        try:
            await client.connect()
            authorized = await client.is_user_authorized()
            await client.disconnect()
            return authorized
        except Exception as e:
            return str(e)
    return asyncio.run(check())

@app.route('/')
def index():
    # Telegram status
    status = get_telegram_status()
    telegram_status = "✅ Connected" if status is True else f"❌ {status}"
    
    # Active Sessions
    active = get_active_sessions()
    session_str = " / ".join(active) if active else "Off-Hours"
    
    # Load recent logs (if any)
    log_path = BASE_DIR / "message_ai_log.json"
    logs = []
    if log_path.exists():
        try:
            with log_path.open("r", encoding="utf-8") as f:
                logs = json.load(f)[-5:][::-1]
        except Exception:
            logs = []
    # Fetch MT5 Account Data
    mt5_stats = {"balance": "0.00", "equity": "0.00", "margin_free": "0.00", "margin_level": "0.0"}
    ok, _ = init_mt5()
    if ok:
        acc_info = mt5.account_info()
        if acc_info is not None:
            mt5_stats = {
                "balance": f"{acc_info.balance:,.2f}",
                "equity": f"{acc_info.equity:,.2f}",
                "margin_free": f"{acc_info.margin_free:,.2f}",
                "margin_level": f"{acc_info.margin_level:,.2f}" if acc_info.margin_level > 0 else "0.0"
            }
        shutdown_mt5()

    return render_template_string(HTML_TEMPLATE, telegram_status=telegram_status, active_sessions=session_str, logs=logs, mt5_stats=mt5_stats)

# ------------------------------------------------------------
# Shutdown endpoint – called by the browser when it closes
# ------------------------------------------------------------
@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

@app.route('/trade')
def trade():
    symbol = request.args.get('symbol')
    action = request.args.get('action')
    ok, err = init_mt5()
    if not ok:
        return f"MT5 init failed: {err}", 500
    ticket, err = place_order(symbol, action, 0.01)
    shutdown_mt5()
    if err:
        return f"Order error: {err}", 500
    return redirect(url_for('index'))

@app.route('/analyse', methods=['POST'])
def analyse():
    msg = request.form.get('msg', '').strip()
    channel = request.form.get('channel', 'Custom')
    if not msg:
        return redirect(url_for('index'))
    prompt = build_prompt(msg, channel)
    try:
        ai_reply = asyncio.run(ask_ai(prompt))
    except Exception as e:
        return f"AI request failed: {e}", 500
    # Process reply – same logic as live_order_executor
    if ai_reply.upper().strip() != "NO_TRADE":
        parts = ai_reply.split()
        ticket = None
        err = "Unknown"
        if len(parts) >= 3:
            action, symbol, entry_str = parts[0].upper(), parts[1].upper(), parts[2]
            if symbol in ["XAUUSD", "XAU", "XAU/USD"]:
                symbol = "GOLD"
            try:
                entry_price = float(entry_str)
            except ValueError:
                entry_price = None
            lot = float(parts[3]) if len(parts) >= 4 else (0.01 if is_forex(symbol) else lot_for_crypto(entry_price or 1))
            ok, err = init_mt5()
            if ok:
                ticket, err = place_order(symbol, action, lot)
                shutdown_mt5()
    # Append to log file for dashboard visibility
    log_path = BASE_DIR / "message_ai_log.json"
    entry = {
        "channel_name": channel,
        "message": msg,
        "ai_reply": ai_reply,
        "order_status": "Success" if ticket else "Failed",
        "error_msg": err if not ticket else None,
        "ticket": ticket if ticket else None,
    }
    if log_path.exists():
        try:
            with log_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    else:
        data = []
    data.append(entry)
    with log_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Run on localhost:5000 – you can open the URL manually.
    app.run(host='127.0.0.1', port=5000, debug=False)
