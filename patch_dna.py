import re

with open('backtest_high_res.py', 'r') as f:
    code = f.read()

# 1. Update simulate_outcomes to read use_grid from the signal
code = re.sub(
    r'is_grid = strat_key in \("SCALPING", "ASIAN_RANGE_SCALP", "ZERO_HERO", "SWAP_ARBITRAGE"\)',
    'is_grid = s.get("use_grid", False)',
    code
)

# 2. Update generate_signals to use Per-Symbol DNA and inject use_grid
new_gen_loop = '''def generate_signals(symbol, df15, df5, df1h_ended, dna_db):
    signals = []
    
    for strat_key, condition_func in STRATEGIES.items():
        sn = strat_key.replace("_M15","").replace("_M5","")
        if sn in DISABLED_STRATEGIES: continue
        
        dna_key = f"{symbol}_{sn}"
        if dna_key not in dna_db: continue # Completely skip if not authorized for this symbol
        dna = dna_db[dna_key]
        
        dr = dna.get("direction","BOTH")
        sl_atr = max(dna.get("sl", 1.5), 0.5)
        tp_atr = max(dna.get("tgt", 1.5), 0.5)
        use_grid = dna.get("use_grid", False)

        working_df = df5 if sn in ("ZERO_HERO","MAGIC_SQUARE","AI_ENHANCED","SCALPING","PIP_BLAST","SWAP_ARBITRAGE") or "M5" in strat_key else df15
        atr_s = (working_df['close'].rolling(14).std()*0.5).shift(1)
        atr_fallback = atr_s.mean()

        records    = working_df.to_dict('records')
        index_list = working_df.index.tolist()
        n = len(records)

        for i in range(50, n-1):
            t    = index_list[i]
            row  = records[i]
            prev = records[i-1]
            utc_h = t.hour
            weekday = t.dayofweek

            h1 = None
            if df1h_ended is not None:
                h1_idx = df1h_ended.index.asof(t)
                if not pd.isna(h1_idx):
                    h1 = df1h_ended.loc[h1_idx].to_dict()
            
            sig = condition_func(row, prev, h1)
            
            if sig == 0: continue
            if dr == "BUY" and sig < 0: continue
            if dr == "SELL" and sig > 0: continue

            entry = row['close']
            atr = atr_s.iloc[i]
            if pd.isna(atr) or atr == 0: atr = atr_fallback
            sl_pts = (sl_atr*atr)/POINT.get(symbol,0.00001)
            tp_pts = (tp_atr*atr)/POINT.get(symbol,0.00001)

            thresh = float(dna.get("thresh",0.50))
            
            signals.append({
                "time": str(t),
                "symbol": symbol,
                "strategy": sn,
                "direction": "BUY" if sig>0 else "SELL",
                "entry": entry,
                "sl_pts": sl_pts,
                "tp_pts": tp_pts,
                "atr": atr,
                "use_grid": use_grid,
                "hour": utc_h,
                "weekday": weekday,
                "rsi_val": row.get('rsi_14', 50.0),
                "adx_val": row.get('adx_14', 20.0),
                "session": get_session(utc_h)
            })

    return signals'''

code = re.sub(r'def generate_signals\(symbol, df15, df5, df1h_ended, dna_db\):.*?return signals', new_gen_loop, code, flags=re.DOTALL)

with open('backtest_high_res.py', 'w') as f:
    f.write(code)
print("Updated backtest_high_res.py with per-symbol DNA logic!")
