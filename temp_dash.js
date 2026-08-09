
    
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
  