import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add strategyPnlTableBody HTML
html_str_find = """          </table>
        </div>
      </details>
    </div>"""
html_str_replace = """          </table>
        </div>
      </details>
      
      <details open style="margin-top: 1rem;">
        <summary><span class="group-title">▶ TODAY'S CLOSED STRATEGY PNL</span></summary>
        <div class="details-content">
          <table class="table">
            <tr><th>Strategy</th><th>Trades</th><th>Win Rate</th><th>Net P&L</th></tr>
            <tbody id="strategyPnlTableBody">
                <tr><td colspan="4" style="text-align:center; padding: 2rem; color: #cbd5e1;">Loading strategy PnL...</td></tr>
            </tbody>
          </table>
        </div>
      </details>
    </div>"""

code = code.replace(html_str_find, html_str_replace, 1)

# Add Javascript polling logic for Strategy PnL
js_find = """      // Refresh every 1.5 seconds"""
js_replace = """
      // Polling Strategy PnL
      async function fetchStrategyPnl() {
        try {
          const res = await fetch('/api/strategy_pnl');
          const data = await res.json();
          const tbody = document.getElementById("strategyPnlTableBody");
          if (!tbody) return;
          
          if (!data || Object.keys(data).length === 0) {
             tbody.innerHTML = "<tr><td colspan='4' style='text-align:center; padding: 2rem; color: #cbd5e1;'>No closed trades today.</td></tr>";
             return;
          }
          
          let html = "";
          for (const [strat, stats] of Object.entries(data)) {
              const color = stats.pnl >= 0 ? "var(--success)" : "var(--danger)";
              html += `<tr>
                  <td>${strat}</td>
                  <td>${stats.trades}</td>
                  <td>${stats.win_rate}</td>
                  <td><span style="color:${color}">$${parseFloat(stats.pnl).toFixed(2)}</span></td>
              </tr>`;
          }
          tbody.innerHTML = html;
        } catch (e) {
          console.error("Error fetching strategy pnl:", e);
        }
      }

      // Refresh every 1.5 seconds"""
code = code.replace(js_find, js_replace, 1)

# Add polling calls in setInterval
js_interval_find = """      setInterval(() => {
          fetchAILiveMetrics();
          fetchPositions();
          fetchHealth();
      }, 1500);
      
      // Initial fetch
      fetchAILiveMetrics();
      fetchPositions();
      fetchHealth();"""
js_interval_replace = """      setInterval(() => {
          fetchAILiveMetrics();
          fetchPositions();
          fetchHealth();
          fetchStrategyPnl();
      }, 1500);
      
      // Initial fetch
      fetchAILiveMetrics();
      fetchPositions();
      fetchHealth();
      fetchStrategyPnl();"""
code = code.replace(js_interval_find, js_interval_replace, 1)

# Add Flask Route for /api/strategy_pnl
route_find = """@app.route('/api/positions')"""
route_replace = """@app.route('/api/strategy_pnl')
def api_strategy_pnl():
    try:
        path = BASE_DIR / "strategy_pnl_today.json"
        if path.exists():
            with open(path, "r") as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({})

@app.route('/api/positions')"""
code = code.replace(route_find, route_replace, 1)

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patched dashboard_flask.py for Strategy PnL tracking!")
