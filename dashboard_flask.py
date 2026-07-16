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
    import unicodedata
    mapping = {}
    
    FOREX_GOLD_VIPS = [
        "scalping gold", "goldsnipers11", "sureshot fx", "sureshot gold", 
        "gold trade signals", "easy forex", "gold trader", "global gold insight",
        "global profit club", "gold_mast78", "forexero", "forexking1132",
        "xauusd signal 99%", "josefina trader", "forex trading master",
        "gold sniper pips", "messy forex", "forex trading tips", "rasrasanforex",
        "riaogoldforex", "gold snipers", "michael gold trader", "grade profit forex",
        "forex market", "gold dreams trader", "xau profit zone", "saviour gold ea",
        "culersforex", "global profit culb", "gold scalper", "victory forex", 
        "source fx hub", "mr.david, xau/usd club", "gold fx network",
        "dubai capital fx group 3", "onyx alpha trades", "xauusd accurate signals",
        "mrgoldenway trader", "vip-mrgoldencircle", "max leverage"
    ]

    CRYPTO_VIPS = [
        "market trader crypto", "coin chief", "binance killers", "crypto world updates",
        "binance 360", "dil se trader crypto", "cryptosimplicity", "crypto radar",
        "king crypto scalp", "earlypumpdetector"
    ]
    
    all_vips = set([v.lower() for v in FOREX_GOLD_VIPS + CRYPTO_VIPS])

    def _read(p: Path):
        if not p.exists(): return
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                parts = line.split("|")
                if len(parts) != 2: continue
                cid = parts[0].strip().lstrip("-")
                name = parts[1].strip()
                
                normalized_name = unicodedata.normalize('NFKC', name).lower()
                for vip in all_vips:
                    if vip in normalized_name:
                        mapping[cid] = name
                        break
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
    # OLLAMA LOCAL AI INTEGRATION (Zero Latency, Zero Cost)
    endpoint = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    try:
        resp = httpx.post(endpoint, json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except Exception as e:
        logging.error(f"Ollama failed, ensure Ollama is running. Error: {e}")
        return '{"action": "NO_TRADE", "error": "Ollama Offline"}'

def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading AI. Extract trade data from channel '{channel_name}'.\n"
        f"Return ONLY a raw JSON object (no markdown, no backticks, no other text) with keys: action, symbol, entry, tp, sl.\n"
        f"If not a signal, return {{\"action\": \"NO_TRADE\"}}. Gold symbols (XAUUSD, XAU) must be \"GOLD\".\n"
        f"Message:\n{message}"
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
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Swarm Trading OS | Terminal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-color: #0b0f19;
      --panel-bg: rgba(17, 24, 39, 0.7);
      --panel-border: rgba(255, 255, 255, 0.08);
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent-blue: #3b82f6;
      --accent-blue-glow: rgba(59, 130, 246, 0.4);
      --accent-green: #10b981;
      --accent-green-glow: rgba(16, 185, 129, 0.4);
      --accent-red: #ef4444;
      --accent-red-glow: rgba(239, 68, 68, 0.4);
      --accent-purple: #8b5cf6;
      --accent-purple-glow: rgba(139, 92, 246, 0.4);
    }
    
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      font-family: 'Outfit', sans-serif;
      background-color: var(--bg-color);
      color: var(--text-main);
      min-height: 100vh;
      background-image: 
        radial-gradient(circle at 15% 50%, rgba(59, 130, 246, 0.08), transparent 25%), 
        radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.08), transparent 25%);
      background-attachment: fixed;
      padding: 2rem;
    }

    /* Typography */
    h1 {
      font-size: 2.5rem;
      font-weight: 800;
      text-align: center;
      margin-bottom: 2rem;
      letter-spacing: -0.5px;
      background: linear-gradient(to right, #60a5fa, #a78bfa);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: pulseGlow 4s infinite alternate;
    }
    @keyframes pulseGlow {
      0% { filter: drop-shadow(0 0 10px rgba(96, 165, 250, 0.2)); }
      100% { filter: drop-shadow(0 0 20px rgba(167, 139, 250, 0.4)); }
    }
    h2 { font-size: 1.2rem; font-weight: 600; color: #fff; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
    h2::before { content: ""; display: block; width: 4px; height: 1.2rem; background: var(--accent-blue); border-radius: 2px; }

    /* Layout */
    .container {
      max-width: 1400px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 1.5rem;
    }
    .col-4 { grid-column: span 4; }
    .col-6 { grid-column: span 6; }
    .col-8 { grid-column: span 8; }
    .col-12 { grid-column: span 12; }

    @media (max-width: 1024px) {
      .col-4, .col-6, .col-8 { grid-column: span 12; }
    }

    /* Panels */
    .panel {
      background: var(--panel-bg);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--panel-border);
      border-radius: 16px;
      padding: 1.5rem;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .panel:hover {
      transform: translateY(-2px);
      border-color: rgba(255, 255, 255, 0.15);
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3);
    }

    /* Metric Cards */
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem; }
    .metric-card {
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      justify-content: center;
      position: relative;
      overflow: hidden;
    }
    .metric-card::after {
      content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
      background: linear-gradient(90deg, transparent, var(--accent-blue), transparent);
      opacity: 0; transition: opacity 0.3s;
    }
    .metric-card:hover::after { opacity: 1; }
    .metric-label { font-size: 0.85rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem; }
    .metric-val { font-size: 1.5rem; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
    .metric-val.green { color: var(--accent-green); text-shadow: 0 0 10px var(--accent-green-glow); }
    .metric-val.blue { color: var(--accent-blue); text-shadow: 0 0 10px var(--accent-blue-glow); }
    
    /* Tables */
    .table-container { width: 100%; overflow-x: auto; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.95rem; }
    th { text-align: left; padding: 1rem; color: var(--text-muted); font-weight: 600; font-size: 0.85rem; text-transform: uppercase; border-bottom: 1px solid var(--panel-border); }
    td { padding: 1rem; border-bottom: 1px solid rgba(255,255,255,0.03); font-family: 'JetBrains Mono', monospace; font-weight: 400; }
    tr:hover td { background: rgba(255,255,255,0.02); }
    tr:last-child td { border-bottom: none; }
    
    .badge { padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge.buy { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge.sell { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.3); }

    /* Tabs CSS */
    .tab { overflow: hidden; border-bottom: 1px solid var(--panel-border); margin-bottom: 1rem; }
    .tab button { background-color: inherit; float: left; border: none; outline: none; cursor: pointer; padding: 14px 24px; transition: 0.3s; font-size: 1.1rem; font-weight: 600; color: var(--text-muted); border-radius: 8px 8px 0 0; font-family: 'Outfit', sans-serif;}
    .tab button:hover { background-color: rgba(255, 255, 255, 0.05); color: var(--text-main); }
    .tab button.active { color: var(--accent-blue); border-bottom: 3px solid var(--accent-blue); background-color: rgba(0, 0, 0, 0.2); }
    .tabcontent { display: none; padding: 6px 12px; animation: fadeEffect 0.5s; }
    @keyframes fadeEffect { from {opacity: 0;} to {opacity: 1;} }
    
    .metric-val.red { color: var(--accent-red); text-shadow: 0 0 10px var(--accent-red-glow); }

    /* Buttons */
    .btn-group { display: flex; gap: 0.75rem; flex-wrap: wrap; }
    .btn {
      padding: 0.75rem 1.5rem;
      border-radius: 8px;
      font-family: 'Outfit', sans-serif;
      font-weight: 600;
      font-size: 0.9rem;
      cursor: pointer;
      border: none;
      transition: all 0.2s ease;
      position: relative;
      overflow: hidden;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: white;
    }
    .btn::before {
      content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      background: linear-gradient(rgba(255,255,255,0.1), transparent); opacity: 0; transition: opacity 0.2s;
    }
    .btn:hover::before { opacity: 1; }
    .btn:active { transform: scale(0.97); }
    
    .btn-primary { background: var(--accent-blue); box-shadow: 0 4px 15px var(--accent-blue-glow); }
    .btn-success { background: var(--accent-green); box-shadow: 0 4px 15px var(--accent-green-glow); }
    .btn-danger { background: var(--accent-red); box-shadow: 0 4px 15px var(--accent-red-glow); }
    .btn-warning { background: #f59e0b; box-shadow: 0 4px 15px rgba(245, 158, 11, 0.4); }

    /* Logs & Scrollbars */
    .log-container { max-height: 300px; overflow-y: auto; padding-right: 0.5rem; }
    .log-item { background: rgba(0,0,0,0.3); border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; border-left: 3px solid var(--accent-purple); font-size: 0.9rem; }
    .log-item span.highlight { color: var(--accent-blue); font-family: 'JetBrains Mono', monospace; font-weight: 600;}
    
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 4px; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

    /* Status Indicator */
    .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; box-shadow: 0 0 8px currentColor; }
    .status-dot.online { color: var(--accent-green); background: var(--accent-green); animation: blink 2s infinite; }
    .status-dot.offline { color: var(--accent-red); background: var(--accent-red); }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    
    /* Header Bar */
    .header-bar { position: relative; z-index: 9999; display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; background: var(--panel-bg); border: 1px solid var(--panel-border); padding: 1rem 2rem; border-radius: 16px; backdrop-filter: blur(12px); box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    .sys-health { font-size: 0.9rem; font-weight: 600; display: flex; align-items: center; gap: 1.5rem; }
  
    .bell-icon { position: relative; cursor: pointer; display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,0.05); transition: background 0.3s; }
    .bell-icon:hover { background: rgba(255,255,255,0.1); }
    .bell-badge { position: absolute; top: 5px; right: 5px; width: 10px; height: 10px; background: var(--accent-red); border-radius: 50%; box-shadow: 0 0 8px var(--accent-red-glow); animation: pulse 1.5s infinite; display: none; }
    .alerts-dropdown { position: absolute; top: 60px; right: 20px; width: 350px; max-height: 400px; background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); z-index: 1000; overflow-y: auto; display: none; flex-direction: column; }
    .alert-item { padding: 12px 15px; border-bottom: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 5px; }
    .alert-item:last-child { border-bottom: none; }
    .alert-time { font-size: 0.8rem; color: var(--text-muted); }
    .alert-msg { font-size: 0.95rem; color: #fff; }
    .alert-crit { border-left: 3px solid var(--accent-red); }
    .alert-warn { border-left: 3px solid var(--accent-yellow); }
    .alert-clear { padding: 10px; text-align: center; cursor: pointer; background: rgba(255,255,255,0.02); font-weight: bold; color: var(--accent-blue); }
    .alert-clear:hover { background: rgba(255,255,255,0.05); }
    </style>

  <script>
    
    function openTelegramTab(evt, tabName) {
      var i, tabcontent, tablinks;
      tabcontent = document.getElementsByClassName("tele-tabcontent");
      for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
      }
      tablinks = document.getElementsByClassName("tele-tablinks");
      for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
      }
      document.getElementById(tabName).style.display = "block";
      evt.currentTarget.className += " active";
    }


    let alertCount = 0;
    window.toggleAlerts = function() {
        const el = document.getElementById('alertsDropdown');
        el.style.display = el.style.display === 'flex' ? 'none' : 'flex';
        if(el.style.display === 'flex') {
            document.getElementById('bellBadge').style.display = 'none';
        }
    };
    
    window.clearAlerts = async function() {
        try {
            await fetch('/api/alerts/clear', {method: 'POST'});
            document.getElementById('alertsDropdown').innerHTML = '<div style="padding:15px; text-align:center; color:var(--text-muted);">No new alerts</div>';
            document.getElementById('bellBadge').style.display = 'none';
        } catch(e) {}
    };
    
    async function fetchAlerts() {
        try {
            const res = await fetch('/api/alerts');
            const data = await res.json();
            if(data.length > 0 && data.length !== alertCount) {
                alertCount = data.length;
                const drop = document.getElementById('alertsDropdown');
                if (drop.style.display !== 'flex') {
                    document.getElementById('bellBadge').style.display = 'block';
                }
                let html = '';
                [...data].reverse().forEach(alert => {
                    const cls = alert.level === 'CRITICAL' ? 'alert-crit' : 'alert-warn';
                    const color = alert.level === 'CRITICAL' ? 'var(--accent-red)' : 'var(--accent-yellow)';
                    html += `<div class="alert-item ${cls}">
                        <div style="display:flex; justify-content:space-between;">
                            <span style="font-weight:bold; color:${color}; font-size:0.85rem;">${alert.source}</span>
                            <span class="alert-time">${alert.timestamp}</span>
                        </div>
                        <div class="alert-msg">${alert.message}</div>
                    </div>`;
                });
                html += `<div class="alert-clear" onclick="clearAlerts()">Clear All</div>`;
                drop.innerHTML = html;
            } else if (data.length === 0) {
                alertCount = 0;
                document.getElementById('alertsDropdown').innerHTML = '<div style="padding:15px; text-align:center; color:var(--text-muted);">No new alerts</div>';
                document.getElementById('bellBadge').style.display = 'none';
            }
        } catch(e) {}
    }

    document.addEventListener("DOMContentLoaded", function() {
      if(document.getElementById("defaultTeleOpen")) {
          document.getElementById("defaultTeleOpen").click();
      }
      
      const startTime = Date.now();


      setInterval(() => {

          const now = new Date();
          document.getElementById('realTimeClock').innerText = now.toLocaleTimeString('en-US', { hour12: false });
          
          const elapsed = Math.floor((Date.now() - startTime) / 1000);
          const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
          const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
          const s = String(elapsed % 60).padStart(2, '0');
          document.getElementById('elapsedTime').innerText = `${h}:${m}:${s}`;
      }, 1000);

      
      async function fetchAILiveMetrics() {
        try {
          const res = await fetch('/api/ai_live_metrics');
          const data = await res.json();
          const contentDiv = document.getElementById("aiMetricsContent");
          
          if (data.status === "AI Engine Starting..." || Object.keys(data).length === 0) {
              contentDiv.innerHTML = "<p style='color: var(--text-muted); text-align: center; width: 100%;'>AI Engine Starting or Offline...</p>";
              return;
          }
          
          let htmlContent = "";
          for (const [threadName, status] of Object.entries(data)) {
              let color = "var(--accent-blue)";
              let shadow = "var(--accent-blue-glow)";
              if (status.includes("Error")) { color = "var(--accent-red)"; shadow = "var(--accent-red-glow)"; }
              else if (status.includes("Active") || status.includes("Monitoring")) { color = "var(--accent-green)"; shadow = "var(--accent-green-glow)"; }
              
              htmlContent += `
                <div class="metric-card" style="border-bottom: 2px solid ${color};">
                    <div class="metric-label">${threadName}</div>
                    <div class="metric-val" style="font-size: 1rem; color: ${color}; text-shadow: 0 0 10px ${shadow}; font-family: 'Outfit', sans-serif;">${status}</div>
                </div>
              `;
          }
          contentDiv.innerHTML = htmlContent;
        } catch (e) { }
      }
      
      async function fetchPositions() {
        try {
          const res = await fetch('/api/positions');
          const data = await res.json();
          const tbody = document.getElementById("positionsTableBody");
          if (!tbody) return;
          
          if (!data || data.length === 0) {
             tbody.innerHTML = "<tr><td colspan='8' style='text-align:center; padding: 3rem; color: var(--text-muted);'>No active market positions. Hunting for signals...</td></tr>";
             return;
          }
          
          let html = "";
          data.forEach(pos => {
              const color = pos.profit >= 0 ? "var(--accent-green)" : "var(--accent-red)";
              const glow = pos.profit >= 0 ? "var(--accent-green-glow)" : "var(--accent-red-glow)";
              const badgeCls = pos.type === "BUY" ? "buy" : "sell";
              html += `<tr>
                  <td style="font-weight: 700; color: #fff;">${pos.symbol}</td>
                  <td style="color: var(--text-muted)">#${pos.ticket}</td>
                  <td><span class="badge ${badgeCls}">${pos.type}</span></td>
                  <td>${pos.volume}</td>
                  <td>${pos.price_open}</td>
                  <td>${pos.price_current}</td>
                  <td style="color:${color}; text-shadow: 0 0 10px ${glow}; font-weight: 700;">${pos.profit >= 0 ? '+' : ''}${pos.profit.toFixed(2)}</td>
                  <td style="font-size: 0.85rem; color: var(--accent-purple)">${pos.comment}</td>
              </tr>`;
          });
          tbody.innerHTML = html;
          tbody.innerHTML = html;
          // Realized PNL is calculated in fetchStrategyPnl

          let totalRunning = 0;
          data.forEach(pos => { totalRunning += pos.profit; });
          const rpnlEl = document.getElementById('runningPnlMetric');
          if (rpnlEl) {
              rpnlEl.innerText = (totalRunning >= 0 ? "+$" : "-$") + Math.abs(totalRunning).toFixed(2);
              rpnlEl.className = "metric-val " + (totalRunning >= 0 ? "green" : "red");
          }

        } catch (e) { }
      }
      
      async function fetchStrategyPnl() {
        try {
          const res = await fetch('/api/strategy_pnl');
          const data = await res.json();
          const tbody = document.getElementById("strategyPnlTableBody");
          if (!tbody) return;
          
          if (!data || Object.keys(data).length === 0) {
             tbody.innerHTML = "<tr><td colspan='4' style='text-align:center; padding: 2rem; color: var(--text-muted);'>No closed trades today.</td></tr>";
             return;
          }
          
          let totalRealized = 0;
          let html = "";
          for (const [strat, stats] of Object.entries(data)) {
              const pnl = parseFloat(stats.pnl) || 0;
              totalRealized += pnl;
              const color = pnl >= 0 ? "var(--accent-green)" : "var(--accent-red)";
              const glow = pnl >= 0 ? "var(--accent-green-glow)" : "var(--accent-red-glow)";
              html += `<tr>
                  <td style="color: var(--accent-blue); font-weight: 600; font-family: 'Outfit', sans-serif;">${strat}</td>
                  <td>${stats.trades}</td>
                  <td>${stats.win_rate}</td>
                  <td style="color:${color}; text-shadow: 0 0 10px ${glow}; font-weight: 700;">$${pnl.toFixed(2)}</td>
              </tr>`;
          }
          tbody.innerHTML = html;
          
          const repnlEl = document.getElementById('realizedPnlMetric');
          if (repnlEl) {
              repnlEl.innerText = (totalRealized >= 0 ? "+$" : "-$") + Math.abs(totalRealized).toFixed(2);
              repnlEl.className = "metric-val " + (totalRealized >= 0 ? "green" : "red");
          }
        } catch (e) { }
      }

      async function fetchLogs() {
          try {
              const res = await fetch('/api/logs');
              const data = await res.json();
              const posRes = await fetch('/api/positions');
              const posData = await posRes.json();
              updateChannelTable(data, posData);
          } catch (e) {}
      }

      async function updateChannelTable(logs, positions) {
            if (!logs) return;
            
            const groupedLogs = {};
            logs.forEach(log => {
                if (!groupedLogs[log.channel_name]) {
                    groupedLogs[log.channel_name] = [];
                }
                groupedLogs[log.channel_name].push(log);
            });

            const table = document.getElementById("channelTable");
            const trs = table.getElementsByTagName("tr");
            
            for (let i = 0; i < trs.length; i++) {
                const tr = trs[i];
                if (!tr.id || !tr.id.startsWith("row_")) continue;
                const cid = tr.id.replace("row_", "");
                
                let channelLogs = null;
                for (const [key, val] of Object.entries(groupedLogs)) {
                    if (tr.innerHTML.includes(key)) {
                        channelLogs = val;
                        break;
                    }
                }
                
                if (channelLogs && channelLogs.length > 0) {
                    channelLogs.sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));
                    
                    const latest = channelLogs[0];
                    let aiParsed;
                    try { aiParsed = JSON.parse(latest.ai_reply); } catch(e) { aiParsed = {action: "ERROR"}; }
                    
                    let latestActionHtml = "-";
                    let latestPricesHtml = "-";
                    if (aiParsed.action && aiParsed.action !== "NO_TRADE" && aiParsed.action !== "ERROR") {
                        latestActionHtml = `<span class="badge ${aiParsed.action.toLowerCase().replace(' ', '-')}">${aiParsed.action}</span> <b>${aiParsed.symbol}</b>`;
                        latestPricesHtml = `<span style="color:var(--text-muted)">E:</span> ${aiParsed.entry || '-'} | <span style="color:var(--accent-green)">TP:</span> ${aiParsed.final_tp1 || aiParsed.tp1 || aiParsed.tp || '-'} | <span style="color:var(--accent-red)">SL:</span> ${aiParsed.final_sl || aiParsed.sl || '-'}`;
                    } else if (aiParsed.action === "NO_TRADE") {
                        latestActionHtml = "NO_TRADE";
                    }
                    
                    let htmlAnalysis = `<div style="margin-bottom:5px;">${latest.message}</div>`;
                    
                    if (channelLogs.length > 1) {
                        htmlAnalysis += `<button onclick="const el = document.getElementById('hist_${cid}'); el.style.display = el.style.display === 'none' ? 'block' : 'none'" style="background:var(--panel-bg); color:var(--accent-blue); border:1px solid var(--border-color); padding:2px 8px; border-radius:4px; cursor:pointer; font-size:0.8rem; margin-top:5px;">Show ${channelLogs.length - 1} Older Messages ▼</button>`;
                        
                        htmlAnalysis += `<div id="hist_${cid}" style="display:none; margin-top:10px; padding:10px; background:rgba(0,0,0,0.2); border-left:2px solid var(--accent-blue); border-radius:4px; font-size:0.9rem; max-height:200px; overflow-y:auto;">`;
                        
                        for (let j = 1; j < channelLogs.length; j++) {
                            const old = channelLogs[j];
                            let oldParsed;
                            try { oldParsed = JSON.parse(old.ai_reply); } catch(e) { oldParsed = {action: "ERROR"}; }
                            let oldAct = "-";
                            let oldPrc = "-";
                            if (oldParsed.action && oldParsed.action !== "NO_TRADE" && oldParsed.action !== "ERROR") {
                                oldAct = `<span style="color:#aaa;">[${old.timestamp}]</span> <span class="badge ${oldParsed.action.toLowerCase().replace(' ', '-')}">${oldParsed.action}</span> <b>${oldParsed.symbol}</b>`;
                                oldPrc = `E: ${oldParsed.entry || '-'} | TP: ${oldParsed.final_tp1 || oldParsed.tp1 || oldParsed.tp || '-'} | SL: ${oldParsed.final_sl || oldParsed.sl || '-'}`;
                            } else {
                                oldAct = `<span style="color:#aaa;">[${old.timestamp}]</span> NO_TRADE`;
                            }
                            htmlAnalysis += `<div style="margin-bottom:8px; padding-bottom:8px; border-bottom:1px solid var(--border-color);">
                                <div style="color:#ccc; font-style:italic;">"${old.message.substring(0, 150)}..."</div>
                                <div style="margin-top:4px;">${oldAct} &rarr; <span style="font-size:0.85rem; color:var(--accent-purple);">${oldPrc}</span></div>
                            </div>`;
                        }
                        htmlAnalysis += `</div>`;
                    }
                    
                    document.getElementById("analysis_" + cid).innerHTML = htmlAnalysis;
                    document.getElementById("action_" + cid).innerHTML = latestActionHtml;
                    document.getElementById("prices_" + cid).innerHTML = latestPricesHtml;
                    document.getElementById("time_" + cid).innerText = latest.timestamp || new Date().toLocaleTimeString();
                    
                    const profitTd = document.getElementById("profit_" + cid);
                    let foundPos = false;
                    if(positions) {
                        positions.forEach(pos => {
                            if (pos.comment === latest.channel_name || pos.symbol === aiParsed.symbol) {
                                const color = pos.profit >= 0 ? "var(--accent-green)" : "var(--accent-red)";
                                profitTd.innerHTML = `<span style="color:${color}; font-weight:bold;">$${pos.profit.toFixed(2)}</span>`;
                                foundPos = true;
                            }
                        });
                    }
                    if(!foundPos) profitTd.innerText = "Closed / No Active";
                }
            }
        }

      async function fetchHealth() {
        try {
          const res = await fetch('/api/health');
          const data = await res.json();
          const el = document.getElementById("systemHealth");
          
          if (el) {
              const isCrit = data.status.includes("CRITICAL") || data.status.includes("OFFLINE");
              const dotClass = isCrit ? "offline" : "online";
              el.innerHTML = `<span class="status-dot ${dotClass}"></span> ${data.status}`;
          }
        } catch(e) {}
      }



      setInterval(() => {

          fetchAILiveMetrics();
          fetchPositions();
          fetchHealth();
          fetchStrategyPnl();

          fetchLogs();
          fetchAlerts();

      }, 1500);
      
      fetchAILiveMetrics();
      fetchPositions();
      fetchHealth();
      fetchStrategyPnl();
    });
    
    async function masterControl(action) {
        try {
            const res = await fetch(`/api/control/${action}`, {method: 'POST'});
            const data = await res.json();
            alert(data.message);
        } catch(e) {
            alert("Error executing command!");
        }
    }
  </script>
