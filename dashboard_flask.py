# -*- coding: utf-8 -*-

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

import flask
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
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
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
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
    
    /* Expandable Grouping */
    details { background: rgba(0,0,0,0.2); border-radius: 8px; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.05); }
    summary { padding: 1rem; cursor: pointer; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
    summary:hover { background: rgba(255,255,255,0.05); }
    .group-title { font-size: 1.1rem; color: var(--primary); }
    .group-pnl { font-size: 1.1rem; }
    .details-content { padding: 0 1rem 1rem 1rem; }
    
    /* Notification Bell */
    .bell-container { position: fixed; top: 1.5rem; right: 2rem; font-size: 2rem; cursor: pointer; z-index: 1000; }
    .bell-icon { display: inline-block; transition: transform 0.2s; }
    .bell-icon.ringing { animation: ring 0.5s ease-in-out infinite; color: var(--danger); }
    @keyframes ring { 0% {transform: rotate(0deg);} 25% {transform: rotate(15deg);} 50% {transform: rotate(0deg);} 75% {transform: rotate(-15deg);} 100% {transform: rotate(0deg);} }
    .notif-badge { position: absolute; top: -5px; right: -5px; background: var(--danger); color: white; font-size: 0.8rem; border-radius: 50%; padding: 2px 6px; font-weight: bold; display: none; }
    .notif-dropdown { position: absolute; top: 40px; right: 0; background: var(--panel); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 1rem; width: 300px; display: none; box-shadow: 0 4px 30px rgba(0,0,0,0.5); }
    .bell-container:hover .notif-dropdown { display: block; }
  </style>
  <script>
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
      // Default open
      document.getElementById("defaultOpen").click();
      
      // Polling AI Engine Metrics
      async function fetchAILiveMetrics() {
        try {
          const res = await fetch('/api/ai_live_metrics');
          const data = await res.json();
          const contentDiv = document.getElementById("aiMetricsContent");
          
          if (data.status === "AI Engine Starting..." || Object.keys(data).length === 0) {
              contentDiv.innerHTML = "<p style='grid-column: 1/-1; text-align: center;'>AI Engine Starting or Offline...</p>";
              return;
          }
          
          let htmlContent = "";
          for (const [threadName, status] of Object.entries(data)) {
              // Color code based on status
              let color = "var(--primary)";
              if (status.includes("Error")) color = "var(--danger)";
              else if (status.includes("Active") || status.includes("Monitoring")) color = "var(--success)";
              
              htmlContent += `
                <div class="metric-box" style="border-top: 3px solid ${color};">
                    <p style="margin:0; font-size: 0.9rem; color: #cbd5e1;">${threadName}</p>
                    <p class="metric-val" style="font-size: 1rem; color: ${color};">${status}</p>
                </div>
              `;
          }
          contentDiv.innerHTML = htmlContent;
        } catch (e) {
          console.error("Error fetching AI metrics:", e);
        }
      }
      
      // Polling Live Positions
      async function fetchPositions() {
        try {
          const res = await fetch('/api/positions');
          const data = await res.json();
          const tbody = document.getElementById("positionsTableBody");
          if (!tbody) return;
          
          if (!data || data.length === 0) {
             tbody.innerHTML = "<tr><td colspan='8' style='text-align:center; padding: 2rem; color: #cbd5e1;'>Waiting for live signals. No open positions currently in MT5.</td></tr>";
             return;
          }
          
          let html = "";
          data.forEach(pos => {
              const color = pos.profit >= 0 ? "var(--success)" : "var(--danger)";
              html += `<tr>
                  <td>${pos.symbol}</td>
                  <td>${pos.ticket}</td>
                  <td>${pos.type}</td>
                  <td>${pos.volume}</td>
                  <td>${pos.price_open}</td>
                  <td>${pos.price_current}</td>
                  <td><span style="color:${color}">${pos.profit}</span></td>
                  <td>${pos.comment}</td>
              </tr>`;
          });
          tbody.innerHTML = html;
        } catch (e) {
          console.error("Error fetching positions:", e);
        }
      }
      
      // Polling System Health
      async function fetchHealth() {
        try {
          const res = await fetch('/api/health');
          const data = await res.json();
          const el = document.getElementById("systemHealth");
          const bell = document.getElementById("bellIcon");
          const badge = document.getElementById("notifBadge");
          const msg = document.getElementById("notifMsg");
          
          if (el) {
              el.innerText = data.status;
              el.style.color = data.status.includes("CRITICAL") ? "var(--danger)" : "var(--success)";
          }
          
          if (data.status.includes("CRITICAL") || data.status.includes("OFFLINE")) {
              bell.classList.add("ringing");
              badge.style.display = "block";
              msg.innerHTML = `<span style='color:var(--danger)'><b>SYSTEM ALERT:</b> One or more bots are OFFLINE! Restart START_FOREX_SYSTEM.bat!</span>`;
          } else {
              bell.classList.remove("ringing");
              badge.style.display = "none";
              msg.innerHTML = `<span style='color:var(--success)'><b>All Systems Active & Healthy.</b> Waiting for market signals...</span>`;
          }
        } catch(e) {}
      }

      // Refresh every 1.5 seconds
      setInterval(() => {
          fetchAILiveMetrics();
          fetchPositions();
          fetchHealth();
      }, 1500);
      
      // Initial fetch
      fetchAILiveMetrics();
      fetchPositions();
      fetchHealth();
    });
  </script>
