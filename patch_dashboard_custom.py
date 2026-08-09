import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add Tabs CSS
css_find = "/* Buttons */"
css_replace = """/* Tabs CSS */
    .tab { overflow: hidden; border-bottom: 1px solid var(--panel-border); margin-bottom: 1rem; }
    .tab button { background-color: inherit; float: left; border: none; outline: none; cursor: pointer; padding: 14px 24px; transition: 0.3s; font-size: 1.1rem; font-weight: 600; color: var(--text-muted); border-radius: 8px 8px 0 0; font-family: 'Outfit', sans-serif;}
    .tab button:hover { background-color: rgba(255, 255, 255, 0.05); color: var(--text-main); }
    .tab button.active { color: var(--accent-blue); border-bottom: 3px solid var(--accent-blue); background-color: rgba(0, 0, 0, 0.2); }
    .tabcontent { display: none; padding: 6px 12px; animation: fadeEffect 0.5s; }
    @keyframes fadeEffect { from {opacity: 0;} to {opacity: 1;} }
    
    .metric-val.red { color: var(--accent-red); text-shadow: 0 0 10px var(--accent-red-glow); }

    /* Buttons */"""
code = code.replace(css_find, css_replace)

# 2. Add openTab JS and update metrics JS
js_find = "document.addEventListener(\"DOMContentLoaded\", function() {"
js_replace = """
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
"""
code = code.replace(js_find, js_replace)

# Add PnL metric updating to JS
js_pos_find = "tbody.innerHTML = html;"
# We need to replace the first instance (positions)
code = code.replace(js_pos_find, """tbody.innerHTML = html;
          let totalRunning = 0;
          data.forEach(pos => { totalRunning += pos.profit; });
          const rpnlEl = document.getElementById('runningPnlMetric');
          if (rpnlEl) {
              rpnlEl.innerText = (totalRunning >= 0 ? "+$" : "-$") + Math.abs(totalRunning).toFixed(2);
              rpnlEl.className = "metric-val " + (totalRunning >= 0 ? "green" : "red");
          }
""", 1)

# And replace the second instance (strategy)
code = code.replace(js_pos_find, """tbody.innerHTML = html;
          let totalRealized = 0;
          for (const [strat, stats] of Object.entries(data)) {
              totalRealized += parseFloat(stats.pnl);
          }
          const repnlEl = document.getElementById('realizedPnlMetric');
          if (repnlEl) {
              repnlEl.innerText = (totalRealized >= 0 ? "+$" : "-$") + Math.abs(totalRealized).toFixed(2);
              repnlEl.className = "metric-val " + (totalRealized >= 0 ? "green" : "red");
          }
""", 1)

# 3. Update Mission Control UI
mc_find = """<!-- Operations Controls -->
  <div class="panel col-8">
    <h2>Mission Control</h2>
    <div class="btn-group" style="margin-top: 1rem;">
        <button class='btn btn-danger' onclick="masterControl('kill_all_orders')" style="flex: 1; padding: 1rem; font-size: 1rem;">🚨 PANIC: CLOSE ALL OPEN ORDERS</button>
    </div>
    <div class="btn-group" style="margin-top: 1rem;">
        <button class='btn btn-warning' onclick="masterControl('toggle_engine')" style="flex: 1;">⏻ Toggle Core Engine</button>
        <button class='btn btn-primary' onclick="masterControl('toggle_ai')" style="flex: 1;">⏸ Toggle AI Strategies</button>
        <button class='btn btn-primary' style="background: var(--accent-purple); box-shadow: 0 4px 15px var(--accent-purple-glow); flex: 1;" onclick="masterControl('toggle_telegram')">⏸ Toggle Telegram Listener</button>
    </div>
  </div>"""

mc_replace = """<!-- Operations Controls -->
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
  </div>"""
code = code.replace(mc_find, mc_replace)

# 4. Add Running/Realized PnL above positions
pos_find = """<!-- Live Positions -->
  <div class="panel col-12">
    <h2>Live Algorithmic Positions</h2>"""

pos_replace = """<!-- Live Positions -->
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
    </div>"""
code = code.replace(pos_find, pos_replace)

# 5. Make Telegram section tabbed
tel_find = """<!-- Telegram AI Logs -->
  <div class="panel col-12">
    <h2>Telegram AI Parsing Stream</h2>
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
  </div>"""

tel_replace = """<!-- Telegram AI Logs -->
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
        <div class="table-container">
          <table>
            <tr><th>Channel Group</th><th>Status</th></tr>
            <tr><td>VIP Gold & Forex (15 Channels)</td><td><span style="color:var(--accent-green); text-shadow: 0 0 10px var(--accent-green-glow);">Listening for Signals...</span></td></tr>
            <tr><td>VIP Crypto (10 Channels)</td><td><span style="color:var(--accent-green); text-shadow: 0 0 10px var(--accent-green-glow);">Listening for Signals...</span></td></tr>
          </table>
        </div>
    </div>
  </div>"""
code = code.replace(tel_find, tel_replace)

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Dashboard UI customized!")
