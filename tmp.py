import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add elapsed time and real time scripts to HTML
script_find = "setInterval(() => {"
script_replace = """
      // Real-time clock and elapsed time
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

      setInterval(() => {"""
code = code.replace(script_find, script_replace)

# 2. Add Running / Realized PnL update logic
pos_logic_find = "tbody.innerHTML = html;"
pos_logic_replace = """tbody.innerHTML = html;
          
          // Update Running PnL Metric
          let totalRunning = 0;
          data.forEach(pos => { totalRunning += pos.profit; });
          const rpnlEl = document.getElementById('runningPnlMetric');
          if (rpnlEl) {
              rpnlEl.innerText = (totalRunning >= 0 ? "+$" : "-$") + Math.abs(totalRunning).toFixed(2);
              rpnlEl.className = "metric-val " + (totalRunning >= 0 ? "green" : "red");
          }
"""
code = code.replace(pos_logic_find, pos_logic_replace)

strat_logic_find = "tbody.innerHTML = html;"
strat_logic_replace = """tbody.innerHTML = html;
          
          // Update Realized PnL Metric
          let totalRealized = 0;
          for (const [strat, stats] of Object.entries(data)) {
              totalRealized += parseFloat(stats.pnl);
          }
          const repnlEl = document.getElementById('realizedPnlMetric');
          if (repnlEl) {
              repnlEl.innerText = (totalRealized >= 0 ? "+$" : "-$") + Math.abs(totalRealized).toFixed(2);
              repnlEl.className = "metric-val " + (totalRealized >= 0 ? "green" : "red");
          }
"""
# Note: Since the variable is also named `tbody.innerHTML = html;`, we need to be careful with replace.
# The fetchStrategyPnl is the second occurrence of `tbody.innerHTML = html;`
code = code.replace("tbody.innerHTML = html;", strat_logic_replace)
# Oops, that replaced both occurrences. Let's fix that by using regex or just splitting.
# Instead of doing that, let me just rewrite the entire JS block.
