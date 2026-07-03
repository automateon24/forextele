import codecs
import re

content = codecs.open(r'C:\25stragy\engine_v15.py', 'r', 'utf-8').read()

tele_code = """
# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM MANAGED EXITS (AI LIVE TRACKING)
# ─────────────────────────────────────────────────────────────────────────────
TELEGRAM_EXCEL_PATH = r"C:\\25stragy\\telegram_signals.xlsx"
tele_sec_cache = {}

def get_tele_sec_id(inst_str: str):
    if inst_str in tele_sec_cache: return tele_sec_cache[inst_str]
    inst = inst_str.upper()
    sec_id = None
    if 'BANK' in inst: sec_id = 25
    elif 'FIN' in inst: sec_id = 27
    elif 'MID' in inst: sec_id = 51
    elif 'SENSEX' in inst: sec_id = 442
    elif 'NIFTY' in inst: sec_id = 13
    
    if not sec_id: return None
    
    strike = 0
    match = re.search(r'\\b\\d{5}\\b', inst)
    if match: strike = float(match.group())
    if strike == 0: return None
    
    side = 'CE' if ('CE' in inst or 'CALL' in inst) else 'PE'
    
    try:
        exp_r = _api_call(dhan_manager.client.expiry_list, under_security_id=sec_id, under_exchange_segment='IDX_I')
        if not exp_r or exp_r.get('status') != 'success': return None
        expiries = exp_r.get('data', {}).get('data', [])
        if not expiries: return None
        
        oc = _api_call(dhan_manager.client.option_chain, under_security_id=sec_id, under_exchange_segment='IDX_I', expiry=expiries[0])
        oc_dict = oc.get('data', {}).get('oc', {}) if oc else {}
        if not oc_dict: oc_dict = oc.get('data', {}).get('data', {}).get('oc', {})
        for s_str, s_data in oc_dict.items():
            if float(s_str) == strike:
                contract = s_data.get(side.lower())
                if contract:
                    val = str(contract.get('security_id'))
                    tele_sec_cache[inst_str] = {'id': val, 'highest': 0.0, 'idx': sec_id}
                    return tele_sec_cache[inst_str]
    except Exception as e:
        logger.error(f"Telegram sec resolve error: {e}")
    return None

def update_telegram_managed_trades(now_time):
    if not os.path.exists(TELEGRAM_EXCEL_PATH): return
    try:
        import pandas as pd
        df = pd.read_excel(TELEGRAM_EXCEL_PATH)
        today_str = now_time.strftime("%Y-%m-%d")
        mask = df['status'].isin(['NEW_SIGNAL', 'T1_HIT', 'T2_HIT']) & df['timestamp'].astype(str).str.startswith(today_str)
        active_idx = df[mask].index
        if len(active_idx) == 0: return
        
        nse_fno = []; bse_fno = []; tracking = {}
        for idx in active_idx:
            inst_str = str(df.loc[idx, 'instrument'])
            cache_obj = get_tele_sec_id(inst_str)
            if cache_obj:
                tracking[idx] = cache_obj['id']
                if cache_obj['idx'] == 442: bse_fno.append(int(cache_obj['id']))
                else: nse_fno.append(int(cache_obj['id']))
                
        live_prices = {}
        if nse_fno or bse_fno:
            sec_dict = {}
            if nse_fno: sec_dict['NSE_FNO'] = nse_fno
            if bse_fno: sec_dict['BSE_FNO'] = bse_fno
            tick_res = _api_call(dhan_manager.client.ticker_data, securities=sec_dict)
            if tick_res and tick_res.get('status') == 'success':
                dmap = tick_res.get('data', {}).get('data', {})
                for k, v in dmap.get('NSE_FNO', {}).items(): live_prices[str(k)] = float(v.get('last_price', 0.0) or 0.0)
                for k, v in dmap.get('BSE_FNO', {}).items(): live_prices[str(k)] = float(v.get('last_price', 0.0) or 0.0)
                
        changed = False
        for idx in active_idx:
            if idx not in tracking: continue
            current_ltp = live_prices.get(tracking[idx], 0.0)
            if current_ltp <= 0: continue
            
            row = df.loc[idx]
            inst_str = str(row['instrument'])
            c_obj = tele_sec_cache[inst_str]
            c_obj['highest'] = max(c_obj['highest'], current_ltp)
            highest = c_obj['highest']
            
            try:
                entry = float(re.search(r'[\\d\\.]+', str(row['entry_range'])).group())
                sl = float(re.search(r'[\\d\\.]+', str(row['stop_loss'])).group())
                tgt = float(re.search(r'[\\d\\.]+', str(row['target'])).group())
            except: continue
            
            exit_triggered = False; reason = ""; exit_px = current_ltp
            
            if highest >= entry * 1.15:
                tsl_floor = max(highest * 0.95, entry * 1.05)
                if current_ltp <= tsl_floor:
                    exit_triggered = True; reason = "TSL_HIT_AT_COST"; exit_px = tsl_floor
            
            if not exit_triggered:
                if current_ltp <= sl: exit_triggered = True; reason = "CLOSED_SL"; exit_px = sl
                elif current_ltp >= tgt: exit_triggered = True; reason = "T3_HIT"; exit_px = tgt
                
            if exit_triggered:
                df.at[idx, 'status'] = reason
                df.at[idx, 'pnl'] = (exit_px - entry) * get_lot_size(inst_str)
                df.at[idx, 'exit_time'] = now_time.strftime("%Y-%m-%d %H:%M:%S")
                changed = True
                logger.info(f"[TELEGRAM AI EXIT] {inst_str} | Reason: {reason} | Entry: {entry} | Exit: {exit_px:.2f} | PnL: Rs. {df.at[idx, 'pnl']:.2f}")
                
        if changed:
            df.to_excel(TELEGRAM_EXCEL_PATH, index=False)
    except Exception as e:
        logger.error(f"Telegram tracking error: {e}")
"""

main_hook = """            # A. Exit Tracking Loop (Runs every 10 seconds)
            if active_trades:
                update_active_trades_exits(now)
            
            # A.1. Telegram AI Exit Tracking
            update_telegram_managed_trades(now)"""

if 'TELEGRAM MANAGED EXITS' not in content:
    content = content.replace('def print_dashboard', tele_code + '\ndef print_dashboard')
    content = content.replace('if active_trades:\r\n                update_active_trades_exits(now)', main_hook)
    content = content.replace('if active_trades:\n                update_active_trades_exits(now)', main_hook)
    codecs.open(r'C:\25stragy\engine_v15.py', 'w', 'utf-8').write(content)
    print('Patched successfully!')
else:
    print('Already patched!')