</head>
<body>
<div class="bell-container">
    <div id="bellIcon" class="bell-icon">🔔</div>
    <div id="notifBadge" class="notif-badge">!</div>
    <div class="notif-dropdown">
        <h4 style="margin-top:0; color:var(--primary); border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px;">System Alerts</h4>
        <p id="notifMsg" style="font-size: 0.9rem;">Monitoring...</p>
    </div>
</div>

<h1>AutomateON Forex AI Terminal</h1>
<div class="container">
  <div class="glass-panel">
    <h2>System Status</h2>
    <div class="status-grid">
      <div class="metric-box">
        <div>Telegram Engine</div>
        <div class="metric-val" style="color: var(--success)">✅ Connected & Active</div>
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
      <details open>
        <summary><span class="group-title">▶ LIVE TRADING POSITIONS</span><span class="group-pnl" style="color:var(--success)"></span></summary>
        <div class="details-content">
          <table class="table">
            <tr><th>Symbol</th><th>Ticket</th><th>Type</th><th>Volume</th><th>Entry Price</th><th>CMP</th><th>Open PnL</th><th>Comment</th></tr>
            <tbody id="positionsTableBody">
                <tr><td colspan="8" style="text-align:center; padding: 2rem; color: #cbd5e1;">Loading live positions...</td></tr>
            </tbody>
          </table>
        </div>
      </details>
    </div>

    <div id="Channels" class="tabcontent">
      <details open>
        <summary><span class="group-title">▶ ACTIVE TELEGRAM CHANNELS ({{ active_channel_count }} Sources)</span><span class="group-pnl"></span></summary>
        <div class="details-content">
          <table class="table">
            <tr><th>Channel Group</th><th>Status</th></tr>
            <tr><td>VIP Gold & Forex (15 Channels)</td><td><span style="color:var(--success)">Listening for Signals...</span></td></tr>
            <tr><td>VIP Crypto (10 Channels)</td><td><span style="color:var(--success)">Listening for Signals...</span></td></tr>
          </table>
        </div>
      </details>
    </div>
  </div>

  <div class="glass-panel full-width">
    <h2>Manual Execution Override</h2>
    <form method='post' action='/trade' class="btn-group">
      <button class='btn buy' type='submit' name='trade_cmd' value='BUY_GOLD'>BUY GOLD</button>
      <button class='btn sell' type='submit' name='trade_cmd' value='SELL_GOLD'>SELL GOLD</button>
      <button class='btn buy' type='submit' name='trade_cmd' value='BUY_EURUSD'>BUY EURUSD</button>
      <button class='btn sell' type='submit' name='trade_cmd' value='SELL_EURUSD'>SELL EURUSD</button>
      <button class='btn buy' type='submit' name='trade_cmd' value='BUY_BTCUSD'>BUY BTC</button>
      <button class='btn sell' type='submit' name='trade_cmd' value='SELL_BTCUSD'>SELL BTC</button>
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

  <!-- AI ENGINE LIVE METRICS PANEL -->
  <div class="glass-panel full-width">
    <h2>🤖 AI Engine Threads (Live Metrics)</h2>
    <div id="aiMetricsContent" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
      <p style="color:#cbd5e1">Loading AI Thread Status...</p>
    </div>
  </div>

  <!-- PROFESSIONAL CONTROL CENTER -->
  <div class="glass-panel full-width">
    <h2>⚙️ Mission Control (Panic & Master Switches)</h2>
    <div style="display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center; padding-top: 1rem;">
        <button class='btn sell' onclick="masterControl('kill_all_orders')" style="font-size:1.1rem; padding: 1rem 2rem; box-shadow: 0 4px 20px rgba(239, 68, 68, 0.6);">🚨 PANIC: CLOSE ALL OPEN ORDERS</button>
        <button class='btn' onclick="masterControl('toggle_engine')" style="background:#f59e0b; color:white; box-shadow: 0 4px 14px rgba(245, 158, 11, 0.4);">⏻ Toggle Core Engine Power</button>
        <button class='btn' onclick="masterControl('toggle_ai')" style="background:var(--secondary); color:white;">⏸ Toggle AI Strategies</button>
        <button class='btn' onclick="masterControl('toggle_telegram')" style="background:#8b5cf6; color:white;">⏸ Toggle Telegram Listener</button>
    </div>
    <p id="controlStatus" style="text-align:center; margin-top: 1rem; font-weight:bold; color:var(--primary);"></p>
    <div style="text-align:center; margin-top:1rem; font-size: 0.9rem;">System Monitor: <span id="systemHealth" style="font-weight:bold; color:var(--success);">Checking Health...</span></div>
  </div>

