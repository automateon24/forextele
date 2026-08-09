import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update build_prompt to ask for JSON
prompt_find = """def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading assistant. The following Telegram message came from channel '{channel_name}'.\\n"
        f"If it contains a real BUY/SELL signal, reply with exactly: ACTION SYMBOL ENTRY_PRICE [LOT].\\n"
        f"IMPORTANT: If the signal is for Gold (XAUUSD, XAU, etc), use the symbol GOLD.\\n"
        f"Otherwise reply with NO_TRADE.\\nMessage:\\n{message}"
    )"""

prompt_replace = """def build_prompt(message: str, channel_name: str) -> str:
    return (
        f"You are a Forex trading AI. Extract trade data from channel '{channel_name}'.\\n"
        f"Return ONLY a raw JSON object (no markdown, no backticks, no other text) with keys: action, symbol, entry, tp, sl.\\n"
        f"If not a signal, return {{\\"action\\": \\"NO_TRADE\\"}}. Gold symbols (XAUUSD, XAU) must be \\"GOLD\\".\\n"
        f"Message:\\n{message}"
    )"""
code = code.replace(prompt_find, prompt_replace)

# 2. Update ask_ai to use Ollama
ask_ai_find = """async def ask_ai(prompt: str) -> str:
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
        return resp.json()["choices"][0]["message"]["content"].strip()"""

ask_ai_replace = """async def ask_ai(prompt: str) -> str:
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
        return '{"action": "NO_TRADE", "error": "Ollama Offline"}'"""
code = code.replace(ask_ai_find, ask_ai_replace)

# 3. Update index route to load channel map
index_find = """def index():
    # Telegram status"""
index_replace = """def index():
    channel_map = load_channel_map()
    # Telegram status"""
code = code.replace(index_find, index_replace)

render_find = "render_template_string(HTML_TEMPLATE, telegram_status=telegram_status, active_sessions=session_str, logs=logs, mt5_stats=mt5_stats, positions=positions_data, active_channel_count=25)"
render_replace = "render_template_string(HTML_TEMPLATE, telegram_status=telegram_status, active_sessions=session_str, logs=logs, mt5_stats=mt5_stats, positions=positions_data, active_channel_count=len(channel_map), channel_map=channel_map)"
code = code.replace(render_find, render_replace)

# 4. Update the Active Channels table in HTML
html_table_find = """    <div id="TeleChannels" class="tele-tabcontent">
        <div class="table-container">
          <table>
            <tr><th>Channel Group</th><th>Status</th></tr>
            <tr><td>VIP Gold & Forex (15 Channels)</td><td><span style="color:var(--accent-green); text-shadow: 0 0 10px var(--accent-green-glow);">Listening for Signals...</span></td></tr>
            <tr><td>VIP Crypto (10 Channels)</td><td><span style="color:var(--accent-green); text-shadow: 0 0 10px var(--accent-green-glow);">Listening for Signals...</span></td></tr>
          </table>
        </div>
    </div>"""

html_table_replace = """    <div id="TeleChannels" class="tele-tabcontent">
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
    </div>"""
code = code.replace(html_table_find, html_table_replace)

# 5. Add JS to populate the channel table dynamically from logs!
js_fetch_find = "async function fetchHealth() {"
js_fetch_replace = """
      async function updateChannelTable(logs, positions) {
          if (!logs) return;
          // Reverse logs so oldest are processed first, newest overwrite
          [...logs].reverse().forEach(log => {
             // We don't have channel ID directly in log yet, just name. 
             // We need to match by name or update the log to include ID.
             // For now, we search the table for the name.
             const table = document.getElementById("channelTable");
             const trs = table.getElementsByTagName("tr");
             let targetCid = null;
             for (let i = 0; i < trs.length; i++) {
                 if (trs[i].innerHTML.includes(log.channel_name)) {
                     targetCid = trs[i].id.replace("row_", "");
                     break;
                 }
             }
             if (targetCid) {
                 document.getElementById("analysis_" + targetCid).innerText = log.message;
                 
                 let aiParsed;
                 try { aiParsed = JSON.parse(log.ai_reply); } catch(e) { aiParsed = {action: "ERROR"}; }
                 
                 const actionTd = document.getElementById("action_" + targetCid);
                 const pricesTd = document.getElementById("prices_" + targetCid);
                 const timeTd = document.getElementById("time_" + targetCid);
                 
                 timeTd.innerText = log.timestamp || new Date().toLocaleTimeString();
                 
                 if (aiParsed.action && aiParsed.action !== "NO_TRADE" && aiParsed.action !== "ERROR") {
                     actionTd.innerHTML = `<span class="badge ${aiParsed.action.toLowerCase()}">${aiParsed.action}</span> <b>${aiParsed.symbol}</b>`;
                     pricesTd.innerHTML = `<span style="color:var(--text-muted)">E:</span> ${aiParsed.entry || '-'} | <span style="color:var(--accent-green)">TP:</span> ${aiParsed.tp || '-'} | <span style="color:var(--accent-red)">SL:</span> ${aiParsed.sl || '-'}`;
                     
                     // Check running profit from positions
                     const profitTd = document.getElementById("profit_" + targetCid);
                     let foundPos = false;
                     if(positions) {
                         positions.forEach(pos => {
                             if (pos.comment === log.channel_name || pos.symbol === aiParsed.symbol) {
                                 const color = pos.profit >= 0 ? "var(--accent-green)" : "var(--accent-red)";
                                 profitTd.innerHTML = `<span style="color:${color}; font-weight:bold;">$${pos.profit.toFixed(2)}</span>`;
                                 foundPos = true;
                             }
                         });
                     }
                     if(!foundPos) profitTd.innerText = "Closed / No Active";
                 } else {
                     actionTd.innerText = "NO_TRADE";
                     pricesTd.innerText = "-";
                     document.getElementById("profit_" + targetCid).innerText = "-";
                 }
             }
          });
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

      async function fetchHealth() {"""
code = code.replace(js_fetch_find, js_fetch_replace)

js_interval_find = """          fetchStrategyPnl();
      }, 1500);"""
js_interval_replace = """          fetchStrategyPnl();
          fetchLogs();
      }, 1500);"""
code = code.replace(js_interval_find, js_interval_replace)

# Add /api/logs route
api_logs_find = """@app.route('/api/strategy_pnl')"""
api_logs_replace = """@app.route('/api/logs')
def api_logs():
    try:
        path = BASE_DIR / "message_ai_log.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify([])

@app.route('/api/strategy_pnl')"""
code = code.replace(api_logs_find, api_logs_replace)

# Fix analyse route to handle JSON and add timestamp
analyse_find = """    if ai_reply.upper().strip() != "NO_TRADE":
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
    }"""
analyse_replace = """    ticket = None
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
    }"""
code = code.replace(analyse_find, analyse_replace)

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Dashboard UI customized for Ollama and 50+ channels!")
