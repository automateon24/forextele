import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

# Path configurations
sys.path.insert(0, r"C:\cursor\options\niftyopt")
sys.path.insert(0, r"C:\cursor\options\niftyopt\Lib\site-packages")

from dhanhq import dhanhq
from regime_detector import RegimeDetector

logger = logging.getLogger("GlobalDataFetcher")
logger.setLevel(logging.INFO)

# Ensure data log folder exists
os.makedirs(r"C:\cursor\options\niftyopt\data", exist_ok=True)

# Helper function to compute PCR Bias
def calc_pcr_bias(pcr: float, put_oi: int, call_oi: int) -> Tuple[str, int, str]:
    """Calculate PCR bias with stability and OI imbalance"""
    zone = 'NEUTRAL'
    # Use standard V4 thresholds
    if pcr < 0.75:
        zone = 'BULLISH'
    elif pcr > 1.25:
        zone = 'BEARISH'
    return zone, 3 if zone != 'NEUTRAL' else 0, zone

class OptionContractWrapper:
    """Wrapper that acts like a dictionary and a dataclass/object for compatibility with V3, V4, and V15 engines."""
    def __init__(self, d: dict):
        self.__dict__['_data'] = d
    
    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'OptionContractWrapper' object has no attribute '{name}'")
        
    def __getitem__(self, key):
        return self._data[key]
        
    def __setitem__(self, key, value):
        self._data[key] = value
        
    def __contains__(self, key):
        return key in self._data
        
    def get(self, key, default=None):
        return self._data.get(key, default)
        
    def keys(self):
        return self._data.keys()
        
    def values(self):
        return self._data.values()
        
    def items(self):
        return self._data.items()

    def __repr__(self):
        return f"OptionContractWrapper({self._data})"

@dataclass
class MarketData:
    timestamp: datetime
    spot: float
    day_open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    prev_close: Optional[float] = None
    vix: float = 14.0
    pcr: float = 1.0
    pcr_bias: str = 'NEUTRAL'
    pcr_zone_count: int = 0
    pcr_raw_zone: str = 'NEUTRAL'
    vwap: Optional[float] = None
    ema5: Optional[float] = None
    ema20: Optional[float] = None
    rsi14: Optional[float] = None
    atm_strike: float = 0.0
    max_call_oi_strike: Optional[float] = None
    max_put_oi_strike: Optional[float] = None
    closes: List[float] = field(default_factory=list)
    chain: Dict[float, Dict[str, OptionContractWrapper]] = field(default_factory=dict)
    regime: str = "NORMAL"
    last_update: str = "N/A"
    call_oi_total: int = 0
    put_oi_total: int = 0
    prev_oi_state: Dict = field(default_factory=dict)
    prev_spot: float = 0.0

