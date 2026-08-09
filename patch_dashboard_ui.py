import re

with open('dashboard_flask.py', 'r', encoding='utf-8') as f:
    code = f.read()

find_js = """            let totalRealized = 0;
            for (const [strat, stats] of Object.entries(data)) {
                totalRealized += parseFloat(stats.pnl);
            }
            const repnlEl = document.getElementById('realizedPnlMetric');
            if (repnlEl) {
                repnlEl.innerText = (totalRealized >= 0 ? "+$" : "-$") + Math.abs(totalRealized).toFixed(2);
                repnlEl.className = "metric-val " + (totalRealized >= 0 ? "green" : "red");
            }"""

replace_js = """            // Realized PNL is calculated in fetchStrategyPnl"""

code = code.replace(find_js, replace_js)

find_js2 = """            let html = "";
            for (const [strat, stats] of Object.entries(data)) {
                const color = stats.pnl >= 0 ? "var(--accent-green)" : "var(--accent-red)";
                const glow = stats.pnl >= 0 ? "var(--accent-green-glow)" : "var(--accent-red-glow)";
                html += `<tr>
                    <td style="color: var(--accent-blue); font-weight: 600; font-family: 'Outfit', sans-serif;">${strat}</td>
                    <td>${stats.trades}</td>
                    <td>${stats.win_rate}</td>
                    <td style="color:${color}; text-shadow: 0 0 10px ${glow}; font-weight: 700;">$${parseFloat(stats.pnl).toFixed(2)}</td>
                </tr>`;
            }
            tbody.innerHTML = html;"""

replace_js2 = """            let html = "";
            let totalRealized = 0;
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
            }"""

code = code.replace(find_js2, replace_js2)

with open('dashboard_flask.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed UI Rendering Exception!")
