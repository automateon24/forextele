import React, { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [data, setData] = useState({ mt5: null, ai_logs: [], signal_audit: [], all_channels: [], server_time: '', telegram_status: '', strategies_scanning: 0, active_channels: [] })
  const [connected, setConnected] = useState(false)
  const [activeTab, setActiveTab] = useState('STRATEGIES') // 'STRATEGIES' or 'TELEGRAM'
  const [expandedChannel, setExpandedChannel] = useState(null)
  
  const terminalRef = useRef(null)
  const wsRef = useRef(null)

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket('ws://localhost:8888')
      wsRef.current = ws
      
      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, 2000)
      }
      ws.onmessage = (e) => {
        const payload = JSON.parse(e.data)
        setData(payload)
      }
    }
    connect()
  }, [])

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [data.ai_logs])

  const account = data.mt5?.account || {}
  const positions = data.mt5?.positions || []
  
  const telegramPositions = positions.filter(p => p.magic === 999999)
  const strategyPositions = positions.filter(p => p.magic === 888888 || p.magic === 111111 || p.magic !== 999999) // Catch-all for strategy/test

  const activePosList = activeTab === 'STRATEGIES' ? strategyPositions : telegramPositions
  const totalUnrealized = activePosList.reduce((sum, p) => sum + (p.profit || 0), 0)
  
  const currentWins = activeTab === 'STRATEGIES' ? (data.mt5?.strat_wins || 0) : (data.mt5?.tele_wins || 0)
  const currentLosses = activeTab === 'STRATEGIES' ? (data.mt5?.strat_losses || 0) : (data.mt5?.tele_losses || 0)
  const currentWinRate = activeTab === 'STRATEGIES' ? (data.mt5?.strat_win_rate || 0.0) : (data.mt5?.tele_win_rate || 0.0)
  const currentPnl = activeTab === 'STRATEGIES' ? (data.mt5?.strat_pnl || 0.0) : (data.mt5?.tele_pnl || 0.0)
  
  // Ledger Splitting Logic
  const allClosedDeals = data.mt5?.closed_deals || []
  const activeClosedDeals = activeTab === 'STRATEGIES' ? allClosedDeals.filter(d => d.magic !== 999999) : allClosedDeals.filter(d => d.magic === 999999)
  const totalClosedProfit = activeClosedDeals.reduce((sum, d) => sum + (d.profit || 0), 0)
  
  // Truly Isolated Ledger Accounting
  const startingBase = 5000 // 5K sandbox
  const ledgerCapital = startingBase + currentPnl + totalUnrealized
  
  // Pro-rate the Used Margin based on actual lot sizes used by each ledger
  const totalVolume = positions.reduce((sum, p) => sum + (p.volume || 0), 0)
  const activeVolume = activePosList.reduce((sum, p) => sum + (p.volume || 0), 0)
  const marginAlloc = totalVolume > 0 ? ((account.margin || 0) * (activeVolume / totalVolume)) : 0

  
  const formatMoney = (val) => {
    if (val === null || val === undefined || isNaN(val)) return '$0.00'
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(val))
  }

  const formatPrice = (val) => {
    if (val === null || val === undefined || isNaN(val)) return '0.00'
    const num = Number(val)
    let str = num.toString()
    if (str.includes('.')) {
      let parts = str.split('.')
      if (parts[1].length > 5) return num.toFixed(5)
    }
    return str
  }

  const formatNumber = (val) => {
    if (val === null || val === undefined || isNaN(val)) return '0.00'
    return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(val))
  }

  const sendCommand = (action) => {
    if (wsRef.current && connected) {
      wsRef.current.send(JSON.stringify({ action }))
    }
  }

  const tickers = data.mt5?.tickers || [
    { symbol: 'EURUSD', price: '0.0', trend: 'NORMAL', status: 'LOADING...', color: '#10b981', spread: 0 }
  ]

  return (
    <div className="dashboard-container">
      {/* TOP HEADER */}
      <div className="app-header">
        <div className="brand-section">
          <h2>Swarm OS Forex</h2>
          <span className="badge production">PRODUCTION</span>
          <button className={`btn-system ${connected ? 'active' : 'error'}`} onClick={() => sendCommand('START_BOT')}>
            {connected ? '▶ SYSTEM ACTIVE' : '▲ SYSTEM ERROR'}
          </button>
        </div>
        
        <div className="tags-section">
          <button className="tag-pill kill-switch" onClick={() => sendCommand('KILL_SWITCH')}>● KILL SWITCH</button>
          <button className="tag-pill clickable">● EOD REPORT</button>
          <div className={`tag-pill ${connected ? 'active' : ''}`}>● MARKET {connected ? 'OPEN' : 'CLOSED'}</div>
          <div className="tag-pill active">● CONNECTED</div>
          <div className="tag-pill active">● {data.telegram_status || 'LIVE'}</div>
          <div className="tag-pill time-display">{data.server_time ? data.server_time.split(' ')[1] + ' ' + data.server_time.split(' ')[2] : '00:00:00 IST'}</div>
        </div>
      </div>

      {/* TICKER ROW */}
      <div className="ticker-grid">
        {tickers.map(t => (
          <div className="ticker-card" key={t.symbol}>
            <div className="ticker-top">
              <span className="symbol">{t.symbol}</span>
              <span className="trend" style={{color: '#64748b'}}>{t.trend}</span>
            </div>
            <div className="ticker-price">{formatPrice(t.price)}</div>
            <div className="ticker-details">
              <div>Spread: <span>{t.spread}</span></div>
              <div>Swap: <span>{t.swap !== undefined ? t.swap : 0}%</span></div>
            </div>
            <div className="ticker-status" style={{color: t.color}}>{t.status}</div>
          </div>
        ))}
      </div>

      {/* CENTER TAB TOGGLE */}
      <div className="tab-toggle-container">
        <button 
          className={`tab-btn ${activeTab === 'STRATEGIES' ? 'active' : ''}`}
          onClick={() => setActiveTab('STRATEGIES')}
        >
          ULTIMATE STRATEGIES
        </button>
        <button 
          className={`tab-btn ${activeTab === 'TELEGRAM' ? 'active' : ''}`}
          onClick={() => setActiveTab('TELEGRAM')}
        >
          TELEGRAM SIGNALS
        </button>
      </div>

      {/* METRICS ROW */}
      <div className="metrics-row">
        <div className="metric-box">
          <div className="metric-label">ISOLATED CAPITAL BASE</div>
          <div className="metric-value">{formatMoney(ledgerCapital)}</div>
          <div className="metric-sub">{activeTab} Ledger (50% Split)</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">USED MARGIN</div>
          <div className="metric-value">{formatMoney(marginAlloc)}</div>
          <div className="metric-sub">{formatNumber((marginAlloc / ledgerCapital)*100)}% Allocation</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">TOTAL TRADES ({activeTab})</div>
          <div className="metric-value">{activePosList.length}</div>
          <div className="metric-sub">{activePosList.length} Active / {currentWins + currentLosses} Closed</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">WIN RATE ({activeTab})</div>
          <div className="metric-value" style={{color: currentWinRate >= 50 ? '#10b981' : '#ef4444'}}>{currentWinRate}%</div>
          <div className="metric-sub">{currentWins} W / {currentLosses} L</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">REALIZED PNL ({activeTab})</div>
          <div className={`metric-value ${currentPnl >= 0 ? 'profit-text' : 'loss-text'}`}>
            {currentPnl >= 0 ? '+' : ''}{formatMoney(currentPnl)}
          </div>
          <div className="metric-sub">Booked Trades</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">LIVE UNREALIZED PNL</div>
          <div className={`metric-value ${totalUnrealized >= 0 ? 'profit-text' : 'loss-text'}`}>
            {totalUnrealized >= 0 ? '+' : ''}{formatMoney(totalUnrealized)}
          </div>
          <div className="metric-sub">Open {activeTab} Positions</div>
        </div>
      </div>

      {/* ACTIVE POSITIONS TABLE */}
      <div className="panel-container">
        <div className="panel-header">
          Active Positions ({activeTab === 'STRATEGIES' ? 'Ultimate Strategies' : 'Telegram Signals'})
        </div>
        <div className="panel-body" style={{maxHeight: '250px', overflowY: 'auto'}}>
          <TradeTable 
            positions={activeTab === 'STRATEGIES' ? strategyPositions : telegramPositions} 
            formatMoney={formatMoney} 
            formatPrice={formatPrice}
          />
        </div>
      </div>

      {/* TODAY'S COMPLETED TRADES */}
      <div className="panel-container">
        <div className="panel-header">
          Today's Completed Trades ({activeTab})
        </div>
        <div className="panel-body" style={{maxHeight: '300px', overflowY: 'auto'}}>
          {activeClosedDeals.length === 0 ? (
            <div className="no-trades-sub">No completed trades today for {activeTab}.</div>
          ) : (
            <table className="data-table">
              <thead style={{position: 'sticky', top: 0, backgroundColor: '#0f172a', zIndex: 1}}>
                <tr>
                  <th>TIME</th>
                  <th>SYMBOL</th>
                  <th style={{textAlign: 'center'}}>DIR</th>
                  <th style={{textAlign: 'center'}}>LOTS</th>
                  <th style={{textAlign: 'right'}}>REALIZED PNL</th>
                </tr>
              </thead>
              <tbody>
                {activeClosedDeals.map((deal) => (
                  <tr key={deal.ticket}>
                    <td style={{color: '#94a3b8'}}>{deal.time}</td>
                    <td className="symbol-cell">{deal.symbol}</td>
                    <td style={{textAlign: 'center'}}>
                      <span className={`dir-badge ${deal.type === 'BUY' ? 'buy' : 'sell'}`}>{deal.type}</span>
                    </td>
                    <td style={{textAlign: 'center'}}>{deal.volume}</td>
                    <td className={deal.profit >= 0 ? 'profit-text' : 'loss-text'} style={{textAlign: 'right', fontWeight: 600}}>
                      {deal.profit >= 0 ? '+' : ''}{formatMoney(deal.profit)}
                    </td>
                  </tr>
                ))}
                <tr style={{borderTop: '2px solid #334155', backgroundColor: '#1e293b'}}>
                  <td colSpan="4" style={{textAlign: 'right', fontWeight: 'bold', padding: '10px 5px'}}>TOTAL REALIZED PNL:</td>
                  <td className={totalClosedProfit >= 0 ? 'profit-text' : 'loss-text'} style={{textAlign: 'right', fontWeight: 'bold', padding: '10px 5px', fontSize: '14px'}}>
                    {totalClosedProfit >= 0 ? '+' : ''}{formatMoney(totalClosedProfit)}
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* TERMINAL */}
      <div className="panel-container">
        <div className="panel-header" style={{color: '#60a5fa'}}>
          ● SWARM AI NEURAL DEBATE (LIVE FEED)
        </div>
        <div className="terminal-body" ref={terminalRef}>
          {data.ai_logs.length === 0 ? (
            <div className="log-line">Awaiting terminal input...</div>
          ) : (
            data.ai_logs.map((line, i) => {
              // Colorize based on personas
              let color = '#94a3b8'; // default
              if (line.includes('[WATCHER]')) color = '#60a5fa';
              else if (line.includes('[TRIGGER]')) color = '#a855f7';
              else if (line.includes('[GOVERNOR]')) {
                if (line.includes('APPROVED')) color = '#10b981';
                else if (line.includes('VETOED') || line.includes('DENIED')) color = '#ef4444';
                else color = '#10b981';
              }
              else if (line.includes('[TRAIL_BOSS]')) color = '#facc15';
              else if (line.includes('ERROR') || line.includes('CRITICAL')) color = '#ef4444';
              
              const timeStr = data.server_time ? `[${data.server_time.split(' ')[1]}]` : '[00:00:00]';
              
              return (
                <div key={i} className="log-line" style={{color}}>
                  <span className="log-time">{timeStr}</span> {line}
                </div>
              )
            })
          )}
        </div>
      </div>
      {/* SIGNAL AUDIT TABLE (ONLY SHOWS FOR TELEGRAM TAB) */}
      {activeTab === 'TELEGRAM' && (
        <div className="panel-container">
          <div className="panel-header" style={{color: '#facc15'}}>
            ● TELEGRAM CHANNEL LIVE TRACKER
          </div>
          <div className="panel-body" style={{overflowX: 'auto', maxHeight: '500px'}}>
            <table className="data-table" style={{fontSize: '11px'}}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>CHANNEL NAME</th>
                  <th>TODAY TRADES</th>
                  <th style={{maxWidth: '150px'}}>LATEST SIGNAL RECEIVED</th>
                  <th>AI PARSED OUTPUT</th>
                  <th>EXECUTION STATUS</th>
                  <th>REASON / SWARM LOGIC</th>
                </tr>
              </thead>
              <tbody>
                {(data.all_channels || []).map((chNameRaw, i) => {
                  const chName = chNameRaw || '';
                  // Get today's date in YYYY-MM-DD
                  const todayStr = new Date().toLocaleString('en-CA', {timeZone: 'Asia/Kolkata'}).split(',')[0];
                  
                  // Find all signals for this channel (case-insensitive) AND filter for TODAY
                  const channelSignals = (data.signal_audit || []).filter(s => {
                    const isChannelMatch = s.Channel && s.Channel.toLowerCase().includes(chName.toLowerCase());
                    const isToday = s.Timestamp && typeof s.Timestamp === 'string' && s.Timestamp.startsWith(todayStr);
                    return isChannelMatch && isToday;
                  });
                  
                  const tradeCount = channelSignals.length;
                  const latestSignal = tradeCount > 0 ? channelSignals[0] : null; // Backend reversed list so [0] is newest
                  
                  let statusColor = '#94a3b8';
                  if (latestSignal) {
                    if (latestSignal.Status === 'SUCCESS' || latestSignal.Status === 'APPROVED') statusColor = '#10b981';
                    else if (latestSignal.Status === 'REJECTED' || latestSignal.Status === 'FAILED') statusColor = '#ef4444';
                    else if (latestSignal.Status === 'UPDATE') statusColor = '#3b82f6';
                  }
                  
                  const isExpanded = expandedChannel === chName;
                  
                  return (
                    <React.Fragment key={i}>
                      <tr onClick={() => setExpandedChannel(isExpanded ? null : chName)} style={{cursor: 'pointer', backgroundColor: isExpanded ? '#1e293b' : 'transparent'}}>
                        <td>{i + 1}</td>
                        <td style={{color: '#60a5fa', fontWeight: 'bold'}}>
                          {isExpanded ? '▼ ' : '▶ '}{chName.toUpperCase()}
                        </td>
                        <td style={{textAlign: 'center', fontWeight: 'bold'}}>{tradeCount > 0 ? tradeCount : '-'}</td>
                        <td style={{maxWidth: '150px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: '#cbd5e1'}} title={latestSignal ? latestSignal.Raw_Signal : ''}>
                          {latestSignal ? latestSignal.Raw_Signal : '-'}
                        </td>
                        <td style={{color: '#a855f7'}}>{latestSignal ? latestSignal.Parsed_Signal : '-'}</td>
                        <td style={{color: statusColor, fontWeight: 'bold'}}>{latestSignal ? latestSignal.Status : 'AWAITING SIGNAL'}</td>
                        <td>{latestSignal ? latestSignal.Reason : '-'}</td>
                      </tr>
                      {isExpanded && tradeCount > 0 && (
                        <tr>
                          <td colSpan="7" style={{padding: '0', backgroundColor: '#0f172a'}}>
                            <div style={{padding: '10px 20px', borderLeft: '4px solid #3b82f6'}}>
                              <table style={{width: '100%', fontSize: '10px', color: '#94a3b8'}}>
                                <thead>
                                  <tr style={{borderBottom: '1px solid #334155'}}>
                                    <th style={{padding: '5px'}}>TIME</th>
                                    <th style={{padding: '5px'}}>ACCOUNT</th>
                                    <th style={{padding: '5px'}}>RAW SIGNAL</th>
                                    <th style={{padding: '5px'}}>PARSED OUTPUT</th>
                                    <th style={{padding: '5px'}}>STATUS</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {channelSignals.map((sig, idx) => {
                                    const ts = sig.Timestamp || '';
                                    const timeStr = ts.includes(' ') ? ts.split(' ')[1] : ts;
                                    return (
                                      <tr key={idx}>
                                        <td style={{padding: '5px'}}>{timeStr}</td>
                                        <td style={{padding: '5px'}}>{sig.Account || '-'}</td>
                                        <td style={{padding: '5px', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{sig.Raw_Signal || '-'}</td>
                                        <td style={{padding: '5px'}}>{sig.Parsed_Signal || '-'}</td>
                                        <td style={{padding: '5px', color: sig.Status === 'SUCCESS' ? '#10b981' : (sig.Status === 'REJECTED' ? '#ef4444' : '#fff')}}>{sig.Status || '-'}</td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function TradeTable({ positions, formatMoney, formatPrice }) {
  if (positions.length === 0) return <div className="no-trades">No active trades.</div>
  
  return (
    <table className="data-table">
      <thead style={{position: 'sticky', top: 0, backgroundColor: '#0f172a', zIndex: 1}}>
        <tr>
          <th>SYMBOL</th>
          <th>STRATEGY NAME</th>
          <th style={{textAlign: 'center'}}>DIR</th>
          <th style={{textAlign: 'center'}}>LOTS</th>
          <th style={{textAlign: 'right'}}>ENTRY PX</th>
          <th style={{textAlign: 'right'}}>LIVE PX</th>
          <th style={{textAlign: 'right'}}>GREEKS (SPREAD/SWAP)</th>
          <th style={{textAlign: 'right'}}>UNREALIZED PNL</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((pos) => (
          <tr key={pos.ticket}>
            <td className="symbol-cell">{pos.symbol}</td>
            <td className="strategy-cell">{pos.magic === 999999 ? 'Telegram_Signal' : (pos.magic === 111111 ? 'Manual_Test' : 'V15_Breakout')}</td>
            <td style={{textAlign: 'center'}}>
              <span className={`dir-badge ${pos.type === 0 ? 'buy' : 'sell'}`}>{pos.type === 0 ? 'BUY' : 'SELL'}</span>
            </td>
            <td style={{textAlign: 'center'}}>{pos.volume}</td>
            <td style={{textAlign: 'right'}}>{formatPrice(pos.open_price)}</td>
            <td style={{textAlign: 'right'}}>{formatPrice(pos.current_price)}</td>
            <td style={{textAlign: 'right', color: '#64748b'}}>-</td>
            <td className={pos.profit >= 0 ? 'profit-text' : 'loss-text'} style={{textAlign: 'right', fontWeight: 600}}>
              {pos.profit >= 0 ? '+' : ''}{formatMoney(pos.profit)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default App