</div>

<script>
    async function masterControl(action) {
        try {
            const res = await fetch(`/api/control/${action}`, {method: 'POST'});
            const data = await res.json();
            document.getElementById('controlStatus').innerText = data.message;
        } catch(e) {
            document.getElementById('controlStatus').innerText = "Error executing command!";
        }
    }
</script>
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

import os
import time

@app.route('/api/positions')
def api_positions():
    try:
        path = BASE_DIR / "positions_status.json"
        if path.exists():
            with open(path, "r") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify([])

@app.route('/api/health')
def api_health():
    try:
        path_strat = BASE_DIR / "thread_status.json"
        path_tele = BASE_DIR / "telegram_status.json"
        
        # Check Local Ollama Heartbeat
        llm_status = "Local LLM: ❌ Offline"
        try:
            import httpx
            r = httpx.get("http://127.0.0.1:11434/", timeout=2)
            if r.status_code == 200:
                llm_status = "Local LLM: ✅ Online"
        except Exception:
            pass

        strat_ok = False
        if path_strat.exists():
            mtime = os.path.getmtime(path_strat)
            if (time.time() - mtime) < 60:
                strat_ok = True

        tele_ok = False
        if path_tele.exists():
            mtime = os.path.getmtime(path_tele)
            if (time.time() - mtime) < 60:
                tele_ok = True

        status_msg = f"{llm_status} | Strategy Bot: {'✅ Active' if strat_ok else '❌ OFFLINE'} | Telegram Bot: {'✅ Active' if tele_ok else '❌ OFFLINE'}"
        
        if not strat_ok or not tele_ok:
            return jsonify({"status": f"CRITICAL: {status_msg}"})
        else:
            return jsonify({"status": status_msg})
    except:
        pass
    return jsonify({"status": "Monitoring System..."})
