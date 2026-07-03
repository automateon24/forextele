#!/usr/bin/env python3
"""
MULTI INDEX SCANNER V3
======================
Runs all 19 V3 strategies across 5 indices simultaneously, each in its own thread:
  - NIFTY      (security_id=13,  lot=75,  atm_step=50,  exchange=IDX_I)
  - BANKNIFTY  (security_id=25,  lot=15,  atm_step=100, exchange=IDX_I)
  - FINNIFTY   (security_id=27,  lot=40,  atm_step=50,  exchange=IDX_I)
  - MIDCPNIFTY (security_id=442, lot=75,  atm_step=25,  exchange=IDX_I)
  - SENSEX     (security_id=51,  lot=10,  atm_step=100, exchange=BSE_I)

Usage:
  py MULTI_INDEX_SCANNER_V3.py           <- SCAN ONLY (no orders) default
  py MULTI_INDEX_SCANNER_V3.py --live    <- LIVE ORDERS (real money)

Each index has its own:
  - DataFeed thread (fast 10s spot + slow 30s full chain)
  - ModularTrader engine with all 19 strategies
  - CSV trade log   daily_data/v3_trades_<INDEX>_<DATE>.csv
  - Log file        daily_data/v3_<INDEX>_<DATE>.log

Unified dashboard refreshes every 10s showing all indices side by side.

IMPORTANT: Do not use --live unless you want real orders to fire.
           Default scan-only mode analyses and logs signals but does NOT place orders.
"""

import json, time, logging, os, sys, threading, signal
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
sys.path.insert(0, r'c:\cursor\options\niftyopt\Lib\site-packages')

from dhanhq import dhanhq

# ── Parse CLI args ────────────────────────────────────────────────────────────
LIVE_ORDERS = '--live' in sys.argv
SCAN_ONLY   = not LIVE_ORDERS

# ═══════════════════════════════════════════════════════════════════════════════
# INDEX DEFINITIONS
# Each dict fully describes one tradeable index for V3 engine
# ═══════════════════════════════════════════════════════════════════════════════

