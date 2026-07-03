import codecs
import json
import os

path = r'C:\cursor\options\niftyopt\dashboard_server.py'
with codecs.open(path, 'r', 'utf-8') as f:
    content = f.read()

# 1. Add FastAPI endpoints for health & control
api_code = """
import traceback
import psutil

SYSTEM_HEALTH_FILE = r'C:\25stragy\system_health.json'

def get_system_health():
    default_health = {
        "master_switch": "START",
        "dhan_api": {"status": "OK", "msg": ""},
        "telegram_engine": {"status": "OK", "msg": ""},
        "v15_engine": {"status": "OK", "msg": ""},
        "unread_alerts": 0
    }
    if os.path.exists(SYSTEM_HEALTH_FILE):
        try:
            with open(SYSTEM_HEALTH_FILE, 'r') as f:
                data = json.load(f)
                return data
        except:
            pass
    return default_health

def save_system_health(data):
    with open(SYSTEM_HEALTH_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.get("/api/health")
async def api_health():
    return get_system_health()

@app.post("/api/control/{action}")
async def api_control(action: str):
    health = get_system_health()
    if action.upper() in ["START", "STOP"]:
        health["master_switch"] = action.upper()
        save_system_health(health)
    elif action.upper() == "CLEAR_ALERTS":
        health["unread_alerts"] = 0
        health["dhan_api"]["status"] = "OK"
        health["telegram_engine"]["status"] = "OK"
        health["v15_engine"]["status"] = "OK"
        save_system_health(health)
    elif action.upper() == "SHUTDOWN":
        # Kill all stragy python processes
        health["master_switch"] = "STOP"
        save_system_health(health)
        os.system('taskkill /F /IM python.exe')
    return health
"""

if '@app.get("/api/health")' not in content:
    content = content.replace('app = FastAPI()', 'app = FastAPI()' + '\n' + api_code)


# 2. Add UI Elements (Bell & Start/Stop)
header_html = """        <header>
            <div class="logo-section">
                <h1>25 Strategy Nifty Options <span>Production</span></h1>
            </div>
            <div class="status-panel">"""

new_header_html = """        <header>
            <div class="logo-section" style="display: flex; align-items: center; gap: 15px;">
                <h1>25 Strategy Nifty Options <span>Production</span></h1>
                <div class="master-control" id="masterControlContainer">
                    <button id="masterToggleBtn" onclick="toggleMasterSwitch()" style="background: rgba(16, 185, 129, 0.2); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.4); font-family: 'Outfit', sans-serif; font-weight: 700; font-size: 13px; padding: 6px 16px; border-radius: 8px; cursor: pointer; transition: all 0.2s; text-transform: uppercase; letter-spacing: 1px; display: flex; align-items: center; gap: 6px;">
                        <span id="masterToggleIcon">▶</span> <span id="masterToggleText">SYSTEM ACTIVE</span>
                    </button>
                </div>
            </div>
            
            <div class="status-panel" style="position: relative; display: flex; align-items: center; gap: 10px;">
                <!-- Notification Bell -->
                <div id="notificationBell" onclick="toggleNotifications()" style="cursor: pointer; position: relative; padding: 6px; background: rgba(255,255,255,0.05); border-radius: 50%; border: 1px solid rgba(255,255,255,0.1); width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; transition: all 0.2s;">
                    <span style="font-size: 16px;">🔔</span>
                    <span id="bellBadge" style="display: none; position: absolute; top: -2px; right: -2px; background: var(--accent-red); color: white; font-size: 9px; font-weight: bold; width: 14px; height: 14px; border-radius: 50%; text-align: center; line-height: 14px;">0</span>
                </div>
                
                <!-- Notification Dropdown -->
                <div id="notificationDropdown" style="display: none; position: absolute; top: 45px; right: 200px; width: 320px; background: #0d101c; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px; z-index: 999; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; margin-bottom: 8px;">
                        <span style="font-weight: 700; font-size: 14px;">System Health Alerts</span>
                        <button onclick="clearAlerts()" style="background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 11px; text-decoration: underline;">Clear All</button>
                    </div>
                    <div id="alertsList" style="font-size: 12px; max-height: 200px; overflow-y: auto;">
                        <div style="color: var(--accent-green); padding: 8px 0; text-align: center;">All systems operating flawlessly.</div>
                    </div>
                </div>
                
                <button id="shutdownBtn" onclick="emergencyShutdown()" style="background: rgba(239, 68, 68, 0.1); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.25); font-family: 'Outfit', sans-serif; font-weight: 600; font-size: 12px; padding: 6px 12px; border-radius: 6px; cursor: pointer; transition: all 0.2s;">POWER OFF</button>
                <div class="divider" style="width: 1px; height: 24px; background: rgba(255,255,255,0.1);"></div>"""

