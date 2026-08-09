import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

# We need to find the `async function updateChannelTable(logs, positions) { ... }` block
# and replace it.

pattern = re.compile(r"async function updateChannelTable\(logs, positions\) \{.*?(?=\s+async function fetchHealth)", re.DOTALL)

new_func = """async function updateChannelTable(logs, positions) {
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
        }"""

if pattern.search(code):
    code = pattern.sub(new_func, code)
    with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Success: Replaced updateChannelTable in dashboard_flask.py")
else:
    print("Failed: Could not find updateChannelTable block in dashboard_flask.py")