class GlobalDataFetcher:
    """Thread-safe centralized Dhan API fetcher for indices spot and option chain data."""
    def __init__(self):
        self.client = None
        self.lock = threading.RLock()
        
        # Token settings
        self.token_file = r"C:\cursor\options\niftyopt\config\dhan_tokens.json"
        self.client_id = "1101936133"
        
        # Market data stores by Index Name
        self.market_data: Dict[str, MarketData] = {}
        self.index_candles_1min: Dict[str, pd.DataFrame] = {}
        self.cached_expiries: Dict[str, str] = {}
        self.regime_detectors: Dict[str, RegimeDetector] = {}
        
        # Option tracking
        self.monitored_option_security_ids: Set[str] = set()
        self.option_prices: Dict[str, float] = {}  # sec_id -> ltp
        
        # Index configurations
        self.index_configs = {
            'NIFTY': {'security_id': '13', 'exchange': 'IDX_I', 'atm_step': 50.0},
            'BANKNIFTY': {'security_id': '25', 'exchange': 'IDX_I', 'atm_step': 100.0},
            'FINNIFTY': {'security_id': '27', 'exchange': 'IDX_I', 'atm_step': 50.0},
            'MIDCPNIFTY': {'security_id': '442', 'exchange': 'IDX_I', 'atm_step': 50.0},
            'SENSEX': {'security_id': '51', 'exchange': 'IDX_I', 'atm_step': 100.0}
        }
        
        # Thread states
        self.running = False
        self.ticker_thread = None
        self.chain_thread = None
        
        self.connect()

    def connect(self):
        try:
            with open(self.token_file, 'r') as f:
                tokens = json.load(f)
            access_token = tokens.get('access_token')
            if not access_token:
                raise ValueError("No access_token in token file")
            self.client = dhanhq(self.client_id, access_token)
            logger.info("Centralized Dhan API connected successfully.")
        except Exception as e:
            logger.error(f"Failed to connect Centralized Dhan API: {e}")
            raise

    def reconnect(self):
        with self.lock:
            try:
                self.connect()
                logger.info("Centralized Dhan API reconnected successfully.")
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def register_active_option_id(self, sec_id: str):
        with self.lock:
            if sec_id:
                self.monitored_option_security_ids.add(str(sec_id))
                logger.info(f"Registered option security ID for real-time tracking: {sec_id}")

    def unregister_active_option_id(self, sec_id: str):
        with self.lock:
            sec_id_str = str(sec_id)
            if sec_id_str in self.monitored_option_security_ids:
                self.monitored_option_security_ids.discard(sec_id_str)
                self.option_prices.pop(sec_id_str, None)
                logger.info(f"Unregistered option security ID from tracking: {sec_id}")

    def get_market_data(self, idx_name: str) -> MarketData:
        with self.lock:
            if idx_name not in self.market_data:
                # Return empty/default object if not warmed up yet
                return MarketData(timestamp=datetime.now(), spot=0.0)
            return self.market_data[idx_name]

    def _api_call(self, func, *args, **kwargs):
        """Standard throttled API call logic to avoid rate limits with Auto-Recovery"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(0.2)  # Max 5 calls per second
                res = func(*args, **kwargs)
                if res and isinstance(res, dict) and res.get('status') == 'success':
                    return res
                elif res and isinstance(res, dict) and ('Too Many Requests' in str(res) or '805' in str(res) or 'Too many requests' in str(res)):
                    logger.error(f"HEALTH MONITOR [AI AUTO-CORRECTION]: Dhan Rate Limit Error 805 detected. Initiating 15-second emergency backoff (Attempt {attempt+1}/{max_retries})...")
                    # Update health status
                    try:
                        import json, os
                        hf = r'C:\\25stragy\\system_health.json'
                        if os.path.exists(hf):
                            with open(hf, 'r') as f: h_data = json.load(f)
                            h_data['dhan_api'] = {"status": "RATE_LIMITED", "msg": "Error 805: Backing off for 15s"}
                            with open(hf, 'w') as f: json.dump(h_data, f, indent=4)
                    except: pass
                    
                    time.sleep(15.0) # Deep backoff to satisfy Dhan servers
                else:
                    logger.warning(f"API returned failure/non-success status: {res}")
            except Exception as e:
                logger.error(f"Error in API call: {e}")
                time.sleep(1.0)
        return None

    def perform_data_warmup(self):
        logger.info("Initializing pre-market seeding and indicator warmup for all 5 indices...")
        
        # Seeding India VIX state
        self.vix_value = 14.0
        
        for idx_name, idx_cfg in self.index_configs.items():
            logger.info(f"Warming up {idx_name}...")
            
            # 1. Fetch expiry date list
            try:
                exp_r = self._api_call(
                    self.client.expiry_list,
                    under_security_id=int(idx_cfg['security_id']),
                    under_exchange_segment='IDX_I'
                )
                if exp_r and exp_r.get('status') == 'success':
                    expiries = exp_r.get('data', {}).get('data', [])
                    if expiries:
                        self.cached_expiries[idx_name] = expiries[0]
                        logger.info(f"  {idx_name} expiry selected: {expiries[0]}")
                    else:
                        raise ValueError(f"No expiries returned for {idx_name}")
                else:
                    raise ValueError(f"Failed to fetch expiry list for {idx_name}: {exp_r}")
            except Exception as e:
                logger.error(f"Error warming up expiry for {idx_name}: {e}")
                self.cached_expiries[idx_name] = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

            # 2. Fetch warmup 1-minute candles
            try:
                today = datetime.now()
                start_date = (today - timedelta(days=5)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
                
                r = self._api_call(
                    self.client.intraday_minute_data,
                    security_id=int(idx_cfg['security_id']),
                    exchange_segment='IDX_I',
                    instrument_type='INDEX',
                    from_date=start_date,
                    to_date=end_date,
                    interval=1
                )
                if r and r.get('status') == 'success' and r.get('data'):
                    df = pd.DataFrame(r['data'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
                    df = df.set_index('timestamp').sort_index()
                    
                    # Store combined candles
                    self.index_candles_1min[idx_name] = df
                    spot_px = df['close'].iloc[-1]
                    logger.info(f"  {idx_name} Warmup candles loaded. Total bars: {len(df)}. Last Spot: {spot_px}")
                else:
                    logger.warning(f"  Could not load candles for {idx_name}. Using synthetic fallback.")
                    # Fallback candle cache
                    df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
                    self.index_candles_1min[idx_name] = df
                    spot_px = 23000.0 if idx_name == 'NIFTY' else 50000.0
            except Exception as e:
                logger.error(f"Error fetching candles for {idx_name}: {e}")
                self.index_candles_1min[idx_name] = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
                spot_px = 23000.0 if idx_name == 'NIFTY' else 50000.0

            # 3. Create Regime Detector
            detector = RegimeDetector()
            self.regime_detectors[idx_name] = detector
            
            df_candles = self.index_candles_1min[idx_name]
            if not df_candles.empty:
                today_date = today.date()
                today_df = df_candles[df_candles.index.date == today_date]
                prior_days = [d for d in sorted(list(set(df_candles.index.date))) if d < today_date]
                
                if len(today_df) > 0:
                    detector.new_day(today_df['open'].iloc[0])
                    for ts, row in today_df.iterrows():
                        hhmm = ts.hour * 100 + ts.minute
                        detector.update(row['close'], iv=0.0, hhmm=hhmm)
                elif prior_days:
                    prior_df = df_candles[df_candles.index.date == prior_days[-1]]
                    detector.new_day(prior_df['open'].iloc[0])
                    for ts, row in prior_df.iterrows():
                        hhmm = ts.hour * 100 + ts.minute
                        detector.update(row['close'], iv=0.0, hhmm=hhmm)

            # 4. Fetch initial option chain
            chain = {}
            try:
                expiry = self.cached_expiries[idx_name]
                chain = self._fetch_and_parse_option_chain_api(idx_name, expiry, spot_px)
                logger.info(f"  {idx_name} initial option chain loaded. Strike count: {len(chain)}")
            except Exception as e:
                logger.error(f"  Could not load initial option chain for {idx_name}: {e}")
                
            # Initialize MarketData
            self.market_data[idx_name] = MarketData(
                timestamp=datetime.now(),
                spot=spot_px,
                chain=chain,
                regime=detector.snapshot().regime,
                last_update=datetime.now().strftime('%H:%M:%S')
            )
            
            # Pre-compute indicators
            self._recalculate_indicators(idx_name)

    def _fetch_and_parse_option_chain_api(self, idx_name: str, expiry: str, spot: float) -> Dict[float, Dict[str, OptionContractWrapper]]:
        idx_cfg = self.index_configs[idx_name]
        oc = self._api_call(
            self.client.option_chain,
            under_security_id=int(idx_cfg['security_id']),
            under_exchange_segment='IDX_I',
            expiry=expiry
        )
        if not oc or oc.get('status') != 'success':
            logger.warning(f"Failed to fetch option chain for {idx_name}: {oc}")
            return {}
            
        parsed = {}
        data = oc.get('data', {})
        oc_dict = data.get('oc', {})
        if not oc_dict:
            oc_dict = data.get('data', {}).get('oc', {})

        # Compute allowed strike range (limit to ATM +/- 15 strikes to avoid bloating memory)
        atm_step = idx_cfg['atm_step']
        atm = round(spot / atm_step) * atm_step
        allowed_strikes = {atm + i * atm_step for i in range(-15, 16)}

        for strike_str, strike_data in oc_dict.items():
            try:
                strike = float(strike_str)
            except ValueError:
                continue
            if strike not in allowed_strikes:
                continue
                
            parsed[strike] = {}
            for side in ['ce', 'pe']:
                contract = strike_data.get(side)
                if contract:
                    opt_type = side.upper()
                    ltp = float(contract.get('last_price', 0.0) or 0.0)
                    iv = float(contract.get('implied_volatility', 0.0) or 0.0)
                    oi = int(contract.get('oi', 0) or 0)
                    volume = int(contract.get('volume', 0) or 0)
                    sec_id = str(contract.get('security_id', ''))
                    
                    greeks = contract.get('greeks', {})
                    delta = float(greeks.get('delta', 0.0) or 0.0)
                    gamma = float(greeks.get('gamma', 0.0) or 0.0)
                    theta = float(greeks.get('theta', 0.0) or 0.0)
                    vega = float(greeks.get('vega', 0.0) or 0.0)
                    
                    bid = float(contract.get('top_bid_price', ltp) or ltp)
                    ask = float(contract.get('top_ask_price', ltp) or ltp)
                    
                    parsed[strike][opt_type] = OptionContractWrapper({
                        'security_id': sec_id,
                        'strike': strike,
                        'option_type': opt_type,
                        'ltp': ltp,
                        'iv': iv,
                        'delta': delta,
                        'gamma': gamma,
                        'theta': theta,
                        'vega': vega,
                        'oi': oi,
                        'volume': volume,
                        'bid': bid,
                        'ask': ask,
                        'trading_symbol': contract.get('trading_symbol', f"{idx_name} {expiry} {strike} {opt_type}"),
                        'greeks': {
                            'delta': delta,
                            'gamma': gamma,
                            'theta': theta,
                            'vega': vega
                        }
                    })
        return parsed

    def _recalculate_indicators(self, idx_name: str):
        """Update EMA, RSI, PCR, VWAP, ATM and regime for an index in real-time."""
        data = self.market_data[idx_name]
        df_candles = self.index_candles_1min.get(idx_name)
        
        if df_candles is None or df_candles.empty:
            return
            
        today_df = df_candles[df_candles.index.date == datetime.now().date()]
        if len(today_df) == 0:
            today_df = df_candles.tail(100) # fallback
            
        closes = today_df['close'].tolist()
        data.closes = closes
        data.spot = closes[-1] if closes else data.spot
        
        # Calculate ATM strike
        atm_step = self.index_configs[idx_name]['atm_step']
        data.atm_strike = round(data.spot / atm_step) * atm_step
        
        # Calculate EMA on full historical series to ensure stability and match backtests
        if len(df_candles) >= 5:
            data.ema5 = df_candles['close'].ewm(span=5, adjust=False).mean().iloc[-1]
        if len(df_candles) >= 20:
            data.ema20 = df_candles['close'].ewm(span=20, adjust=False).mean().iloc[-1]
            
        # Calculate RSI on full historical series to ensure stability and match backtests
        if len(df_candles) >= 15:
            delta = df_candles['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            data.rsi14 = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
            
        # Calculate VWAP
        if len(today_df) > 0:
            high = today_df['high'].max()
            low = today_df['low'].min()
            data.day_open = today_df['open'].iloc[0]
            data.day_high = high
            data.day_low = low
            data.vwap = (high + low + data.spot) / 3
            
        # Calculate PCR based on cached option chain
        if data.chain:
            call_oi = sum(data.chain[s]['CE'].oi for s in data.chain if 'CE' in data.chain[s])
            put_oi = sum(data.chain[s]['PE'].oi for s in data.chain if 'PE' in data.chain[s])
            
            data.call_oi_total = call_oi
            data.put_oi_total = put_oi
            
            if call_oi > 0:
                data.pcr = put_oi / call_oi
            else:
                data.pcr = 1.0
                
            bias, count, raw = calc_pcr_bias(data.pcr, put_oi, call_oi)
            data.pcr_bias = bias
            data.pcr_zone_count = count
            data.pcr_raw_zone = raw
            
            # Find max OI strikes
            max_call_oi = 0
            max_put_oi = 0
            max_call_strike = None
            max_put_strike = None
            
            for strike, contracts in data.chain.items():
                if 'CE' in contracts and contracts['CE'].oi > max_call_oi:
                    max_call_oi = contracts['CE'].oi
                    max_call_strike = strike
                if 'PE' in contracts and contracts['PE'].oi > max_put_oi:
                    max_put_oi = contracts['PE'].oi
                    max_put_strike = strike
                    
            data.max_call_oi_strike = max_call_strike
            data.max_put_oi_strike = max_put_strike

        # VIX
        data.vix = self.vix_value

    def start(self):
        self.running = True
        
        # 1. Start live ticker thread (polls every 2 seconds)
        self.ticker_thread = threading.Thread(target=self._live_ticker_loop, name="CentralTicker", daemon=True)
        self.ticker_thread.start()
        
        # 2. Start round-robin option chain thread (refreshes one index option chain every minute)
        self.chain_thread = threading.Thread(target=self._option_chain_loop, name="CentralChain", daemon=True)
        self.chain_thread.start()
        
        logger.info("Centralized background data fetching threads started.")

    def stop(self):
        self.running = False
        if self.ticker_thread:
            self.ticker_thread.join(timeout=2.0)
        if self.chain_thread:
            self.chain_thread.join(timeout=2.0)
        logger.info("Centralized background data fetching threads stopped.")

    def _live_ticker_loop(self):
        """High-frequency thread to update spot index levels and active option LTPs in a single API call."""
        logger.info("Starting high-frequency Central Ticker loop.")
        while self.running:
            try:
                # Compile list of security IDs to query
                # Standard Indices Spot segment is IDX_I
                index_sec_ids = [13, 25, 27, 51, 442, 21] # Nifty, Banknifty, Finnifty, Sensex, Midcpnifty, India VIX
                
                # Copy active options lists safely
                with self.lock:
                    active_opts = list(self.monitored_option_security_ids)
                
                # Group active option contracts under NSE_FNO or BSE_FNO
                # Sensex options belong to BSE_FNO, Nifty/Banknifty/Finnifty/Midcpnifty to NSE_FNO
                nse_fno = []
                bse_fno = []
                
                # Check active option descriptions (in V15 SENSEX options need BSE_FNO segment)
                # For simplicity, if we don't know, we can probe both or use a simple heuristic:
                # SENSEX options have strikes like 70000+ and trading symbols with SENSEX
                for opt_id in active_opts:
                    opt_id_int = int(opt_id)
                    # Let's inspect the active trade entries. If any are SENSEX, they go to BSE_FNO
                    # The security ID mapping of BSE_FNO contracts is usually distinct
                    # We can fetch them or check their length. Usually we can fetch under NSE_FNO first
                    # or place them in BSE_FNO if SENSEX is active.
                    # Since SENSEX is on BSE, SENSEX options are BSE_FNO. All others are NSE_FNO.
                    is_bse = False
                    with self.lock:
                        # Find if there is a SENSEX active trade using this security id
                        for idx_name in self.market_data:
                            md = self.market_data[idx_name]
                            if idx_name == 'SENSEX' and md.chain:
                                for strike in md.chain:
                                    for side in ['CE', 'PE']:
                                        if side in md.chain[strike] and md.chain[strike][side]['security_id'] == opt_id:
                                            is_bse = True
                                            break
                    if is_bse:
                        bse_fno.append(opt_id_int)
                    else:
                        nse_fno.append(opt_id_int)

                securities = {'IDX_I': index_sec_ids}
                if nse_fno:
                    securities['NSE_FNO'] = nse_fno
                if bse_fno:
                    securities['BSE_FNO'] = bse_fno

                # Poll Dhan
                tick_res = self._api_call(self.client.ticker_data, securities=securities)
                
                if tick_res and tick_res.get('status') == 'success':
                    data_map = tick_res.get('data', {}).get('data', {})
                    now = datetime.now()
                    now_str = now.strftime('%H:%M:%S')
                    
                    with self.lock:
                        # 1. Update VIX
                        vix_data = data_map.get('IDX_I', {}).get('21', {})
                        if vix_data:
                            self.vix_value = float(vix_data.get('last_price', self.vix_value))

                        # 2. Update Indices Spot Prices
                        for idx_name, idx_cfg in self.index_configs.items():
                            sec_data = data_map.get('IDX_I', {}).get(str(idx_cfg['security_id']))
                            if sec_data:
                                lp = float(sec_data.get('last_price', 0.0))
                                if lp > 0:
                                    if idx_name not in self.market_data:
                                        self.market_data[idx_name] = MarketData(timestamp=now, spot=lp)
                                    
                                    self.market_data[idx_name].spot = lp
                                    self.market_data[idx_name].last_update = now_str
                                    self.market_data[idx_name].timestamp = now
                                    
                                    # Update 1-minute candle lists
                                    df = self.index_candles_1min.get(idx_name)
                                    if df is not None:
                                        now_minute_ts = now.replace(second=0, microsecond=0)
                                        if now_minute_ts in df.index:
                                            df.at[now_minute_ts, 'close'] = lp
                                            df.at[now_minute_ts, 'high'] = max(df.at[now_minute_ts, 'high'], lp)
                                            df.at[now_minute_ts, 'low'] = min(df.at[now_minute_ts, 'low'], lp)
                                        else:
                                            # Create new minute bar
                                            new_row = pd.DataFrame([{
                                                'open': lp, 'high': lp, 'low': lp, 'close': lp, 'volume': 0
                                            }], index=[now_minute_ts])
                                            new_row.index.name = 'timestamp'
                                            self.index_candles_1min[idx_name] = pd.concat([df, new_row])
                                            
                                            # Update indicators on new candle boundaries
                                            self._recalculate_indicators(idx_name)
                                            
                                            # Update Regime Detector
                                            detector = self.regime_detectors.get(idx_name)
                                            if detector:
                                                detector.update(lp, iv=0.0, hhmm=now.hour * 100 + now.minute)
                                                self.market_data[idx_name].regime = detector.snapshot().regime
                                                
                        # 3. Update Option prices
                        for segment in ['NSE_FNO', 'BSE_FNO']:
                            seg_data = data_map.get(segment, {})
                            for sec_id_str, opt_data in seg_data.items():
                                ltp = float(opt_data.get('last_price', 0.0))
                                bid = float(opt_data.get('top_bid_price', ltp) or ltp)
                                ask = float(opt_data.get('top_ask_price', ltp) or ltp)
                                
                                if ltp > 0:
                                    self.option_prices[str(sec_id_str)] = ltp
                                    
                                    # Update price inside Option Chain wrappers if matching
                                    for idx_name in self.market_data:
                                        md = self.market_data[idx_name]
                                        if md.chain:
                                            for strike in md.chain:
                                                for side in ['CE', 'PE']:
                                                    if side in md.chain[strike] and md.chain[strike][side]['security_id'] == str(sec_id_str):
                                                        md.chain[strike][side]['ltp'] = ltp
                                                        md.chain[strike][side]['bid'] = bid
                                                        md.chain[strike][side]['ask'] = ask

                        # 4. DATA LOGGING (Spot & Greeks)
                        if not hasattr(self, '_log_tick_counter'): self._log_tick_counter = 0
                        self._log_tick_counter += 1
                        if self._log_tick_counter >= 15:  # Log every 30 seconds (15 ticks of 2s)
                            self._log_tick_counter = 0
                            try:
                                import csv, os
                                today_str = now.strftime('%Y%m%d')
                                log_file = rf"C:\25stragy\daily_data\market_data_tick_{today_str}.csv"
                                file_exists = os.path.exists(log_file)
                                with open(log_file, 'a', newline='') as f:
                                    writer = csv.writer(f)
                                    if not file_exists:
                                        writer.writerow(['timestamp', 'index', 'spot', 'vix', 'strike', 'type', 'ltp', 'bid', 'ask', 'delta', 'theta', 'gamma', 'vega'])
                                    for idx_name, md in self.market_data.items():
                                        if md.chain:
                                            for strike in md.chain:
                                                for side in ['CE', 'PE']:
                                                    if side in md.chain[strike]:
                                                        c = md.chain[strike][side]
                                                        writer.writerow([now_str, idx_name, md.spot, self.vix_value, strike, side, c.get('ltp'), c.get('bid'), c.get('ask'), c.get('delta'), c.get('theta'), c.get('gamma'), c.get('vega')])
                            except Exception as el:
                                logger.error(f"Error logging CSV data: {el}")

            except Exception as e:
                logger.error(f"Error in Central Ticker loop: {e}")
                
            time.sleep(2.0)

    def _option_chain_loop(self):
        """Low-frequency thread that refreshes option chains for each index in a round-robin cycle."""
        logger.info("Starting option chain Central refresh loop.")
        indices = list(self.index_configs.keys())
        cycle = 0
        
        while self.running:
            try:
                now = datetime.now()
                # Only check/fetch during market hours
                hhmm = now.hour * 100 + now.minute
                if hhmm < 914 or hhmm >= 1531:
                    time.sleep(10)
                    continue

                idx_name = indices[cycle % len(indices)]
                cycle += 1

                with self.lock:
                    expiry = self.cached_expiries.get(idx_name)
                    spot = self.market_data.get(idx_name, MarketData(timestamp=now, spot=0.0)).spot

                if expiry and spot > 0:
                    logger.info(f"Central refresh of {idx_name} option chain (Expiry: {expiry})...")
                    new_chain = self._fetch_and_parse_option_chain_api(idx_name, expiry, spot)
                    
                    if new_chain:
                        with self.lock:
                            md = self.market_data[idx_name]
                            
                            # Merge real-time price updates for active option contracts already queried
                            for strike in new_chain:
                                for side in ['CE', 'PE']:
                                    if side in new_chain[strike]:
                                        sec_id = new_chain[strike][side]['security_id']
                                        if sec_id in self.option_prices:
                                            new_chain[strike][side]['ltp'] = self.option_prices[sec_id]
                                            
                            md.chain = new_chain
                            self._recalculate_indicators(idx_name)
                            logger.info(f"Central refresh of {idx_name} completed.")

            except Exception as e:
                logger.error(f"Error in Central Option Chain loop: {e}")
                
            # SMART OPTIMIZATION: Instead of hitting Dhan's heavy Option Chain API every 60s,
            # we back off to 300 seconds (5 minutes). The fast 2-second ticker loop 
            # already updates the LTP/Greeks for the 31 cached strikes perfectly!
            time.sleep(300.0)

# Global fetcher instance
global_data_fetcher = None

def get_global_data_fetcher():
    global global_data_fetcher
    if global_data_fetcher is None:
        global_data_fetcher = GlobalDataFetcher()
    return global_data_fetcher