INDEX_CONFIGS = [
    {
        'name':        'NIFTY',
        'security_id': '13',
        'exchange':    'IDX_I',
        'lot_size':    75,
        'atm_step':    50,
        'premium_max': 600,
    },
    {
        'name':        'BANKNIFTY',
        'security_id': '25',
        'exchange':    'IDX_I',
        'lot_size':    15,
        'atm_step':    100,
        'premium_max': 1200,
    },
    {
        'name':        'FINNIFTY',
        'security_id': '27',
        'exchange':    'IDX_I',
        'lot_size':    40,
        'atm_step':    50,
        'premium_max': 600,
    },
    {
        'name':        'MIDCPNIFTY',
        'security_id': '442',
        'exchange':    'IDX_I',
        'lot_size':    75,
        'atm_step':    25,
        'premium_max': 400,
    },
    {
        'name':        'SENSEX',
        'security_id': '51',
        'exchange':    'IDX_I',
        'lot_size':    10,
        'atm_step':    100,
        'premium_max': 2000,
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# SHARED CLIENT
# One Dhan client; all index engines share it (Dhan API is thread-safe for reads)
# ═══════════════════════════════════════════════════════════════════════════════

TOKEN_FILE = 'config/dhan_tokens.json'
CLIENT_ID  = '1101936133'

os.makedirs('daily_data', exist_ok=True)
today_str = datetime.now().strftime('%Y%m%d')

# Root logger — writes to a shared scanner log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-14s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(f'daily_data/multi_scanner_{today_str}.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
scanner_log = logging.getLogger('SCANNER')

# Global API throttle lock — Dhan API is NOT thread-safe for concurrent calls.
# All 5 index threads share this lock; each waits its turn before any API call.
_API_LOCK = threading.Lock()
_API_MIN_INTERVAL = 0.4  # seconds between calls globally
_api_last_call = 0.0

def _api_call(fn, *args, **kwargs):
    """Thread-safe wrapper: acquire global lock, respect min interval, call fn."""
    global _api_last_call
    with _API_LOCK:
        now = time.monotonic()
        wait = _API_MIN_INTERVAL - (now - _api_last_call)
        if wait > 0:
            time.sleep(wait)
        result = fn(*args, **kwargs)
        _api_last_call = time.monotonic()
    return result

def load_client() -> dhanhq:
    with open(TOKEN_FILE) as f:
        t = json.load(f)
    client = dhanhq(CLIENT_ID, t['access_token'])
    scanner_log.info("✅ Dhan API client connected")
    return client

# ═══════════════════════════════════════════════════════════════════════════════
# PER-INDEX STATUS  (lightweight snapshot for dashboard)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IndexStatus:
    name:           str
    spot:           float       = 0.0
    day_open:       float       = 0.0
    pcr:            float       = 1.0
    pcr_bias:       str         = 'NEUTRAL'
    rsi14:          float       = 0.0
    total_pnl:      float       = 0.0
    open_trades:    int         = 0
    total_trades:   int         = 0
    last_signal:    str         = '-'
    last_updated:   str         = '-'
    status:         str         = 'STARTING'
    error:          str         = ''

# ═══════════════════════════════════════════════════════════════════════════════
# INDEX ENGINE  — per-index thread running the full V3 logic
# ═══════════════════════════════════════════════════════════════════════════════

class IndexEngine(threading.Thread):
    """
    Each IndexEngine:
      - Runs in its own daemon thread
      - Creates its own DataFeed patched to the index's security_id / exchange / lot_size
      - Creates its own ModularTrader (all 19 strategies)
      - In SCAN_ONLY mode: analyzes signals but skips order placement
      - In LIVE mode: places real orders
      - Updates a shared IndexStatus dict every cycle for the dashboard
    """

    def __init__(self, cfg: dict, client: dhanhq, statuses: Dict[str, IndexStatus], scan_only: bool):
        super().__init__(name=f"Eng-{cfg['name']}", daemon=True)
        self.cfg        = cfg
        self.client     = client
        self.statuses   = statuses
        self.scan_only  = scan_only
        self.running    = False
        self.log        = logging.getLogger(cfg['name'])

        # Per-index log file
        fh = logging.FileHandler(
            f"daily_data/v3_{cfg['name']}_{today_str}.log", encoding='utf-8'
        )
        fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', '%H:%M:%S'))
        self.log.addHandler(fh)
        self.log.propagate = False  # don't double-print to root

    def stop(self):
        self.running = False

    # ── helpers ──────────────────────────────────────────────────────────────

    # ── main thread loop ─────────────────────────────────────────────────────

    def run(self):
        self.running = True
        name = self.cfg['name']
        self.statuses[name].status = 'STARTING'
        self.log.info(f"[{name}] Engine starting (scan_only={self.scan_only})")

        try:
            import MODULAR_TRADER_V3 as v3

            # Build DataFeed directly — fully index-parameterised, no global Config touch
            feed = _IndexDataFeed(self.cfg, self.client, self.log)
            feed.update()   # initial full fetch

            # Build all 19 strategy modules fresh for this index
            modules = self._build_modules(v3)
            module_dict = {m.name: m for m in modules}

            trade_manager = _IndexTradeManager(self.cfg, self.log)
            health_monitor = v3.LiveHealthMonitor.__new__(v3.LiveHealthMonitor)
            # Minimal init of health monitor
            health_monitor.trader = type('T', (), {
                'modules': modules,
                'trade_manager': trade_manager,
            })()
            health_monitor._lock  = threading.Lock()
            health_monitor._last_report = {}
            health_monitor._cycle = 0

            self.statuses[name].status = 'RUNNING'
            self.log.info(f"[{name}] ✅ Engine ready — {len(modules)} strategies")

            FAST_INTERVAL = 10
            SLOW_INTERVAL = 30
            last_full = 0.0

            while self.running:
                now = time.monotonic()
                try:
                    if now - last_full >= SLOW_INTERVAL:
                        feed.update()
                        last_full = time.monotonic()
                    else:
                        feed.fast_update()

                    data = feed.get_current_data()

                    # Exits always run
                    trade_manager.manage_exits(data, module_dict)

                    # Signal analysis
                    all_signals = []
                    for module in modules:
                        if not module.enabled:
                            continue
                        try:
                            sig = module.analyze(data)
                            if sig:
                                self.log.info(
                                    f"[{name}][SIGNAL] {module.display_name}: "
                                    f"{sig.strategy} {sig.direction} ({sig.confidence:.0%}) - {sig.reason}"
                                )
                                all_signals.append((sig, module))
                        except Exception as e:
                            self.log.error(f"[{name}][MODULE] {module.name}: {e}")

                    all_signals.sort(key=lambda x: x[0].confidence, reverse=True)

                    # FIX 2026-05-19: 1 CE + 1 PE max per cycle (mirrors V3 signal_cycle fix)
                    entered_dirs: set = set()
                    for sig, module in all_signals:
                        if sig.direction in entered_dirs:
                            continue
                        if not trade_manager.can_enter(module, sig.direction, data, sig.confidence):
                            continue
                        if self.scan_only:
                            self.log.info(
                                f"[{name}][SCAN] Would enter: {sig.direction} "
                                f"{sig.strategy} conf={sig.confidence:.0%} — ORDER SKIPPED (scan mode)"
                            )
                        else:
                            trade_manager.enter(sig, module, data)
                        entered_dirs.add(sig.direction)
                        if len(entered_dirs) >= 2:
                            break

                    # Update shared status for dashboard
                    self._update_status(name, data, trade_manager, all_signals)

                except Exception as e:
                    import traceback
                    self.log.error(f"[{name}] Cycle error: {e}\n{traceback.format_exc()}")
                    self.statuses[name].error = str(e)[:60]

                time.sleep(FAST_INTERVAL)

        except Exception as e:
            import traceback
            self.log.error(f"[{name}] Fatal: {e}\n{traceback.format_exc()}")
            self.statuses[name].status = 'ERROR'
            self.statuses[name].error  = str(e)[:80]
        finally:
            self.statuses[name].status = 'STOPPED'
            self.log.info(f"[{name}] Engine stopped")

    def _build_modules(self, v3):
        """Build fresh instances of all 19 strategy modules."""
        return [
            v3.UltimateDayHighLowModule(),
            v3.DayHighBearishModule(),
            v3.DayLowBullishModule(),
            v3.EnhancedBearishModule(),
            v3.EnhancedBullishModule(),
            v3.DayHighLowTraditionalModule(),
            v3.TrendFollowingModule(),
            v3.AIEnhancedModule(),
            v3.MeanReversionModule(),
            v3.ScalpingModule(),
            v3.BreakoutModule(),
            v3.VolatilityBreakoutModule(),
            v3.OptionsGreeksModule(),
            v3.MagicSquareModule(),
            v3.ShortUnwindModule(),
            v3.LongUnwindModule(),
            v3.ResistBreakModule(),
            v3.PutWriterSupportModule(),
            v3.OrderBlockReversalModule(),
        ]

    def _update_status(self, name, data, tm, signals):
        s = self.statuses[name]
        s.spot         = data.spot
        s.day_open     = data.day_open or 0.0
        s.pcr          = data.pcr
        s.pcr_bias     = data.pcr_bias
        s.rsi14        = data.rsi14 or 0.0
        s.total_pnl    = sum(t.pnl for t in tm.trades if t.pnl is not None)
        s.open_trades  = sum(1 for t in tm.trades if t.status == 'OPEN')
        s.total_trades = len([t for t in tm.trades if t.status == 'CLOSED'])
        s.last_updated = datetime.now().strftime('%H:%M:%S')
        if signals:
            top = signals[0][0]
            s.last_signal = f"{top.direction} {top.strategy[:12]} {top.confidence:.0%}"
        else:
            s.last_signal = '-'


# ═══════════════════════════════════════════════════════════════════════════════
# INDEX-SPECIFIC DATA FEED
# Thin wrapper around V3 DataFeed logic but parameterised per index
# ═══════════════════════════════════════════════════════════════════════════════

class _IndexDataFeed:
    """
    Lightweight copy of V3 DataFeed that uses per-index security_id/exchange/atm_step.
    Shares the same Dhan client but operates independently.
    """

    def __init__(self, cfg: dict, client: dhanhq, log):
        import MODULAR_TRADER_V3 as v3
        self.cfg    = cfg
        self.client = client
        self.log    = log
        self._lock  = threading.Lock()
        self._v3    = v3
        self.data = v3.MarketData(
            timestamp=datetime.now(), spot=0.0, day_open=None,
            day_high=None, day_low=None, prev_close=None, vix=None,
        )
        self._atm_step    = cfg['atm_step']
        self._sec_id      = str(cfg['security_id'])
        self._exch        = cfg['exchange']
        self._chain_exch  = cfg.get('chain_exchange', cfg['exchange'])  # BSE_D for SENSEX
        self._lot         = cfg['lot_size']
        self._pmax        = cfg['premium_max']

    def get_current_data(self):
        with self._lock:
            return self._copy()

    def _copy(self):
        v3 = self._v3
        d = self.data
        return v3.MarketData(
            timestamp=d.timestamp, spot=d.spot,
            day_open=d.day_open, day_high=d.day_high,
            day_low=d.day_low, prev_close=d.prev_close,
            vix=d.vix, closes=d.closes.copy(),
            chain=d.chain.copy(), pcr=d.pcr,
            pcr_bias=d.pcr_bias, pcr_zone_count=d.pcr_zone_count,
            pcr_raw_zone=d.pcr_raw_zone, vwap=d.vwap,
            ema5=d.ema5, ema20=d.ema20, rsi14=d.rsi14,
            atm_strike=d.atm_strike,
            max_call_oi_strike=d.max_call_oi_strike,
            max_put_oi_strike=d.max_put_oi_strike,
            prev_oi_state=d.prev_oi_state.copy(),
            prev_spot=d.prev_spot,
            put_oi_total=d.put_oi_total,
            call_oi_total=d.call_oi_total,
        )

    def fast_update(self) -> bool:
        """Spot price refresh only."""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            r = _api_call(self.client.intraday_minute_data,
                security_id=self._sec_id, exchange_segment=self._exch,
                instrument_type='INDEX', from_date=today, to_date=today, interval=1
            )
            if not (r and r.get('status') == 'success'):
                return False
            d = r.get('data', {})
            raw_closes = d.get('close', [])
            raw_highs  = d.get('high', [])
            raw_lows   = d.get('low', [])
            if not raw_closes:
                return False
            closes  = [float(c) for c in raw_closes]
            spot    = closes[-1]
            ph = raw_highs[:-1] if len(raw_highs) > 1 else raw_highs
            pl = raw_lows[:-1]  if len(raw_lows)  > 1 else raw_lows
            day_high = float(max(ph)) if ph else None
            day_low  = float(min(pl)) if pl else None
            vwap  = sum(closes) / len(closes)
            ema5  = self._ema(closes, 5)  if len(closes) >= 5  else None
            ema20 = self._ema(closes, 20) if len(closes) >= 20 else None
            rsi14 = self._rsi(closes, 14) if len(closes) >= 15 else None
            atm   = round(spot / self._atm_step) * self._atm_step
            with self._lock:
                self.data.prev_spot  = self.data.spot
                self.data.spot       = spot
                self.data.day_high   = day_high
                self.data.day_low    = day_low
                self.data.closes     = closes
                self.data.vwap       = vwap
                self.data.ema5       = ema5
                self.data.ema20      = ema20
                self.data.rsi14      = rsi14
                self.data.atm_strike = atm
                self.data.timestamp  = datetime.now()
            return True
        except Exception as e:
            self.log.warning(f"fast_update: {e}")
            return False

    def update(self):
        """Full update: spot + chain + OI + prev_close + VIX."""
        try:
            today     = datetime.now().strftime('%Y-%m-%d')
            yesterday = datetime.now().strftime('%Y-%m-%d')  # fallback; prev_close from hist

            # 1. Intraday
            r = _api_call(self.client.intraday_minute_data,
                security_id=self._sec_id, exchange_segment=self._exch,
                instrument_type='INDEX', from_date=today, to_date=today, interval=1
            )
            if not (r and r.get('status') == 'success'):
                self.log.warning("update: no intraday data")
                return
            d = r.get('data', {})
            raw_c = d.get('close', []);  raw_o = d.get('open', [])
            raw_h = d.get('high', []);   raw_l = d.get('low', [])
            if not raw_c:
                return
            closes   = [float(c) for c in raw_c]
            spot     = closes[-1]
            day_open = float(raw_o[0]) if raw_o else None
            ph = raw_h[:-1] if len(raw_h) > 1 else raw_h
            pl = raw_l[:-1] if len(raw_l) > 1 else raw_l
            day_high = float(max(ph)) if ph else None
            day_low  = float(min(pl)) if pl else None

            # 2. Prev close
            prev_close = None
            try:
                from datetime import timedelta
                y = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                h = _api_call(self.client.historical_daily_data,
                    security_id=self._sec_id, exchange_segment=self._exch,
                    instrument_type='INDEX', from_date=y, to_date=today
                )
                if h and h.get('status') == 'success':
                    hc = h.get('data', {}).get('close', [])
                    if hc:
                        prev_close = float(hc[-1])
            except:
                pass

            # 3. Option chain
            chain = self._fetch_chain(spot)

            if not chain:
                self.log.warning("update: empty chain")
                # Still update spot even if no chain
                atm  = round(spot / self._atm_step) * self._atm_step
                vwap = sum(closes) / len(closes)
                ema5  = self._ema(closes, 5)  if len(closes) >= 5  else None
                ema20 = self._ema(closes, 20) if len(closes) >= 20 else None
                rsi14 = self._rsi(closes, 14) if len(closes) >= 15 else None
                with self._lock:
                    self.data.spot = spot; self.data.day_open = day_open
                    self.data.day_high = day_high; self.data.day_low = day_low
                    self.data.prev_close = prev_close; self.data.closes = closes
                    self.data.vwap = vwap; self.data.ema5 = ema5
                    self.data.ema20 = ema20; self.data.rsi14 = rsi14
                    self.data.atm_strike = atm; self.data.timestamp = datetime.now()
                return

            # 4. OI + PCR
            put_oi  = sum(chain[s]['PE'].oi for s in chain if 'PE' in chain[s])
            call_oi = sum(chain[s]['CE'].oi for s in chain if 'CE' in chain[s])
            pcr     = put_oi / call_oi if call_oi > 0 else 1.0

            v3   = self._v3
            pcr_bias, pcr_zone_count, pcr_raw_zone = v3.DataFeed._calc_pcr_bias(
                pcr, put_oi, call_oi,
                self.data.pcr_zone_count, self.data.pcr_raw_zone
            )
            vwap  = sum(closes) / len(closes)
            ema5  = self._ema(closes, 5)  if len(closes) >= 5  else None
            ema20 = self._ema(closes, 20) if len(closes) >= 20 else None
            rsi14 = self._rsi(closes, 14) if len(closes) >= 15 else None
            atm   = round(spot / self._atm_step) * self._atm_step
            max_c = self._max_oi_strike(chain, 'CE')
            max_p = self._max_oi_strike(chain, 'PE')
            rsi_str = f"{rsi14:.0f}" if rsi14 is not None else "n/a"

            self.log.info(
                f"spot={spot:.0f} O={day_open} PCR={pcr:.3f}/{pcr_bias} "
                f"RSI={rsi_str} chain={len(chain)} strikes"
            )

            with self._lock:
                self.data.prev_oi_state = {
                    s: {'CE': chain[s]['CE'].oi if 'CE' in chain[s] else 0,
                        'PE': chain[s]['PE'].oi if 'PE' in chain[s] else 0}
                    for s in chain
                }
                self.data.prev_spot         = self.data.spot
                self.data.timestamp         = datetime.now()
                self.data.spot              = spot
                self.data.day_open          = day_open
                self.data.day_high          = day_high
                self.data.day_low           = day_low
                self.data.prev_close        = prev_close
                self.data.closes            = closes
                self.data.chain             = chain
                self.data.pcr               = pcr
                self.data.pcr_bias          = pcr_bias
                self.data.pcr_zone_count    = pcr_zone_count
                self.data.pcr_raw_zone      = pcr_raw_zone
                self.data.vwap              = vwap
                self.data.ema5              = ema5
                self.data.ema20             = ema20
                self.data.rsi14             = rsi14
                self.data.atm_strike        = atm
                self.data.max_call_oi_strike= max_c
                self.data.max_put_oi_strike = max_p
                self.data.put_oi_total      = put_oi
                self.data.call_oi_total     = call_oi

        except Exception as e:
            import traceback
            self.log.error(f"update error: {e}\n{traceback.format_exc()}")

    def _fetch_chain(self, spot: float) -> dict:
        try:
            sec_id = int(self._sec_id)
            exp_r  = _api_call(self.client.expiry_list,
                under_security_id=sec_id,
                under_exchange_segment=self._chain_exch
            )
            if not (exp_r and exp_r.get('status') == 'success'):
                return {}
            exp_data = exp_r.get('data', {})
            exp_list = exp_data.get('data', []) if isinstance(exp_data, dict) else exp_data
            if not exp_list:
                return {}
            expiry = exp_list[0]

            oc = _api_call(self.client.option_chain,
                under_security_id=sec_id,
                under_exchange_segment=self._chain_exch,
                expiry=expiry
            )
            if not (oc and oc.get('status') == 'success'):
                return {}
            data   = oc.get('data', {})
            oc_raw = None
            if isinstance(data, dict):
                if 'oc' in data:
                    oc_raw = data['oc']
                elif 'data' in data:
                    nested = data['data']
                    if isinstance(nested, dict):
                        oc_raw = nested.get('oc', {})
            if not oc_raw:
                return {}

            v3 = self._v3
            atm     = round(spot / self._atm_step) * self._atm_step
            n_wings = 20   # ±20 strikes each side
            allowed = set(atm + i * self._atm_step for i in range(-n_wings, n_wings + 1))
            result  = {}
            for sk, sdata in oc_raw.items():
                try:
                    strike = float(sk)
                    if strike not in allowed:
                        continue
                    entry = {}
                    for side, key in [('CE', 'ce'), ('PE', 'pe')]:
                        s = sdata.get(key) if isinstance(sdata, dict) else None
                        if not s:
                            continue
                        g   = s.get('greeks', {}) if isinstance(s, dict) else {}
                        ltp = float(s.get('last_price', 0) or 0)
                        if ltp <= 0:
                            continue
                        entry[side] = v3.OptionContract(
                            security_id=str(s.get('security_id', '')),
                            strike=strike, option_type=side, ltp=ltp,
                            iv=float(s.get('implied_volatility', 0) or 0),
                            delta=float(g.get('delta', 0) or 0),
                            gamma=float(g.get('gamma', 0) or 0),
                            theta=float(g.get('theta', 0) or 0),
                            vega=float(g.get('vega', 0) or 0),
                            oi=int(s.get('oi', 0) or 0),
                            volume=int(s.get('volume', 0) or 0),
                            bid=float(s.get('top_bid_price', ltp) or ltp),
                            ask=float(s.get('top_ask_price', ltp) or ltp),
                        )
                    if entry:
                        result[strike] = entry
                except:
                    continue
            return result
        except Exception as e:
            self.log.error(f"_fetch_chain: {e}")
            return {}

    # ── technical helpers (same maths as V3 DataFeed) ────────────────────────

    @staticmethod
    def _ema(closes, n):
        if len(closes) < n:
            return None
        k = 2 / (n + 1)
        ema = sum(closes[:n]) / n
        for c in closes[n:]:
            ema = c * k + ema * (1 - k)
        return ema

    @staticmethod
    def _rsi(closes, n=14):
        if len(closes) < n + 1:
            return None
        diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(d, 0) for d in diffs]
        losses= [abs(min(d, 0)) for d in diffs]
        ag = sum(gains[:n]) / n
        al = sum(losses[:n]) / n
        for i in range(n, len(diffs)):
            ag = (ag * (n-1) + gains[i]) / n
            al = (al * (n-1) + losses[i]) / n
        if al == 0:
            return 100
        rs = ag / al
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _max_oi_strike(chain, side):
        best_s, best_oi = None, 0
        for sk, data in chain.items():
            if side in data and data[side].oi > best_oi:
                best_oi = data[side].oi
                best_s  = sk
        return best_s


# ═══════════════════════════════════════════════════════════════════════════════
# INDEX TRADE MANAGER  (thin subclass of V3 TradeManager — index-specific CSV)
# ═══════════════════════════════════════════════════════════════════════════════

class _IndexTradeManager:
    """
    Delegates all real trade management to V3 TradeManager,
    but writes to a per-index CSV.
    Thread-safe: NEVER touches global Config — uses per-instance lot_size override.
    """
    def __init__(self, cfg: dict, log):
        import MODULAR_TRADER_V3 as v3
        self._tm = v3.TradeManager()
        self._tm.csv_file = f"daily_data/v3_trades_{cfg['name']}_{today_str}.csv"
        self._tm._init_csv()
        self._log  = log
        self._cfg  = cfg
        self._lot  = cfg['lot_size']   # authoritative lot for this index
        self._scan_only = SCAN_ONLY

    @property
    def trades(self):
        return self._tm.trades

    @property
    def same_dir_count(self):
        return self._tm.same_dir_count

    def can_enter(self, module, direction, data=None, confidence=0):
        return self._tm.can_enter(module, direction, data, confidence)

    def enter(self, signal, module, data):
        """Enter trade with index-specific lot size — no global Config mutation."""
        if self._scan_only:
            return
        import MODULAR_TRADER_V3 as v3
        # Directly call _enter_trade with overridden quantity
        qty = self._lot
        contract = signal.contract
        trade = v3.Trade(
            trade_id=f"{signal.module}_{signal.direction}{int(contract.strike)}_{datetime.now().strftime('%H%M%S')}",
            module=signal.module,
            strategy=signal.strategy,
            contract=contract,
            entry_price=contract.ltp,
            quantity=qty,
            stop_loss=contract.ltp * (1 - v3.Config.SL_PCT),
            target=contract.ltp * (1 + v3.Config.TARGET_PCT),
            status='OPEN',
            open_time=datetime.now(),
        )
        self._tm.trades.append(trade)
        self._tm.same_dir_count[contract.option_type] += 1
        module.open_trade = trade
        if module.name != 'MAGIC_SQUARE':
            module.trade_count += 1
        self._tm._log_to_csv(trade, 'ENTER', signal, '')
        self._log.info(
            f"[LIVE] ENTER {trade.trade_id} | {contract.option_type}{contract.strike:.0f} "
            f"@ Rs.{contract.ltp:.2f} x{qty} | SL={trade.stop_loss:.2f} TGT={trade.target:.2f}"
        )

    def manage_exits(self, data, module_dict):
        self._tm.manage_exits(data, module_dict)


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD  — unified terminal display refreshing every 10s
# ═══════════════════════════════════════════════════════════════════════════════

def print_dashboard(statuses: Dict[str, IndexStatus], scan_only: bool, elapsed_secs: int):
    os.system('cls' if os.name == 'nt' else 'clear')
    now_str = datetime.now().strftime('%H:%M:%S')
    mode    = 'SCAN ONLY (no orders)' if scan_only else '*** LIVE ORDERS ***'

    print("=" * 110)
    print(f"  MULTI-INDEX SCANNER V3  |  {now_str}  |  Mode: {mode}  |  Up: {elapsed_secs//60}m{elapsed_secs%60:02d}s")
    print("=" * 110)
    print(f"  {'INDEX':<12} {'SPOT':>9} {'OPEN':>7} {'BIAS':<9} {'RSI':>5} {'OPEN_T':>6} {'NET_PNL':>10} {'LAST SIGNAL':<30} {'STATUS'}")
    print("-" * 110)

    total_pnl = 0.0
    for name, s in statuses.items():
        chg = ((s.spot - s.day_open) / s.day_open * 100) if s.day_open else 0
        chg_str = f"{chg:+.2f}%" if s.day_open else "  n/a"
        pnl_str = f"Rs.{s.total_pnl:+,.0f}"
        err_str = f" [ERR: {s.error}]" if s.error else ""
        print(
            f"  {name:<12} {s.spot:>9.1f} {chg_str:>7} {s.pcr_bias:<9} "
            f"{s.rsi14:>5.0f} {s.open_trades:>6} {pnl_str:>10} "
            f"{s.last_signal:<30} {s.status}{err_str}"
        )
        total_pnl += s.total_pnl

    print("-" * 110)
    print(f"  {'COMBINED':12} {'':>9} {'':>7} {'':9} {'':5} {'':6} {'Rs.'+f'{total_pnl:+,.0f}':>10}")
    print("=" * 110)
    print(f"  Logs: daily_data/v3_<INDEX>_{today_str}.log   |   Press Ctrl+C to stop")
    print("=" * 110)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    scanner_log.info("=" * 80)
    scanner_log.info(f"MULTI-INDEX SCANNER V3 starting  |  scan_only={SCAN_ONLY}")
    scanner_log.info(f"Indices: {[c['name'] for c in INDEX_CONFIGS]}")
    scanner_log.info("=" * 80)

    # Load shared Dhan client
    try:
        client = load_client()
    except Exception as e:
        scanner_log.error(f"Cannot connect to Dhan API: {e}")
        sys.exit(1)

    # Shared status objects
    statuses: Dict[str, IndexStatus] = {
        cfg['name']: IndexStatus(name=cfg['name']) for cfg in INDEX_CONFIGS
    }

    # Create + start one engine per index
    engines: List[IndexEngine] = []
    for cfg in INDEX_CONFIGS:
        eng = IndexEngine(cfg, client, statuses, scan_only=SCAN_ONLY)
        engines.append(eng)
        time.sleep(1.5)   # stagger starts to avoid API burst
        eng.start()
        scanner_log.info(f"Started engine: {cfg['name']}")

    start_time = time.monotonic()

    # Graceful shutdown on Ctrl+C
    def _shutdown(sig, frame):
        scanner_log.info("Ctrl+C — stopping all engines...")
        for eng in engines:
            eng.stop()
        time.sleep(2)
        scanner_log.info("All engines stopped. Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    # Dashboard loop
    try:
        while True:
            elapsed = int(time.monotonic() - start_time)
            print_dashboard(statuses, SCAN_ONLY, elapsed)
            time.sleep(10)
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == '__main__':
    main()