@app.route('/api/ai_live_metrics')
def ai_live_metrics():
    try:
        with open("thread_status.json", "r") as f:
            status = json.load(f)
        return jsonify(status)
    except FileNotFoundError:
        return jsonify({"status": "AI Engine Starting..."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/control/<action>', methods=['POST'])
def master_control(action):
    control_file = BASE_DIR / "control_flags.json"
    
    # Initialize control file if missing
    if not control_file.exists():
        with open(control_file, "w") as f:
            json.dump({"ai_paused": False, "telegram_paused": False, "engine_running": True}, f)
            
    with open(control_file, "r") as f:
        flags = json.load(f)
        
    msg = ""
    if action == "kill_all_orders":
        ok, _ = init_mt5()
        if ok:
            positions = mt5.positions_get()
            if positions:
                for pos in positions:
                    tick = mt5.symbol_info_tick(pos.symbol)
                    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos.symbol,
                        "volume": pos.volume,
                        "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "position": pos.ticket,
                        "price": price,
                        "magic": pos.magic,
                        "comment": "PANIC_CLOSE",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    mt5.order_send(req)
            shutdown_mt5()
        msg = "🚨 All open positions closed via Panic Switch!"
    elif action == "toggle_engine":
        flags["engine_running"] = not flags.get("engine_running", True)
        msg = f"Core Engines are now {'RUNNING' if flags['engine_running'] else 'SHUT DOWN'}."
    elif action == "toggle_ai":
        flags["ai_paused"] = not flags["ai_paused"]
        msg = f"AI Strategies are now {'PAUSED' if flags['ai_paused'] else 'RUNNING'}."
    elif action == "toggle_telegram":
        flags["telegram_paused"] = not flags["telegram_paused"]
        msg = f"Telegram Engine is now {'PAUSED' if flags['telegram_paused'] else 'RUNNING'}."
        
    with open(control_file, "w") as f:
        json.dump(flags, f)
        
    return jsonify({"status": "success", "message": msg})

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
    positions_data = []
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
        # Fetch live positions
        raw_positions = mt5.positions_get()
        if raw_positions:
            for p in raw_positions:
                positions_data.append({
                    "symbol": p.symbol,
                    "ticket": p.ticket,
                    "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "price_current": p.price_current,
                    "profit": p.profit,
                    "comment": p.comment
                })
        shutdown_mt5()

    return render_template_string(HTML_TEMPLATE, telegram_status=telegram_status, active_sessions=session_str, logs=logs, mt5_stats=mt5_stats, positions=positions_data, active_channel_count=25)

# ------------------------------------------------------------
# Shutdown endpoint removed to prevent crash on refresh
# ------------------------------------------------------------

@app.route('/trade', methods=['GET', 'POST'])
def trade():
    if request.method == 'POST':
        trade_cmd = request.form.get('trade_cmd') # e.g. "BUY_GOLD"
        if not trade_cmd:
            return "Missing command", 400
        parts = trade_cmd.split('_')
        action = parts[0]
        symbol = parts[1]
    else:
        symbol = request.args.get('symbol')
        action = request.args.get('action')
        
    ok, err = init_mt5()
    if not ok:
        return f"MT5 init failed: {err}", 500
        
    # Make sure symbol is available in Market Watch
    mt5.symbol_select(symbol, True)
        
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
    from waitress import serve
    print("[SUCCESS] Production WSGI Server (Waitress) is LIVE and running on http://127.0.0.1:5000")
    print("Access the dashboard in your web browser.")
    # Run on localhost:5000 using Waitress (Production WSGI Server)
    serve(app, host='127.0.0.1', port=5000)
