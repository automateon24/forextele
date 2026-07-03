import re
import codecs

path = r'C:\cursor\options\niftyopt\dashboard_server.py'
with codecs.open(path, 'r', 'utf-8') as f:
    content = f.read()

# 1. Move Tabs
tabs_html = """        <div class="tabs-container" style="margin-left: auto; margin-right: auto; margin-top: -8px; margin-bottom: 24px;">
            <button class="tab-btn active" id="tab-v15" onclick="switchEngine('v15')">15 Ultimate Strategies</button>
            <button class="tab-btn" id="tab-telegram" onclick="switchEngine('telegram')" style="border-left: 2px solid var(--accent-blue);">Telegram Signals</button>
        </div>"""

content = content.replace(tabs_html, '')

indices_html = """        <!-- 5 Indices Tracker -->
        <div class="index-grid" id="indexContainer">
            <!-- Dynamic index cards populated by JS -->
        </div>"""

new_tabs_html = """        <!-- 5 Indices Tracker -->
        <div class="index-grid" id="indexContainer" style="margin-bottom: 24px;">
            <!-- Dynamic index cards populated by JS -->
        </div>

        <div class="tabs-container" style="margin-left: auto; margin-right: auto; margin-top: 12px; margin-bottom: 24px; padding: 4px; background: rgba(0,0,0,0.2); border-radius: 12px; display: flex; justify-content: center; gap: 8px;">
            <button class="tab-btn active" id="tab-v15" onclick="switchEngine('v15')" style="padding: 10px 30px; font-size: 15px;">15 Ultimate Strategies</button>
            <button class="tab-btn" id="tab-telegram" onclick="switchEngine('telegram')" style="padding: 10px 30px; font-size: 15px; border-left: 2px solid var(--accent-blue);">Telegram Signals</button>
        </div>"""

content = content.replace(indices_html, new_tabs_html)

# 2. Add IDs to theads
content = content.replace('<thead>\n                            <tr>\n                                <th>Index</th>', '<thead id="activeTradesHead">\n                            <tr>\n                                <th>Index</th>')
content = content.replace('<thead>\n                        <tr>\n                            <th>Exit Time</th>', '<thead id="completedTradesHead">\n                        <tr>\n                            <th>Exit Time</th>')

# 3. Modify JS render active trades
old_active_js = """                    activeTrades.forEach(t => {
                        const pnlClass = t.unrealized_pnl >= 0 ? 'price-up' : 'price-down';
                        const row = `
                            <tr>
                                <td><strong style="color: var(--accent-blue);">${t.index}</strong></td>
                                <td style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">${t.option_name}</td>
                                <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                <td>${t.lots}</td>
                                <td>${formatCurrency(t.entry_price)}</td>
                                <td><strong>${formatCurrency(t.current_price)}</strong></td>
                                <td>
                                    <div class="greeks-display">
                                        <span>&Delta;: <span class="greek-val">${t.greeks.delta}</span></span>
                                        <span>&theta;: <span class="greek-val">${t.greeks.theta}</span></span>
                                        <span>IV: <span class="greek-val">${t.greeks.iv}%</span></span>
                                    </div>
                                </td>
                                <td class="pnl-cell ${pnlClass}">${formatCurrency(t.unrealized_pnl)}</td>
                            </tr>
                        `;
                        activeTable.insertAdjacentHTML('beforeend', row);
                    });"""

new_active_js = """                    activeTrades.forEach(t => {
                        let row = '';
                        if (currentEngine === 'telegram') {
                            row = `
                                <tr>
                                    <td><strong style="color: var(--accent-blue); font-size: 11px;">${t.index}</strong></td>
                                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">${t.option_name}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td style="color: var(--accent-yellow);">${t.entry_price}</td>
                                    <td><strong style="color: var(--accent-green);">${t.current_price}</strong></td>
                                    <td><span class="badge" style="background: rgba(245, 158, 11, 0.1); color: var(--accent-yellow); font-size: 10px;">${t.status}</span></td>
                                    <td style="color: var(--text-muted); font-size: 12px; font-style: italic;">Monitoring Momentum & TP</td>
                                </tr>
                            `;
                        } else {
                            const pnlClass = t.unrealized_pnl >= 0 ? 'price-up' : 'price-down';
                            row = `
                                <tr>
                                    <td><strong style="color: var(--accent-blue);">${t.index}</strong></td>
                                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">${t.option_name}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td>${formatCurrency(t.entry_price)}</td>
                                    <td><strong>${formatCurrency(t.current_price)}</strong></td>
                                    <td>
                                        <div class="greeks-display">
                                            <span>&Delta;: <span class="greek-val">${t.greeks.delta}</span></span>
                                            <span>&theta;: <span class="greek-val">${t.greeks.theta}</span></span>
                                            <span>IV: <span class="greek-val">${t.greeks.iv}%</span></span>
                                        </div>
                                    </td>
                                    <td class="pnl-cell ${pnlClass}">${formatCurrency(t.unrealized_pnl)}</td>
                                </tr>
                            `;
                        }
                        activeTable.insertAdjacentHTML('beforeend', row);
                    });"""