</head>
<body>

<div class="header-bar">
    <div style="display: flex; align-items: center; gap: 1rem;">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="url(#blue-gradient)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <defs>
                <linearGradient id="blue-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#3b82f6" />
                    <stop offset="100%" stop-color="#8b5cf6" />
                </linearGradient>
            </defs>
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
        <h1 style="margin: 0; font-size: 1.8rem;">Swarm OS</h1>
    </div>

    <div style="display:flex; align-items:center; gap: 1rem;">
        <div class="bell-icon" onclick="toggleAlerts()">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
            <div class="bell-badge" id="bellBadge"></div>
        </div>
        <div class="sys-health" id="systemHealth">
            <span class="status-dot online"></span> Checking Health...
        </div>
    </div>
    
    <div class="alerts-dropdown" id="alertsDropdown">
        <!-- Alerts will be injected here -->
    </div>
</div>


<div class="container">
  
  <!-- MT5 Account Data -->
  <div class="panel col-4">
    <h2>MT5 Wallet</h2>
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-label">Balance</div>
        <div class="metric-val blue">${{ mt5_stats.balance }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Equity</div>
        <div class="metric-val green">${{ mt5_stats.equity }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Free Margin</div>
        <div class="metric-val">${{ mt5_stats.margin_free }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Margin Level</div>
        <div class="metric-val">{{ mt5_stats.margin_level }}%</div>
      </div>
    </div>
  </div>

  <!-- Operations Controls -->
  <div class="panel col-8">
    <h2>Mission Control</h2>
    <div class="metric-grid" style="margin-bottom: 1rem;">
      <div class="metric-card" style="padding: 0.5rem 1rem;">
        <div class="metric-label" style="font-size: 0.7rem;">Market Status</div>
        <div class="metric-val" style="font-size: 1rem; color:var(--accent-green)">{{ active_sessions }}</div>
      </div>
      <div class="metric-card" style="padding: 0.5rem 1rem;">
        <div class="metric-label" style="font-size: 0.7rem;">Telegram Connect</div>
        <div class="metric-val" style="font-size: 1rem;">{{ telegram_status }}</div>
      </div>
      <div class="metric-card" style="padding: 0.5rem 1rem;">
        <div class="metric-label" style="font-size: 0.7rem;">Uptime</div>
        <div class="metric-val" id="elapsedTime" style="font-size: 1rem; color:var(--accent-blue)">00:00:00</div>
      </div>
      <div class="metric-card" style="padding: 0.5rem 1rem;">
        <div class="metric-label" style="font-size: 0.7rem;">Local Time</div>
        <div class="metric-val" id="realTimeClock" style="font-size: 1rem;">00:00:00</div>
      </div>
    </div>
    <div class="btn-group" style="margin-top: 1rem;">
        <button class='btn btn-danger' onclick="masterControl('kill_all_orders')" style="flex: 1; padding: 1rem; font-size: 1rem;">🚨 PANIC: CLOSE ALL OPEN ORDERS</button>
    </div>
    <div class="btn-group" style="margin-top: 1rem;">
        <button class='btn btn-warning' onclick="masterControl('toggle_engine')" style="flex: 1;">⏻ Toggle Core Engine</button>
        <button class='btn btn-primary' onclick="masterControl('toggle_ai')" style="flex: 1;">⏸ Toggle AI Strategies</button>
        <button class='btn btn-primary' style="background: var(--accent-purple); box-shadow: 0 4px 15px var(--accent-purple-glow); flex: 1;" onclick="masterControl('toggle_telegram')">⏸ Toggle Telegram Listener</button>
    </div>
  </div>

  <!-- Live Positions -->
  <div class="panel col-12">
    <div style="display:flex; justify-content: space-between; align-items: flex-end; margin-bottom: 1rem;">
        <h2 style="margin: 0;">Live Algorithmic Positions</h2>
        <div style="display: flex; gap: 1rem;">
            <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 0.5rem 1rem; text-align: center;">
                <div class="metric-label" style="font-size: 0.7rem; margin:0;">Running P&L</div>
                <div id="runningPnlMetric" class="metric-val" style="font-size: 1.2rem;">$0.00</div>
            </div>
            <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 0.5rem 1rem; text-align: center;">
                <div class="metric-label" style="font-size: 0.7rem; margin:0;">Realized P&L</div>
                <div id="realizedPnlMetric" class="metric-val" style="font-size: 1.2rem;">$0.00</div>
            </div>
        </div>
    </div>
    <div class="table-container">
      <table>
        <thead>
            <tr><th>Symbol</th><th>Ticket</th><th>Type</th><th>Volume</th><th>Entry Price</th><th>CMP</th><th>Open PnL</th><th>Strategy</th></tr>
        </thead>
        <tbody id="positionsTableBody">
            <tr><td colspan="8" style="text-align:center; padding: 3rem; color: var(--text-muted);">Initializing Engine...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Strategy PnL -->
  <div class="panel col-6">
    <h2>Today's Realized P&L (By Strategy)</h2>
    <div class="table-container">
      <table>
        <thead>
            <tr><th>Strategy</th><th>Trades</th><th>Win Rate</th><th>Net P&L</th></tr>
        </thead>
        <tbody id="strategyPnlTableBody">
            <tr><td colspan="4" style="text-align:center; padding: 2rem; color: var(--text-muted);">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- AI Thread Metrics -->
  <div class="panel col-6">
    <h2>AI Engine Diagnostics</h2>
    <div id="aiMetricsContent" class="metric-grid">
      <p style="color: var(--text-muted); text-align: center; width: 100%;">Loading AI Thread Status...</p>
    </div>
  </div>
  
  <!-- Telegram AI Logs -->
  <div class="panel col-12">
    <div class="tab">
      <button class="tele-tablinks active" onclick="openTelegramTab(event, 'TeleStream')" id="defaultTeleOpen">AI Parsing Stream</button>
      <button class="tele-tablinks" onclick="openTelegramTab(event, 'TeleChannels')">Active Channels</button>
    </div>

    <div id="TeleStream" class="tele-tabcontent" style="display: block;">
        <div class="log-container">
        {% if logs %}
          {% for entry in logs %}
            <div class="log-item">
               <div style="display:flex; justify-content: space-between; margin-bottom: 0.5rem;">
                   <span style="font-weight: 600; color: #fff;">{{ entry.channel_name }}</span>
                   <span class="badge {{ 'buy' if 'Success' in entry.order_status else 'sell' }}">{{ entry.order_status }}</span>
               </div>
               <p style="color: var(--text-muted); margin-bottom: 0.5rem;">{{ entry.message|truncate(120) }}</p>
               <p>AI Output: <span class="highlight">{{ entry.ai_reply }}</span></p>
               {% if entry.error_msg %}<p style="color: var(--accent-red); margin-top: 0.25rem;">Err: {{ entry.error_msg }}</p>{% endif %}
            </div>
          {% endfor %}
        {% else %}
          <p style="color: var(--text-muted); text-align: center; padding: 2rem;">Listening for VIP signals on Telegram network...</p>
        {% endif %}
        </div>
    </div>
    
    <div id="TeleChannels" class="tele-tabcontent">
        <div class="table-container" style="max-height: 500px; overflow-y: auto;">
          <table id="channelTable">
            <thead style="position: sticky; top: 0; background: var(--panel-bg); z-index: 10;">
                <tr>
                    <th>Telegram Name / ID</th>
                    <th>Signal Analysis (Ollama)</th>
                    <th>Action & Symbol</th>
                    <th>Buy Entry | TP | SL</th>
                    <th>Profit Running</th>
                    <th>Timestamp</th>
                </tr>
            </thead>
            <tbody>
                {% for cid, name in channel_map.items() %}
                <tr id="row_{{ cid }}">
                    <td>
                        <div style="color:var(--accent-blue); font-weight:600; font-family:'Outfit', sans-serif;">{{ name }}</div>
                        <div style="color:var(--text-muted); font-size: 0.75rem;">{{ cid }}</div>
                    </td>
                    <td id="analysis_{{ cid }}" style="color:var(--text-muted); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">Awaiting Signal...</td>
                    <td id="action_{{ cid }}">-</td>
                    <td id="prices_{{ cid }}">-</td>
                    <td id="profit_{{ cid }}">-</td>
                    <td id="time_{{ cid }}">-</td>
                </tr>
                {% endfor %}
            </tbody>
          </table>
        </div>
    </div>
  </div>

</div>

</body>
</html>
"""

def get_telegram_status():
    status_file = BASE_DIR / "telegram_status.json"
    if status_file.exists():
        try:
            import json, time
            from pathlib import Path
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return True if data.get("status") in ["Running", "Active"] else "Stopped"
        except Exception as e:
            return str(e)
    return "Unknown" 

import os
import time


@app.route('/api/alerts')
def api_alerts():
    try:
        path = BASE_DIR / "alerts.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify([])

@app.route('/api/alerts/clear', methods=['POST'])
def api_alerts_clear():
    try:
        path = BASE_DIR / "alerts.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
        return jsonify({"status": "success"})
    except Exception:
        return jsonify({"status": "error"}), 500

@app.route('/api/logs')
def api_logs():
    try:
        path = BASE_DIR / "message_ai_log.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f)[-200:])
    except Exception:
        pass
    return jsonify([])

@app.route('/api/strategy_pnl')
def api_strategy_pnl():
    try:
        path = BASE_DIR / "strategy_pnl_today.json"
        if path.exists():
            with open(path, "r") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({})

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
    channel_map = load_channel_map()
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

    return render_template_string(HTML_TEMPLATE, telegram_status=telegram_status, active_sessions=session_str, logs=logs, mt5_stats=mt5_stats, positions=positions_data, active_channel_count=len(channel_map), channel_map=channel_map)

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
    ticket = None
    err = "Unknown"
    try:
        parsed = json.loads(ai_reply)
        action = parsed.get("action", "NO_TRADE").upper()
        if action != "NO_TRADE" and action != "ERROR":
            symbol = parsed.get("symbol", "").upper()
            if symbol in ["XAUUSD", "XAU", "XAU/USD"]: symbol = "GOLD"
            try:
                entry_price = float(parsed.get("entry", 1.0))
            except:
                entry_price = 1.0
            lot = 0.01 if is_forex(symbol) else lot_for_crypto(entry_price)
            ok, err = init_mt5()
            if ok:
                ticket, err = place_order(symbol, action, lot)
                shutdown_mt5()
    except Exception as parse_e:
        err = f"JSON Parse error: {parse_e}"
        
    # Append to log file for dashboard visibility
    log_path = BASE_DIR / "message_ai_log.json"
    entry = {
        "channel_name": channel,
        "message": msg,
        "ai_reply": ai_reply,
        "order_status": "Success" if ticket else "Failed" if action != "NO_TRADE" else "Ignored",
        "error_msg": err if not ticket and action != "NO_TRADE" else None,
        "ticket": ticket if ticket else None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    serve(app, host='127.0.0.1', port=5000, threads=1)
