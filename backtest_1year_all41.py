"""
backtest_1year_all41.py
=======================
Loads 1-year parquet data and runs all 41 strategies.
NO MT5 connection needed. NO synthetic data.
Saves: backtest_1year_signals.csv
"""
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(r"C:\anlyzeforex\forextele")
DNA_PATH = BASE_DIR / "25stragy" / "ai_optimized_forex_dna.json"
OUT_CSV  = BASE_DIR / "backtest_1year_signals.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SYMBOLS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","GOLD","SILVER","BTCUSD","ETHUSD"]
POINT   = {"EURUSD":0.00001,"GBPUSD":0.00001,"USDJPY":0.001,"AUDUSD":0.00001,
           "GOLD":0.01,"SILVER":0.001,"BTCUSD":0.01,"ETHUSD":0.001}
DIGITS  = {"EURUSD":5,"GBPUSD":5,"USDJPY":3,"AUDUSD":5,
           "GOLD":2,"SILVER":3,"BTCUSD":2,"ETHUSD":3}

# ---------- Indicators ----------
def rsi(s, p=14):
    d=s.diff(); g=d.where(d>0,0).rolling(p).mean()
    l=(-d.where(d<0,0)).rolling(p).mean()
    return 100-100/(1+g/l.replace(0,np.nan))

def bollinger(s, p=20, std=2.0):
    m=s.rolling(p).mean(); b=s.rolling(p).std()*std
    return m, m+b, m-b

def macd_line(s):
    return s.ewm(span=12).mean()-s.ewm(span=26).mean()

def adx_series(df, p=14):
    tr=pd.concat([df['high']-df['low'],
                  (df['high']-df['close'].shift()).abs(),
                  (df['low']-df['close'].shift()).abs()],axis=1).max(axis=1)
    dmp=((df['high']-df['high'].shift())>(df['low'].shift()-df['low'])).astype(float)*(df['high']-df['high'].shift()).clip(lower=0)
    dmn=((df['low'].shift()-df['low'])>(df['high']-df['high'].shift())).astype(float)*(df['low'].shift()-df['low']).clip(lower=0)
    atr_s=tr.rolling(p).mean()
    di_p=100*(dmp.rolling(p).mean()/atr_s)
    di_n=100*(dmn.rolling(p).mean()/atr_s)
    dx=(abs(di_p-di_n)/(di_p+di_n).replace(0,1))*100
    return dx.rolling(p).mean()

def session_flag(h):
    if h<4:   return "ASIAN"
    if h<8:   return "LONDON"
    if h<12:  return "NY"
    if h<16:  return "US"
    return "LONDON"

# ---------- Load parquet ----------
def load_tf(symbol, tf):
    p = BASE_DIR / f"data_1y_{symbol}_{tf}.parquet"
    if not p.is_file():
        return None
    df = pd.read_parquet(p)
    df.index = pd.to_datetime(df.index)
    return df

def load_tf_with_fallback(symbol, preferred_tfs):
    """Try each TF in order, return first available."""
    for tf in preferred_tfs:
        df = load_tf(symbol, tf)
        if df is not None and not df.empty:
            return df, tf
    return None, None

# ---------- Build indicators ----------
def build_indicators(df15, df5, df1h):
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
    tp_vwap = (df5['high']+df5['low']+df5['close'])/3
    df5['vwap'] = (tp_vwap*df5['volume']).cumsum()/df5['volume'].cumsum()

    if df1h is not None:
        df1h['range']       = df1h['high']-df1h['low']
        df1h['mean_24']     = df1h['close'].rolling(24).mean()
        df1h['std_24']      = df1h['close'].rolling(24).std()
        df1h['dh_24']       = df1h['high'].rolling(24).max()
        df1h['dl_24']       = df1h['low'].rolling(24).min()
        df1h['ah_8']        = df1h['high'].rolling(8).max().shift(1)
        df1h['al_8']        = df1h['low'].rolling(8).min().shift(1)
        df1h['ph_12']       = df1h['high'].rolling(8).max().shift(4)
        df1h['pl_12']       = df1h['low'].rolling(8).min().shift(4)
        df1h['pc']          = df1h['close'].shift(1)
        df1h['co']          = df1h['open']
        df1h['cc']          = df1h['close']
        df1h['lr']          = df1h['range']
        df1h['ar']          = df1h['range'].rolling(10).mean()
        df1h['range_mean_5']= df1h['range'].rolling(5).mean()
        df1h['ah_4']        = df1h['high'].rolling(4).max()
        df1h['al_4']        = df1h['low'].rolling(4).min()
        bull_highs          = df1h['high'].where(df1h['close']>df1h['open'],np.nan)
        df1h['ob_bob']      = bull_highs.rolling(20,min_periods=1).max()
        bear_lows           = df1h['low'].where(df1h['close']<df1h['open'],np.nan)
        df1h['ob_bok']      = bear_lows.rolling(20,min_periods=1).min()
        # Shift by 1 period to avoid lookahead
        df1h_ended = df1h.copy()
        df1h_ended.index = df1h_ended.index + pd.Timedelta(hours=1)
    else:
        df1h_ended = None

    return df15, df5, df1h_ended

