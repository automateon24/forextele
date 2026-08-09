import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# First, let's remove ALL instances of the injected alert logic to start fresh.
alert_logic_regex = re.compile(r"      let alertCount = 0;.*?async function fetchAlerts\(\) \{.*?\n      \}\n", re.DOTALL)
code = alert_logic_regex.sub("", code)

# We also need to fix the duplicate window.toggleAlerts if any
code = code.replace("window.toggleAlerts = function()", "function toggleAlerts()")

# Now, we define the alert logic OUTSIDE DOMContentLoaded so it's global
global_js = """
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
"""

# Insert the global JS right before document.addEventListener
code = code.replace('    document.addEventListener("DOMContentLoaded", function() {', global_js + '\n    document.addEventListener("DOMContentLoaded", function() {')

# Make sure fetchAlerts is called inside the 1500ms setInterval
# The 1500ms setInterval currently looks like:
#       setInterval(() => {
#           fetchAILiveMetrics();
#           fetchPositions();
#           fetchHealth();
#           fetchStrategyPnl();
#           fetchLogs();
#       }, 1500);
# We need to make sure fetchAlerts() is there.
if "fetchAlerts();" not in code:
    code = code.replace("fetchLogs();", "fetchLogs();\n          fetchAlerts();")

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Cleaned up duplicated JS and fixed scoping!")