content = content.replace(old_active_js, new_active_js)

# 4. Modify JS render completed trades
old_completed_js = """                    completedTrades.slice().reverse().forEach(t => {
                        const pnlClass = t.pnl_rs >= 0 ? 'price-up' : 'price-down';
                        const row = `
                            <tr>
                                <td style="color: var(--text-muted); font-size: 12.5px;">${t.exit_time || t.timestamp}</td>
                                <td><strong>${t.index}</strong></td>
                                <td style="font-size: 12.5px; color: var(--text-muted);">${t.strategy}</td>
                                <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                <td>${t.lots}</td>
                                <td>${formatCurrency(t.entry_price)}</td>
                                <td>${formatCurrency(t.exit_price)}</td>
                                <td><span style="font-size: 12px; font-weight: 500; color: var(--accent-yellow);">${t.exit_reason || 'EXIT'}</span></td>
                                <td class="pnl-cell ${pnlClass}">${formatCurrency(t.pnl_rs)}</td>
                            </tr>
                        `;
                        completedTable.insertAdjacentHTML('beforeend', row);
                    });"""

new_completed_js = """                    completedTrades.slice().reverse().forEach(t => {
                        const pnlClass = t.pnl_rs >= 0 ? 'price-up' : 'price-down';
                        let row = '';
                        if (currentEngine === 'telegram') {
                            row = `
                                <tr>
                                    <td style="color: var(--text-muted); font-size: 12.5px;">${t.exit_time || t.timestamp}</td>
                                    <td><strong style="color: var(--accent-blue); font-size: 11px;">${t.index}</strong></td>
                                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">${t.option_name}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td>${t.entry_price}</td>
                                    <td>${t.exit_price}</td>
                                    <td><span style="font-size: 12px; font-weight: 500; color: var(--accent-yellow);">${t.exit_reason || 'BOOKED'}</span></td>
                                    <td class="pnl-cell ${pnlClass}">${formatCurrency(t.pnl_rs)}</td>
                                </tr>
                            `;
                        } else {
                            row = `
                                <tr>
                                    <td style="color: var(--text-muted); font-size: 12.5px;">${t.exit_time || t.timestamp}</td>
                                    <td><strong>${t.index}</strong></td>
                                    <td style="font-size: 12.5px; color: var(--text-muted);">${t.strategy}</td>
                                    <td><span class="badge ${t.direction.toLowerCase()}">${t.direction}</span></td>
                                    <td>${t.lots}</td>
                                    <td>${formatCurrency(t.entry_price)}</td>
                                    <td>${formatCurrency(t.exit_price)}</td>
                                    <td><span style="font-size: 12px; font-weight: 500; color: var(--accent-yellow);">${t.exit_reason || 'EXIT'}</span></td>
                                    <td class="pnl-cell ${pnlClass}">${formatCurrency(t.pnl_rs)}</td>
                                </tr>
                            `;
                        }
                        completedTable.insertAdjacentHTML('beforeend', row);
                    });"""
                    
content = content.replace(old_completed_js, new_completed_js)

# 5. Inject Head Updater
header_updater_js = """                // 5. Update Active Trades
                const activeHead = document.getElementById('activeTradesHead');
                if (activeHead) {
                    if (currentEngine === 'telegram') {
                        activeHead.innerHTML = `<tr><th>Channel ID</th><th>Instrument</th><th>Action</th><th>Lots</th><th>Entry Range</th><th>Target / SL</th><th>Status</th><th>AI Inference</th></tr>`;
                    } else {
                        activeHead.innerHTML = `<tr><th>Index</th><th>Option Name</th><th>Dir</th><th>Lots</th><th>Entry Px</th><th>Live Px</th><th>Greeks (Delta/Theta)</th><th>Unrealized PnL</th></tr>`;
                    }
                }
                
                const completedHead = document.getElementById('completedTradesHead');
                if (completedHead) {
                    if (currentEngine === 'telegram') {
                        completedHead.innerHTML = `<tr><th>Exit Time</th><th>Channel ID</th><th>Instrument</th><th>Action</th><th>Lots</th><th>Entry Px</th><th>Exit Px</th><th>Reason</th><th>Realized PnL</th></tr>`;
                    } else {
                        completedHead.innerHTML = `<tr><th>Exit Time</th><th>Index</th><th>Strategy</th><th>Dir</th><th>Lots</th><th>Entry Px</th><th>Exit Px</th><th>Exit Reason</th><th>Realized PnL</th></tr>`;
                    }
                }"""

content = content.replace('// 5. Update Active Trades', header_updater_js + '\n\n                // Update Active Trades Count')

with codecs.open(path, 'w', 'utf-8') as f:
    f.write(content)

print("UI Patch Applied!")
