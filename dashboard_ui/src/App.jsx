import { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [data, setData] = useState({ mt5: null, ai_logs: [], server_time: '', telegram_status: '', strategies_scanning: 0, active_channels: [] })
  const [connected, setConnected] = useState(false)
  const [activeTab, setActiveTab] = useState('STRATEGIES') // 'STRATEGIES' or 'TELEGRAM'
  
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

  const totalUnrealized = positions.reduce((sum, p) => sum + (p.profit || 0), 0)
  
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
          <div className="metric-label">CAPITAL BASE</div>
          <div className="metric-value">{formatMoney(account.equity)}</div>
          <div className="metric-sub">Shared Portfolio Base</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">USED MARGIN</div>
          <div className="metric-value">{formatMoney(account.margin)}</div>
          <div className="metric-sub">{formatNumber((account.margin / account.equity)*100)}% Allocation</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">TOTAL TRADES</div>
          <div className="metric-value">{positions.length}</div>
          <div className="metric-sub">{positions.length} Active / {data.mt5?.wins !== undefined ? data.mt5.wins + data.mt5.losses : 0} Closed</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">WIN RATE</div>
          <div className="metric-value" style={{color: (data.mt5?.win_rate || 0) >= 50 ? '#10b981' : '#ef4444'}}>{data.mt5?.win_rate || 0.0}%</div>
          <div className="metric-sub">{data.mt5?.wins || 0} W / {data.mt5?.losses || 0} L</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">TODAY'S REALIZED PNL</div>
          <div className={`metric-value ${data.mt5?.today_pnl >= 0 ? 'profit-text' : 'loss-text'}`}>
            {data.mt5?.today_pnl >= 0 ? '+' : ''}{formatMoney(data.mt5?.today_pnl || 0)}
          </div>
          <div className="metric-sub">Booked Trades</div>
        </div>
        <div className="metric-box">
          <div className="metric-label">LIVE UNREALIZED PNL</div>
          <div className={`metric-value ${totalUnrealized >= 0 ? 'profit-text' : 'loss-text'}`}>
            {totalUnrealized >= 0 ? '+' : ''}{formatMoney(totalUnrealized)}
          </div>
          <div className="metric-sub">Open Positions</div>
        </div>
      </div>

      {/* ACTIVE POSITIONS TABLE */}
      <div className="panel-container">
        <div className="panel-header">
          Active Positions ({activeTab === 'STRATEGIES' ? 'Ultimate Strategies' : 'Telegram Signals'})
        </div>
        <div className="panel-body">
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
          Today's Completed Trades History
        </div>
        <div className="panel-body">
          <div className="no-trades-sub">No completed trades today.</div>
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
    </div>
  )
}

function TradeTable({ positions, formatMoney, formatPrice }) {
  if (positions.length === 0) return <div className="no-trades">No active trades.</div>
  
  return (
    <table className="data-table">
      <thead>
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