# ---------- Simulate outcome ----------
def simulate_outcomes(signals, df_m1, point):
    if not signals:
        return []
    closes = df_m1['close'].values
    highs  = df_m1['high'].values
    lows   = df_m1['low'].values
    times  = df_m1.index.values.astype('datetime64[ns]')

    results = []
    for s in signals:
        entry   = s['entry']
        sl_pts  = s['sl_pts']
        tp_pts  = s['tp_pts']
        dr      = s['direction']
        t_entry = np.datetime64(s['time'], 'ns')

        sl_price = entry - sl_pts*point if dr=="BUY" else entry + sl_pts*point
        tp_price = entry + tp_pts*point if dr=="BUY" else entry - tp_pts*point

        idx = int(np.searchsorted(times, t_entry)) + 1
        if idx >= len(closes):
            continue

        outcome  = "EXPIRED"
        pnl_pts  = 0.0
        for fwd in range(idx, min(idx+48, len(closes))):
            h = highs[fwd]; l = lows[fwd]
            if dr == "BUY":
                if l <= sl_price: outcome="LOSS"; pnl_pts=-sl_pts; break
                if h >= tp_price: outcome="WIN";  pnl_pts=tp_pts;  break
            else:
                if h >= sl_price: outcome="LOSS"; pnl_pts=-sl_pts; break
                if l <= tp_price: outcome="WIN";  pnl_pts=tp_pts;  break

        if outcome == "EXPIRED":
            pnl_pts = (closes[min(idx+47,len(closes)-1)] - entry)/point * (1 if dr=="BUY" else -1)

        results.append({**s, "outcome": outcome, "pnl_pts": round(pnl_pts,1)})
    return results

