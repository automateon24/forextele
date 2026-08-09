import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add CSS
css_inject = """
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
"""
code = code.replace("</style>", css_inject)

# 2. Add HTML
html_inject = """
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
"""
code = code.replace("""    <div class="sys-health" id="systemHealth">
        <span class="status-dot online"></span> Checking Health...
    </div>
</div>""", html_inject)

# 3. Add JS
js_inject = """
      let alertCount = 0;
      function toggleAlerts() {
          const el = document.getElementById('alertsDropdown');
          el.style.display = el.style.display === 'flex' ? 'none' : 'flex';
          if(el.style.display === 'flex') {
              document.getElementById('bellBadge').style.display = 'none';
          }
      }
      
      async function clearAlerts() {
          try {
              await fetch('/api/alerts/clear', {method: 'POST'});
              document.getElementById('alertsDropdown').innerHTML = '<div style="padding:15px; text-align:center; color:var(--text-muted);">No new alerts</div>';
              document.getElementById('bellBadge').style.display = 'none';
          } catch(e) {}
      }
      
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

      setInterval(() => {
"""
code = code.replace("      setInterval(() => {", js_inject)

js_inject_2 = """
          fetchLogs();
          fetchAlerts();
"""
code = code.replace("          fetchLogs();", js_inject_2)

# 4. Add Python Routes
py_inject = """
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

"""
code = code.replace("@app.route('/api/logs')", py_inject + "@app.route('/api/logs')")

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Injected notification bell UI into dashboard_flask.py!")