content = content.replace(header_html, new_header_html)


# 3. Add JS for Health polling
js_code = """
            let healthState = { master_switch: 'START' };
            
            async function fetchSystemHealth() {
                try {
                    const res = await fetch('/api/health');
                    healthState = await res.json();
                    updateHealthUI();
                } catch (err) {
                    console.error("Health fetch error");
                }
            }
            
            function updateHealthUI() {
                // Update Master Toggle
                const btn = document.getElementById('masterToggleBtn');
                const text = document.getElementById('masterToggleText');
                const icon = document.getElementById('masterToggleIcon');
                
                if (healthState.master_switch === 'START') {
                    btn.style.background = 'rgba(16, 185, 129, 0.15)';
                    btn.style.color = 'var(--accent-green)';
                    btn.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                    text.innerText = 'SYSTEM ACTIVE';
                    icon.innerText = '▶';
                } else {
                    btn.style.background = 'rgba(239, 68, 68, 0.15)';
                    btn.style.color = 'var(--accent-red)';
                    btn.style.borderColor = 'rgba(239, 68, 68, 0.4)';
                    text.innerText = 'SYSTEM STOPPED';
                    icon.innerText = '⏸';
                }
                
                // Update Bell
                const bell = document.getElementById('notificationBell');
                const badge = document.getElementById('bellBadge');
                let errors = [];
                
                if (healthState.dhan_api && healthState.dhan_api.status !== 'OK') errors.push(`Dhan API: ${healthState.dhan_api.msg}`);
                if (healthState.telegram_engine && healthState.telegram_engine.status !== 'OK') errors.push(`Telegram: ${healthState.telegram_engine.msg}`);
                if (healthState.v15_engine && healthState.v15_engine.status !== 'OK') errors.push(`V15 Engine: ${healthState.v15_engine.msg}`);
                
                const alertCount = errors.length + (healthState.unread_alerts || 0);
                
                if (alertCount > 0) {
                    bell.style.borderColor = 'var(--accent-red)';
                    bell.style.background = 'rgba(239, 68, 68, 0.1)';
                    badge.style.display = 'block';
                    badge.innerText = alertCount;
                    
                    const alertsList = document.getElementById('alertsList');
                    alertsList.innerHTML = '';
                    errors.forEach(e => {
                        alertsList.innerHTML += `<div style="color: var(--accent-red); padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">${e}</div>`;
                    });
                } else {
                    bell.style.borderColor = 'rgba(255,255,255,0.1)';
                    bell.style.background = 'rgba(255,255,255,0.05)';
                    badge.style.display = 'none';
                    document.getElementById('alertsList').innerHTML = '<div style="color: var(--accent-green); padding: 8px 0; text-align: center;">All systems operating flawlessly.</div>';
                }
            }
            
            function toggleNotifications() {
                const drop = document.getElementById('notificationDropdown');
                drop.style.display = drop.style.display === 'none' ? 'block' : 'none';
            }
            
            async function clearAlerts() {
                await fetch('/api/control/CLEAR_ALERTS', { method: 'POST' });
                fetchSystemHealth();
            }
            
            async function toggleMasterSwitch() {
                const action = healthState.master_switch === 'START' ? 'STOP' : 'START';
                if (action === 'STOP') {
                    if(!confirm('EMERGENCY STOP: This will halt all new trades across all engines immediately. Continue?')) return;
                }
                await fetch(`/api/control/${action}`, { method: 'POST' });
                fetchSystemHealth();
            }
            
            async function emergencyShutdown() {
                if(confirm('FATAL: This will forcefully terminate ALL Python trading engines and shut down the dashboard. Are you sure?')) {
                    await fetch('/api/control/SHUTDOWN', { method: 'POST' });
                    document.body.innerHTML = '<h1 style="color: red; text-align: center; margin-top: 100px;">SYSTEM TERMINATED SUCCESSFULLY. CLOSE BROWSER.</h1>';
                }
            }
            
            setInterval(fetchSystemHealth, 2000);
            fetchSystemHealth();
"""

if "fetchSystemHealth()" not in content:
    content = content.replace('setInterval(fetchDashboardData, 1500);', js_code + '\n            setInterval(fetchDashboardData, 1500);')

with codecs.open(path, 'w', 'utf-8') as f:
    f.write(content)

print("Dashboard Server Patched with Health Monitoring & Control System!")