# ---------- Generate signals for one symbol ----------
def generate_signals(symbol, df15, df5, df1h_ended, dna_db):
    dna_key = "XAUUSD" if symbol=="GOLD" else ("XAGUSD" if symbol=="SILVER" else symbol)
    symbol_dnas = {k:v for k,v in dna_db.items() if k.startswith(f"{dna_key}:")}
    point  = POINT.get(symbol, 0.00001)
    digits = DIGITS.get(symbol, 5)

    # Merge H1 into M15 and M5
    if df1h_ended is not None:
        df1h_ended.index = df1h_ended.index.astype('datetime64[ns]')
        df15.index = df15.index.astype('datetime64[ns]')
        df5.index  = df5.index.astype('datetime64[ns]')
        df15 = pd.merge_asof(df15, df1h_ended, left_index=True, right_index=True, suffixes=('','_h1'))
        df5  = pd.merge_asof(df5,  df1h_ended, left_index=True, right_index=True, suffixes=('','_h1'))
    df15_adx = df15[['adx']].copy()
    df15_adx.index = df15_adx.index.astype('datetime64[ns]')
    df5 = pd.merge_asof(df5, df15_adx, left_index=True, right_index=True, suffixes=('','_m15'))

    atr_fallback = df15['close'].std()*0.5
    signals = []

    for strat_key, dna in symbol_dnas.items():
        sn = strat_key.split(":")[1]
        dr = dna.get("direction","BOTH")
        sl_atr = max(dna.get("sl",1.5),0.1)
        tp_atr = max(dna.get("tgt",3.0),0.2)

        working_df = df5 if "M5" in strat_key else df15
        atr_s = (working_df['close'].rolling(14).std()*0.5).shift(1)
        std_short = working_df['close'].rolling(5).std().shift(1)
        std_long  = working_df['close'].rolling(50).std().shift(1)

        records    = working_df.to_dict('records')
        index_list = working_df.index.tolist()
        n = len(records)

        for i in range(50, n-1):
            row  = records[i]
            prev = records[i-1]
            t    = index_list[i]
            utc_h = t.hour

            adx_val  = row.get('adx') or row.get('adx_m15', 20) or 20
            if pd.isna(adx_val): adx_val = 20
            sl_v = std_short.iloc[i]; sl_v = sl_v if sl_v and not pd.isna(sl_v) else 0
            ll_v = std_long.iloc[i];  ll_v = ll_v if ll_v and not pd.isna(ll_v) else 1
            vol_ratio = sl_v/ll_v if ll_v > 0 else 1.0

            is_trend    = sn in ("TREND_FOLLOWING","BULL_TREND_FOLLOWER","BEAR_TREND_FOLLOWER","MOMENTUM_BURST","EMA_CROSSOVER","ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SWAP_ARBITRAGE","SCALPING")
            is_revert   = sn in ("MEAN_REVERSION","RSI_REVERSAL","NY_OPEN_REVERSAL","ASIAN_RANGE_SCALP","BOLLINGER_SQUEEZE","DAY_HIGH_BEARISH","ENHANCED_BEARISH","DAY_LOW_BULLISH","ENHANCED_BULLISH","DAY_HIGH_LOW_TRADITIONAL","ULTIMATE_DAY_HIGH_LOW","ORDER_BLOCK_REVERSAL","VOLUME_CLIMAX","INSTITUTIONAL_SUPPORT")
            is_breakout = sn in ("BREAKOUT","VOLATILITY_BREAKOUT","ATR_BREAK","RESIST_BREAK","LONDON_BREAKOUT","MORNING_BREAKOUT","NEWS_BREAKOUT_STRADDLE","OPENING_DRIVE","WIDE_RANGE_RIDER")

            if symbol in ("GOLD","SILVER") and sn in ("ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SWAP_ARBITRAGE","SCALPING","PIP_BLAST"): continue
            if is_trend   and adx_val < 20:  continue
            if is_revert  and adx_val >= 25: continue
            if is_breakout and vol_ratio < 0.8: continue
            if is_revert  and vol_ratio >= 1.5: continue

            atr = atr_s.iloc[i]
            if pd.isna(atr) or atr == 0: atr = atr_fallback
            sl_pts = (sl_atr*atr)/point
            tp_pts = (tp_atr*atr)/point

            thresh = float(dna.get("thresh",0.85))
            h1 = row if ('mean_24' in row and not pd.isna(row.get('mean_24',float('nan')))) else None
            sig = None

            try:
                if sn=="BOLLINGER_SQUEEZE":
                    w=(row['bb_up']-row['bb_lo'])/row['bb_mid'] if row.get('bb_mid') else 1
                    if w < 0.004*thresh:
                        if row['close']>row['bb_up'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close']<row['bb_lo'] and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("DAY_HIGH_BEARISH","ENHANCED_BEARISH"):
                    if 7<=utc_h<=20 and h1:
                        s24=h1['std_24'] or row['close']*0.001
                        if (row['close']-h1['mean_24'])/s24 >= thresh and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("DAY_LOW_BULLISH","ENHANCED_BULLISH"):
                    if 7<=utc_h<=20 and h1:
                        s24=h1['std_24'] or row['close']*0.001
                        if (row['close']-h1['mean_24'])/s24 <= (thresh if thresh<0 else -2.2) and dr in ("BUY","BOTH"): sig="BUY"
                elif sn in ("DAY_HIGH_LOW_TRADITIONAL","ULTIMATE_DAY_HIGH_LOW"):
                    if h1:
                        buf=(h1['dh_24']-h1['dl_24'])*0.01*(thresh-0.5)
                        if row['close']>h1['dh_24']+buf and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close']<h1['dl_24']-buf and dr in ("SELL","BOTH"): sig="SELL"
                elif sn=="LONDON_BREAKOUT":
                    if 7<=utc_h<=10 and h1:
                        rng=h1['ah_8']-h1['al_8']
                        if row['close']>h1['ah_8']+rng*0.05*thresh: sig="BUY"
                        elif row['close']<h1['al_8']-rng*0.05*thresh: sig="SELL"
                elif sn=="MORNING_BREAKOUT":
                    if 6<=utc_h<=9 and h1:
                        rng=h1['ph_12']-h1['pl_12']
                        if row['close']>h1['ph_12']+rng*0.05*thresh: sig="BUY"
                        elif row['close']<h1['pl_12']-rng*0.05*thresh: sig="SELL"
                elif sn=="NY_OPEN_REVERSAL":
                    if 12<=utc_h<=14:
                        ob=35*thresh; obb=100-ob
                        if row['rsi']<ob and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['rsi']>obb and dr in ("SELL","BOTH"): sig="SELL"
                elif sn=="MACD_DIVERGENCE":
                    if prev['macd']<prev['msig'] and row['macd']>row['msig'] and dr in ("BUY","BOTH"): sig="BUY"
                    elif prev['macd']>prev['msig'] and row['macd']<row['msig'] and dr in ("SELL","BOTH"): sig="SELL"
                elif sn=="EMA_CROSSOVER":
                    if prev['ema9']<prev['ema21'] and row['ema9']>row['ema21'] and dr in ("BUY","BOTH"): sig="BUY"
                    elif prev['ema9']>prev['ema21'] and row['ema9']<row['ema21'] and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("MEAN_REVERSION","RSI_REVERSAL"):
                    if adx_val<25:
                        ob=30*thresh; obb=100-ob
                        if row['rsi']<ob and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['rsi']>obb and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("TREND_FOLLOWING","BULL_TREND_FOLLOWER","BEAR_TREND_FOLLOWER","MOMENTUM_BURST"):
                    if adx_val>=20:
                        if row['ema9']>row['ema50'] and 45<row['rsi']<70 and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['ema9']<row['ema50'] and 30<row['rsi']<55 and dr in ("SELL","BOTH"): sig="SELL"
                elif "GAP" in sn and h1:
                    gp=(h1['co']-h1['pc'])/h1['pc'] if h1['pc'] else 0
                    if abs(gp)>0.001:
                        if gp>0 and h1['cc']<h1['co'] and dr in ("SELL","BOTH"): sig="SELL"
                        elif gp<0 and h1['cc']>h1['co'] and dr in ("BUY","BOTH"): sig="BUY"
                elif sn in ("BREAKOUT","VOLATILITY_BREAKOUT","ATR_BREAK","RESIST_BREAK"):
                    rh=working_df['high'].iloc[max(0,i-21):i].max()
                    rl=working_df['low'].iloc[max(0,i-21):i].min()
                    if row['close']>rh*(1+0.0002*thresh) and dr in ("BUY","BOTH"): sig="BUY"
                    elif row['close']<rl*(1-0.0002*thresh) and dr in ("SELL","BOTH"): sig="SELL"
                elif sn=="VWAP_BOUNCE":
                    pv=records[i-1]
                    if pv.get('vwap') and row.get('vwap'):
                        if pv['close']<pv['vwap'] and row['close']>row['vwap'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif pv['close']>pv['vwap'] and row['close']<row['vwap'] and dr in ("SELL","BOTH"): sig="SELL"
                elif sn=="VOLUME_CLIMAX":
                    if row.get('volume',0)>row.get('vol_avg',1)*2:
                        if row['close']<prev['close'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close']>prev['close'] and dr in ("SELL","BOTH"): sig="SELL"
                elif sn=="INSTITUTIONAL_SUPPORT":
                    rf=10**(digits-2); nr=round(row['close']*rf)/rf
                    if abs(row['close']-nr)/row['close']<0.0005:
                        if row['rsi']<45 and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['rsi']>55 and dr in ("SELL","BOTH"): sig="SELL"
                elif sn=="ORDER_BLOCK_REVERSAL" and h1:
                    bob=h1.get('ob_bob',0); bok=h1.get('ob_bok',0)
                    if bok and row['close']<=bok*(1+0.001*thresh) and dr in ("BUY","BOTH"): sig="BUY"
                    elif bob and row['close']>=bob*(1-0.001*thresh) and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SCALPING","PIP_BLAST","SWAP_ARBITRAGE"):
                    rb=50+(5*thresh); rs=50-(5*thresh)
                    if row['ema9']>row['ema21'] and row['rsi']>rb and dr in ("BUY","BOTH"): sig="BUY"
                    elif row['ema9']<row['ema21'] and row['rsi']<rs and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("ASIAN_RANGE_SCALP",) and h1:
                    if utc_h<8:
                        mid=(h1['ah_4']+h1['al_4'])/2
                        if row['close']<mid and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close']>mid and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("OPENING_DRIVE","NEWS_BREAKOUT_STRADDLE"):
                    if utc_h in [8,9,13,14]:
                        rh=working_df['high'].iloc[max(0,i-12):i].max()
                        rl=working_df['low'].iloc[max(0,i-12):i].min()
                        if row['close']>rh: sig="BUY"
                        elif row['close']<rl: sig="SELL"
                elif sn in ("WIDE_RANGE_RIDER",) and h1:
                    if h1['lr']>h1['ar']*1.5:
                        if row['close']>h1['co'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close']<h1['co'] and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("RANGE_CONTRACTION","EARLY_BREAKDOWN") and h1:
                    if h1['lr']<h1['range_mean_5']*0.6:
                        if row['close']>h1['co'] and dr in ("BUY","BOTH"): sig="BUY"
                        elif row['close']<h1['co'] and dr in ("SELL","BOTH"): sig="SELL"
                elif sn in ("SHORT_SQUEEZE",):
                    if row['rsi']>60 and row['close']>row.get('bb_up',row['close']+1) and dr in ("BUY","BOTH"): sig="BUY"
                elif sn in ("LONG_LIQUIDATION",):
                    if row['rsi']<40 and row['close']<row.get('bb_lo',row['close']-1) and dr in ("SELL","BOTH"): sig="SELL"
            except Exception:
                continue

            if sig:
                signals.append({
                    "time":      t, "symbol": symbol, "strategy": sn,
                    "direction": sig, "entry":  row['close'],
                    "sl_pts":    sl_pts, "tp_pts": tp_pts, "atr": atr,
                    "point":     point,
                    "hour":      utc_h,
                    "weekday":   t.weekday(),
                    "session":   session_flag(utc_h),
                    "rsi_val":   row.get('rsi', 50),
                    "adx_val":   adx_val,
                })
    return signals


def main():
    with open(DNA_PATH) as f:
        dna_db = json.load(f).get("strategies", {})

    all_results = []

    for symbol in SYMBOLS:
        log.info("=== %s ===", symbol)
        df_m15 = load_tf(symbol, "M15")
        df_h1  = load_tf(symbol, "H1")

        # Use best available fine-grained TF for signal generation
        df_m5, tf_m5 = load_tf_with_fallback(symbol, ["M5", "M15"])
        # Use best available for simulation (need bars to scan SL/TP)
        df_sim, tf_sim = load_tf_with_fallback(symbol, ["M1", "M5", "M15"])

        if df_m15 is None or df_m5 is None or df_sim is None:
            log.warning("Missing data for %s — skipping", symbol)
            continue

        log.info("  Signal TF: M15+%s | Simulation TF: %s", tf_m5, tf_sim)
        df_m15, df_m5, df_h1_ended = build_indicators(df_m15, df_m5, df_h1)

        signals = generate_signals(symbol, df_m15, df_m5, df_h1_ended, dna_db)
        log.info("  %d signals generated", len(signals))

        point = POINT.get(symbol, 0.00001)
        results = simulate_outcomes(signals, df_sim, point)
        log.info("  %d outcomes simulated", len(results))
        all_results.extend(results)

    if not all_results:
        log.error("No results. Run fetch_1year_m1_data.py first.")
        return

    df = pd.DataFrame(all_results)
    df.to_csv(OUT_CSV, index=False)
    log.info("Saved %d rows → %s", len(df), OUT_CSV)

    wins = (df['outcome']=='WIN').sum()
    total = len(df)
    log.info("WIN RATE: %.1f%%  |  TOTAL SIGNALS: %d", wins/total*100, total)


if __name__ == "__main__":
    main()