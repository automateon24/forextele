"""
1-WEEK BACKTEST — All 41 Strategies × 8 Symbols
Uses MT5 historical data. Reports PnL per strategy per pair.
"""
import json
import logging
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
DNA_PATH = BASE_DIR / "25stragy" / "ai_optimized_forex_dna.json"
CFG_PATH = BASE_DIR / "mt5_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

SYMBOLS = {
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY",
    "AUDUSD": "AUDUSD", "GOLD": "GOLD", "SILVER": "SILVER",
    "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD"
}
FIXED_LOT   = 0.10   # Fixed 0.10 lot for all backtests
ACCOUNT_BAL = 10000  # Simulated $10k account

# ─── MT5 CONNECT ────────────────────────────────────────────────────────────
def connect():
    if mt5.initialize(): return True
    with open(CFG_PATH) as f: cfg = json.load(f)
    return mt5.initialize(login=int(cfg["login"]), server=cfg["server"], password=cfg["password"])

# ─── LOAD DNA ────────────────────────────────────────────────────────────────
def load_dna():
    with open(DNA_PATH) as f:
        return json.load(f).get("strategies", {})

# ─── INDICATOR HELPERS ───────────────────────────────────────────────────────
def rsi(s, p=14):
    d=s.diff(); g=d.where(d>0,0).rolling(p).mean(); l=(-d.where(d<0,0)).rolling(p).mean()
    return 100-100/(1+g/l.replace(0,np.nan))

def bollinger(s, p=20, std=2.0):
    m=s.rolling(p).mean(); b=s.rolling(p).std()*std
    return m, m+b, m-b

def macd_line(s):
    return s.ewm(span=12).mean() - s.ewm(span=26).mean()

def adx_series(df, p=14):
    tr=pd.concat([df['high']-df['low'],(df['high']-df['close'].shift()).abs(),(df['low']-df['close'].shift()).abs()],axis=1).max(axis=1)
    dmp=((df['high']-df['high'].shift())>(df['low'].shift()-df['low'])).astype(float)*(df['high']-df['high'].shift()).clip(lower=0)
    dmn=((df['low'].shift()-df['low'])>(df['high']-df['high'].shift())).astype(float)*(df['low'].shift()-df['low']).clip(lower=0)
    atr=tr.rolling(p).mean()
    di_p=100*(dmp.rolling(p).mean()/atr); di_n=100*(dmn.rolling(p).mean()/atr)
    dx=(abs(di_p-di_n)/(di_p+di_n).replace(0,1))*100
    return dx.rolling(p).mean()

# ─── FETCH HISTORICAL DATA ───────────────────────────────────────────────────
def fetch(symbol, tf, bars=2000):
    r = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if r is None or len(r) == 0: return None
    df = pd.DataFrame(r)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    for c in ['open','high','low','close']:
        df[c] = df[c].astype(float)
    # Volume may not exist on all brokers
    if 'tick_volume' in df.columns:
        df['volume'] = df['tick_volume'].astype(float)
    elif 'real_volume' in df.columns:
        df['volume'] = df['real_volume'].astype(float)
    else:
        df['volume'] = 1.0  # Fallback constant
    return df

# ─── SIGNAL GENERATOR ────────────────────────────────────────────────────────
def generate_signals(symbol, mt5_sym, dna_db, target_key=None, pre_df5=None, pre_df15=None, pre_df1h=None):
    """Returns list of {time, strategy, direction, entry, sl_pts, tp_pts}"""
    dna_key = "XAUUSD" if symbol=="GOLD" else ("XAGUSD" if symbol=="SILVER" else symbol)
    if target_key:
        symbol_dnas = {target_key: dna_db[target_key]}
    else:
        symbol_dnas = {k:v for k,v in dna_db.items() if k.startswith(f"{dna_key}:")}

    if pre_df5 is not None:
        df5, df15, df1h_ended = pre_df5, pre_df15, pre_df1h
    else:
        df5  = fetch(mt5_sym, mt5.TIMEFRAME_M5,  2000)
        df15 = fetch(mt5_sym, mt5.TIMEFRAME_M15, 2000)
        df1h = fetch(mt5_sym, mt5.TIMEFRAME_H1,  500)
        if df5 is None: return []

        # Build indicators on M15 and M5
        df15['rsi']   = rsi(df15['close'])
        df15['adx']   = adx_series(df15)
        df15['macd']  = macd_line(df15['close'])
        df15['msig']  = df15['macd'].ewm(span=9).mean()
        df15['ema9']  = df15['close'].ewm(span=9).mean()
        df15['ema21'] = df15['close'].ewm(span=21).mean()
        df15['ema50'] = df15['close'].ewm(span=50).mean()
        _,df15['bb_up'],df15['bb_lo'] = bollinger(df15['close'])
        df15['bb_mid'] = df15['close'].rolling(20).mean()
        df15['vol_avg'] = df15['volume'].rolling(20).mean()

        df5['rsi']   = rsi(df5['close'])
        df5['ema9']  = df5['close'].ewm(span=9).mean()
        df5['ema21'] = df5['close'].ewm(span=21).mean()
        df5['tp_vwap'] = (df5['high']+df5['low']+df5['close'])/3
        df5['vwap']  = (df5['tp_vwap']*df5['volume']).cumsum()/df5['volume'].cumsum()

        if df1h is not None:
            df1h['range'] = df1h['high'] - df1h['low']
            df1h['mean_24'] = df1h['close'].rolling(24).mean()
            df1h['std_24'] = df1h['close'].rolling(24).std()
            df1h['dh_24'] = df1h['high'].rolling(24).max()
            df1h['dl_24'] = df1h['low'].rolling(24).min()
            df1h['ah_8'] = df1h['high'].rolling(8).max().shift(1)
            df1h['al_8'] = df1h['low'].rolling(8).min().shift(1)
            df1h['ph_12'] = df1h['high'].rolling(8).max().shift(4)
            df1h['pl_12'] = df1h['low'].rolling(8).min().shift(4)
            
            df1h['pc'] = df1h['close'].shift(1)
            df1h['co'] = df1h['open']
            df1h['cc'] = df1h['close']
            
            df1h['lr'] = df1h['range']
            df1h['ar'] = df1h['range'].rolling(10).mean()
            df1h['range_mean_5'] = df1h['range'].rolling(5).mean()
            
            df1h['ah_4'] = df1h['high'].rolling(4).max()
            df1h['al_4'] = df1h['low'].rolling(4).min()
            
            bull_highs = df1h['high'].where(df1h['close'] > df1h['open'], np.nan)
            df1h['ob_bob'] = bull_highs.rolling(20, min_periods=1).max()
            bear_lows = df1h['low'].where(df1h['close'] < df1h['open'], np.nan)
            df1h['ob_bok'] = bear_lows.rolling(20, min_periods=1).min()
            
            df1h_ended = df1h.copy()
            df1h_ended.index = df1h_ended.index + pd.Timedelta(hours=1)
        else:
            df1h_ended = None

    # Cut to last 7 days only
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=7)
    df15_week = df15[df15.index >= cutoff].copy()
    df5_week  = df5[df5.index >= cutoff].copy()

    # Align indexes to standard datetime64[ns] to prevent MergeError
    df15_week.index = df15_week.index.astype('datetime64[ns]')
    df5_week.index = df5_week.index.astype('datetime64[ns]')

    if df1h_ended is not None:
        df1h_ended.index = df1h_ended.index.astype('datetime64[ns]')
        df15_week = pd.merge_asof(df15_week, df1h_ended, left_index=True, right_index=True, suffixes=('', '_h1'))
        df5_week = pd.merge_asof(df5_week, df1h_ended, left_index=True, right_index=True, suffixes=('', '_h1'))

    # Also merge M15's ADX into M5 so that M5 strategies have access to M15 ADX
    df15_adx = df15[['adx']].copy()
    df15_adx.index = df15_adx.index.astype('datetime64[ns]')
    df5_week = pd.merge_asof(df5_week, df15_adx, left_index=True, right_index=True, suffixes=('', '_m15'))

    signals = []
    info = mt5.symbol_info(mt5_sym)
    if not info: return []
    point = info.point
    atr_fallback = df15['close'].std() * 0.5

    for strat_key, dna in symbol_dnas.items():
        sn = strat_key.split(":")[1]
        dr = dna.get("direction","BOTH")
        sl_atr_mult = max(dna.get("sl", 1.5), 0.1)
        tp_atr_mult = max(dna.get("tgt", 3.0), 0.2)

        # Iterate M15 bars from last week
        working_df = df15_week if "M5" not in strat_key else df5_week
        std_short_series = working_df['close'].rolling(5).std().shift(1).tolist()
        std_long_series = working_df['close'].rolling(50).std().shift(1).tolist()
        atr_series = (working_df['close'].rolling(14).std() * 0.5).shift(1).tolist()

        records = working_df.to_dict('records')
        index_list = working_df.index.tolist()

        for i in range(50, len(records)-1):
            row = records[i]
            prev = records[i-1]
            t = index_list[i]
            utc_h = t.hour

            # --- REGIME FILTER GUARD ---
            # Volatility ratio
            std_short = std_short_series[i]
            std_long  = std_long_series[i]
            vol_ratio = std_short / std_long if std_long and std_long > 0 else 1.0

            # Trend Strength from M15 ADX
            adx_val = row.get('adx') if 'adx' in row else row.get('adx_m15', 20)
            if pd.isna(adx_val) or adx_val is None: adx_val = 20

            # Define strategy categories
            is_trend_strategy = sn in ("TREND_FOLLOWING","BULL_TREND_FOLLOWER","BEAR_TREND_FOLLOWER","MOMENTUM_BURST","EMA_CROSSOVER","ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SWAP_ARBITRAGE","SCALPING")
            is_reversion_strategy = sn in ("MEAN_REVERSION","RSI_REVERSAL","NY_OPEN_REVERSAL","ASIAN_RANGE_SCALP","BOLLINGER_SQUEEZE","DAY_HIGH_BEARISH","ENHANCED_BEARISH","DAY_LOW_BULLISH","ENHANCED_BULLISH","DAY_HIGH_LOW_TRADITIONAL","ULTIMATE_DAY_HIGH_LOW","ORDER_BLOCK_REVERSAL","VOLUME_CLIMAX","INSTITUTIONAL_SUPPORT")
            is_breakout_strategy = sn in ("BREAKOUT","VOLATILITY_BREAKOUT","ATR_BREAK","RESIST_BREAK","LONDON_BREAKOUT","MORNING_BREAKOUT","NEWS_BREAKOUT_STRADDLE","OPENING_DRIVE","WIDE_RANGE_RIDER")

            # Check rules
            if dna.get("active", True) is False: continue
            if symbol in ("GOLD", "SILVER") and sn in ("ZERO_HERO", "MAGIC_SQUARE", "AI_ENHANCED", "SWAP_ARBITRAGE", "SCALPING", "PIP_BLAST"): continue
            if is_trend_strategy and adx_val < 20: continue
            if is_reversion_strategy and adx_val >= 25: continue
            if is_breakout_strategy and vol_ratio < 0.8: continue
            if is_reversion_strategy and vol_ratio >= 1.5: continue

            # ATR from rolling std as proxy
            atr = atr_series[i]
            if pd.isna(atr) or atr == 0 or atr is None: atr = atr_fallback
            sl_pts  = (sl_atr_mult * atr) / point
            tp_pts  = (tp_atr_mult * atr) / point

            sig = None

            try:
                thresh_val = float(dna.get("thresh", 0.85))
                # Avoid lookahead bias in H1 metrics
                h1 = row if ('mean_24' in row and not pd.isna(row['mean_24'])) else None

                if sn == "BOLLINGER_SQUEEZE":
                    width = (row['bb_up'] - row['bb_lo']) / row['bb_mid'] if row['bb_mid'] != 0 else 1
                    bol_squeeze_thresh = 0.004 * (thresh_val if thresh_val > 0 else 0.87)
                    if width < bol_squeeze_thresh:
                        if row['close'] > row['bb_up'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close'] < row['bb_lo'] and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("DAY_HIGH_BEARISH","ENHANCED_BEARISH"):
                    if 7 <= utc_h <= 20 and h1 is not None:
                        mean_24 = h1['mean_24']
                        std_24 = h1['std_24']
                        std_24 = std_24 if std_24 > 0 else (row['close'] * 0.001)
                        z_score = (row['close'] - mean_24) / std_24
                        if z_score >= (thresh_val if thresh_val > 0 else 0.82) and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("DAY_LOW_BULLISH","ENHANCED_BULLISH"):
                    if 7 <= utc_h <= 20 and h1 is not None:
                        mean_24 = h1['mean_24']
                        std_24 = h1['std_24']
                        std_24 = std_24 if std_24 > 0 else (row['close'] * 0.001)
                        z_score = (row['close'] - mean_24) / std_24
                        if z_score <= (thresh_val if thresh_val < 0 else -2.2) and dr in ("BUY","BOTH"): sig="BUY"

                elif sn in ("DAY_HIGH_LOW_TRADITIONAL","ULTIMATE_DAY_HIGH_LOW"):
                    if h1 is not None:
                        dh = h1['dh_24']
                        dl = h1['dl_24']
                        buffer = (dh - dl) * 0.01 * (thresh_val - 0.5)
                        if row['close'] > dh + buffer and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close'] < dl - buffer and dr in ("SELL","BOTH"): sig="SELL"

                elif sn == "LONDON_BREAKOUT":
                    if 7 <= utc_h <= 10 and h1 is not None:
                        ah = h1['ah_8']
                        al = h1['al_8']
                        rng = ah - al
                        if row['close'] > ah + rng * 0.05 * thresh_val: sig="BUY"
                        elif row['close'] < al - rng * 0.05 * thresh_val: sig="SELL"

                elif sn == "MORNING_BREAKOUT":
                    if 6 <= utc_h <= 9 and h1 is not None:
                        ph = h1['ph_12']
                        pl = h1['pl_12']
                        rng = ph - pl
                        if row['close'] > ph + rng * 0.05 * thresh_val: sig="BUY"
                        elif row['close'] < pl - rng * 0.05 * thresh_val: sig="SELL"

                elif sn == "NY_OPEN_REVERSAL":
                    if 12 <= utc_h <= 14:
                        oversold = 35 * thresh_val
                        overbought = 100 - oversold
                        if row['rsi'] < oversold and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['rsi'] > overbought and dr in ("SELL","BOTH"): sig="SELL"

                elif sn == "MACD_DIVERGENCE":
                    if prev['macd'] < prev['msig'] and row['macd'] > row['msig'] and dr in ("BUY","BOTH"): sig="BUY"
                    elif prev['macd'] > prev['msig'] and row['macd'] < row['msig'] and dr in ("SELL","BOTH"): sig="SELL"

                elif sn == "EMA_CROSSOVER":
                    if prev['ema9'] < prev['ema21'] and row['ema9'] > row['ema21'] and dr in ("BUY","BOTH"): sig="BUY"
                    elif prev['ema9'] > prev['ema21'] and row['ema9'] < row['ema21'] and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("MEAN_REVERSION","RSI_REVERSAL"):
                    if row['adx'] < 25:
                        oversold = 30 * thresh_val
                        overbought = 100 - oversold
                        if row['rsi'] < oversold and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['rsi'] > overbought and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("TREND_FOLLOWING","BULL_TREND_FOLLOWER","BEAR_TREND_FOLLOWER","MOMENTUM_BURST"):
                    if row['adx'] >= 20:
                        if row['ema9'] > row['ema50'] and 45 < row['rsi'] < 70 and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['ema9'] < row['ema50'] and 30 < row['rsi'] < 55 and dr in ("SELL","BOTH"): sig="SELL"

                elif "GAP" in sn and h1 is not None:
                    pc = h1['pc']
                    co = h1['co']
                    cc = h1['cc']
                    gp = (co - pc) / pc if pc != 0 else 0
                    if abs(gp) > 0.001:
                        if gp > 0 and cc < co and dr in ("SELL","BOTH"): sig="SELL"
                        elif gp < 0 and cc > co and dr in ("BUY","BOTH"): sig="BUY"

                elif sn in ("BREAKOUT","VOLATILITY_BREAKOUT","ATR_BREAK","RESIST_BREAK"):
                    rh = working_df['high'].iloc[max(0, i-21):i].max()
                    rl = working_df['low'].iloc[max(0, i-21):i].min()
                    if row['close'] > rh * (1 + 0.0002 * thresh_val) and dr in ("BUY","BOTH"): sig="BUY"
                    elif row['close'] < rl * (1 - 0.0002 * thresh_val) and dr in ("SELL","BOTH"): sig="SELL"

                elif sn == "VWAP_BOUNCE":
                    pv_r = working_df.iloc[i-1]
                    if pv_r.get('vwap') is not None and row.get('vwap') is not None:
                        if pv_r['close'] < pv_r.get('vwap',0) and row['close'] > row.get('vwap',0) and dr in ("BUY","BOTH"): sig="BUY"
                        elif pv_r['close'] > pv_r.get('vwap',0) and row['close'] < row.get('vwap',0) and dr in ("SELL","BOTH"): sig="SELL"

                elif sn == "SHORT_SQUEEZE":
                    if row['rsi'] > 60 and row['close'] > row['bb_up'] and dr in ("BUY","BOTH"): sig="BUY"

                elif sn == "LONG_LIQUIDATION":
                    if row['rsi'] < 40 and row['close'] < row['bb_lo'] and dr in ("SELL","BOTH"): sig="SELL"

                elif sn == "VOLUME_CLIMAX":
                    if row['volume'] > row['vol_avg'] * 2:
                        if row['close'] < prev['close'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close'] > prev['close'] and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("WIDE_RANGE_RIDER",) and h1 is not None:
                    lr = h1['lr']
                    ar = h1['ar']
                    if lr > ar * 1.5:
                        if row['close'] > h1['co'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close'] < h1['co'] and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("OPENING_DRIVE","NEWS_BREAKOUT_STRADDLE"):
                    if utc_h in [8,9,13,14]:
                        rh = working_df['high'].iloc[max(0, i-12):i].max()
                        rl = working_df['low'].iloc[max(0, i-12):i].min()
                        if row['close'] > rh: sig="BUY"
                        elif row['close'] < rl: sig="SELL"

                elif sn in ("ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SCALPING","PIP_BLAST","SWAP_ARBITRAGE"):
                    rsi_buy = 50 + (5 * thresh_val)
                    rsi_sell = 50 - (5 * thresh_val)
                    if row['ema9'] > row['ema21'] and row['rsi'] > rsi_buy and dr in ("BUY","BOTH"): sig="BUY"
                    elif row['ema9'] < row['ema21'] and row['rsi'] < rsi_sell and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("RANGE_CONTRACTION","EARLY_BREAKDOWN") and h1 is not None:
                    if h1['lr'] < h1['range_mean_5'] * 0.6:
                        if row['close'] < h1['co'] and dr in ("SELL","BOTH"): sig="SELL"
                        elif row['close'] > h1['co'] and dr in ("BUY","BOTH"): sig="BUY"

                elif sn in ("ASIAN_RANGE_SCALP",) and h1 is not None:
                    if utc_h < 8:
                        ah = h1['ah_4']
                        al = h1['al_4']
                        mid = (ah + al) / 2
                        if row['close'] < mid and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close'] > mid and dr in ("SELL","BOTH"): sig="SELL"

                elif sn == "INSTITUTIONAL_SUPPORT":
                    pr = row['close']
                    rf = 10**(info.digits - 2)
                    nr = round(pr * rf) / rf
                    if abs(pr - nr) / pr < 0.0005:
                        if row['rsi'] < 45 and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['rsi'] > 55 and dr in ("SELL","BOTH"): sig="SELL"

                elif sn in ("ORDER_BLOCK_REVERSAL",) and h1 is not None:
                    bob = h1['ob_bob']
                    bok = h1['ob_bok']
                    if bok > 0 and row['close'] <= bok * (1 + 0.001 * thresh_val) and dr in ("BUY","BOTH"): sig="BUY"
                    elif bob > 0 and row['close'] >= bob * (1 - 0.001 * thresh_val) and dr in ("SELL","BOTH"): sig="SELL"

            except Exception as e:
                continue

            if sig:
                signals.append({
                    "time": t, "symbol": symbol, "strategy": sn,
                    "direction": sig, "entry": row['close'],
                    "sl_pts": sl_pts, "tp_pts": tp_pts,
                    "atr": atr, "point": point
                })

    return signals

# ─── SIMULATE TRADE OUTCOMES ─────────────────────────────────────────────────
def simulate(signals, df5_full, tick_val, point):
    """For each signal, scan forward 48 bars to see if SL or TP is hit first."""
    results = []
    closes = df5_full['close'].values
    times  = df5_full.index.values
    highs  = df5_full['high'].values
    lows   = df5_full['low'].values

    for s in signals:
        entry   = s['entry']
        sl_pts  = s['sl_pts']
        tp_pts  = s['tp_pts']
        dr      = s['direction']
        point   = s['point']
        t_entry = s['time']

        sl_price = entry - sl_pts*point if dr=="BUY" else entry + sl_pts*point
        tp_price = entry + tp_pts*point if dr=="BUY" else entry - tp_pts*point

        # Find bar index after entry using fast binary search
        idx = np.searchsorted(times, np.datetime64(t_entry))
        start_idx = int(idx) + 1
        if start_idx >= len(closes): continue

        outcome = "OPEN"
        pnl_pts = 0
        for fwd in range(start_idx, min(start_idx+48, len(closes))):
            h = highs[fwd]; l = lows[fwd]
            if dr == "BUY":
                if l <= sl_price: outcome="LOSS"; pnl_pts = -sl_pts; break
                if h >= tp_price: outcome="WIN";  pnl_pts = tp_pts;  break
            else:
                if h >= sl_price: outcome="LOSS"; pnl_pts = -sl_pts; break
                if l <= tp_price: outcome="WIN";  pnl_pts = tp_pts;  break

        if outcome == "OPEN":
            pnl_pts = (closes[min(start_idx+47, len(closes)-1)] - entry)/point * (1 if dr=="BUY" else -1)
            outcome = "EXPIRED"

        pnl_usd = pnl_pts * point * tick_val * FIXED_LOT * (1/point)
        results.append({**s, "outcome": outcome, "pnl_pts": round(pnl_pts,1), "pnl_usd": round(pnl_usd,2)})

    return results

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if not connect():
        log.error("MT5 connection failed"); return

    dna_db = load_dna()
    all_results = []

    for sym_label, mt5_sym in SYMBOLS.items():
        log.info(f"=== Processing {sym_label} ({mt5_sym}) ===")
        if not mt5.symbol_select(mt5_sym, True):
            log.warning(f"Symbol {mt5_sym} not available — skipping"); continue

        info = mt5.symbol_info(mt5_sym)
        if not info: continue
        tick_val = info.trade_tick_value
        point    = info.point

        signals = generate_signals(sym_label, mt5_sym, dna_db)
        log.info(f"  {len(signals)} raw signals generated")

        df5_full = fetch(mt5_sym, mt5.TIMEFRAME_M5, 2000)
        if df5_full is None: continue

        results = simulate(signals, df5_full, tick_val, point)
        all_results.extend(results)
        log.info(f"  {len(results)} trades simulated")

    if not all_results:
        log.error("No results produced"); mt5.shutdown(); return

    df = pd.DataFrame(all_results)
    df['week'] = "Jul 04–10 2026"

    # ─── REPORT ──────────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("  1-WEEK BACKTEST REPORT — ALL 41 STRATEGIES × 8 SYMBOLS")
    print("  Period: Last 7 days | Fixed Lot: 0.10 | Account: $10,000")
    print("="*80)

    # By Symbol Summary
    print("\n--- PnL BY SYMBOL ---\n" + "-"*60)
    sym_grp = df.groupby("symbol").agg(
        Trades=("pnl_usd","count"),
        Wins=("outcome", lambda x: (x=="WIN").sum()),
        Losses=("outcome", lambda x: (x=="LOSS").sum()),
        PnL_USD=("pnl_usd","sum")
    ).sort_values("PnL_USD", ascending=False)
    sym_grp['WinRate'] = (sym_grp['Wins']/sym_grp['Trades']*100).round(1).astype(str)+"%"
    print(sym_grp.to_string())

    # By Strategy Summary
    print("\n\n--- PnL BY STRATEGY ---\n" + "-"*60)
    str_grp = df.groupby("strategy").agg(
        Trades=("pnl_usd","count"),
        Wins=("outcome", lambda x: (x=="WIN").sum()),
        PnL_USD=("pnl_usd","sum")
    ).sort_values("PnL_USD", ascending=False)
    str_grp['WinRate'] = (str_grp['Wins']/str_grp['Trades']*100).round(1).astype(str)+"%"
    print(str_grp.to_string())

    # By Symbol x Strategy matrix
    print("\n\n--- PnL MATRIX (SYMBOL x STRATEGY) ---\n" + "-"*60)
    pivot = df.pivot_table(index="symbol", columns="strategy", values="pnl_usd", aggfunc="sum").fillna(0).round(0)
    print(pivot.to_string())

    # Overall
    total    = df['pnl_usd'].sum()
    wins     = (df['outcome']=="WIN").sum()
    losses   = (df['outcome']=="LOSS").sum()
    total_t  = len(df)
    win_rate = wins/total_t*100 if total_t>0 else 0
    print(f"\n{'='*80}")
    print(f"  TOTAL TRADES : {total_t}")
    print(f"  WINS         : {wins}  |  LOSSES: {losses}  |  WIN RATE: {win_rate:.1f}%")
    print(f"  TOTAL PnL    : ${total:,.2f}  (on $10,000 account = {total/ACCOUNT_BAL*100:.2f}%)")
    print(f"{'='*80}\n")

    # Save to CSV
    out = BASE_DIR / "backtest_1week_results.csv"
    df.to_csv(out, index=False)
    log.info(f"Full results saved to {out}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
