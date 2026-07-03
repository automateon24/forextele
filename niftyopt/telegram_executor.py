import sys
import os
import json
import time
import re
import pandas as pd
from datetime import datetime
from dhanhq import dhanhq

# -------------------------------------------------------------
# TELEGRAM AUTONOMOUS EXECUTION ENGINE (DHAN)
# -------------------------------------------------------------

TOKEN_FILE = r"C:\cursor\options\niftyopt\config\dhan_tokens.json"
EXCEL_LOG_PATH = r"C:\25stragy\telegram_signals.xlsx"

INDEX_MAP = {
    "NIFTY": {"id": 13, "seg": "IDX_I", "lot": 25},
    "BANKNIFTY": {"id": 25, "seg": "IDX_I", "lot": 15},
    "SENSEX": {"id": 51, "seg": "IDX_I", "lot": 10},
    "FINNIFTY": {"id": 27, "seg": "IDX_I", "lot": 25}
}

class TelegramDhanExecutor:
    def __init__(self):
        print("🚀 Initializing Telegram Autonomous Execution Engine...")
        with open(TOKEN_FILE, 'r') as f:
            tokens = json.load(f)
            self.client_id = tokens.get("CLIENT_ID", "")
            self.access_token = tokens.get("ACCESS_TOKEN", "")
            
        self.dhan = dhanhq(self.client_id, self.access_token)
        self.active_contracts = {} # instrument -> security_id
        
    def _parse_instrument(self, instrument_str):
        """
        Parses 'BANKNIFTY 28 JUL 58000 CALL' -> ('BANKNIFTY', 58000, 'CALL')
        """
        inst_upper = instrument_str.upper()
        
        idx = None
        for key in INDEX_MAP:
            if key in inst_upper:
                idx = key
                break
                
        if not idx:
            return None # Not an index we can auto-trade yet (e.g. MCX)
            
        strike_match = re.search(r'(\d{4,5})', inst_upper)
        if not strike_match:
            return None
        strike = int(strike_match.group(1))
        
        opt_type = "CALL" if "CE" in inst_upper or "CALL" in inst_upper else "PUT"
        
        return idx, strike, opt_type

    def get_security_id(self, idx, strike, opt_type):
        """
        Fetches the Dhan security ID for the given parameters.
        """
        try:
            sec_id = INDEX_MAP[idx]["id"]
            exch_seg = INDEX_MAP[idx]["seg"]
            
            exp_res = self.dhan.expiry_list(under_security_id=sec_id, under_exchange_segment=exch_seg)
            if exp_res.get('status') != 'success': return None
            
            # Use nearest expiry
            nearest_exp = exp_res['data'][0]
            
            oc_res = self.dhan.option_chain(under_security_id=sec_id, under_exchange_segment=exch_seg, expiry=nearest_exp)
            if oc_res.get('status') != 'success': return None
            
            for item in oc_res['data']:
                if item['strikePrice'] == float(strike):
                    return item['ceSecurityId'] if opt_type == "CALL" else item['peSecurityId']
            return None
        except Exception as e:
            print(f"Error fetching security ID: {e}")
            return None

    def get_ltp(self, security_id):
        try:
            sec_dict = {"NSE_FNO": [security_id]} # Assuming NSE
            tick = self.dhan.ticker_data(securities=sec_dict)
            if tick and tick.get('status') == 'success':
                data = tick.get('data', {})
                for k, v in data.items():
                    return v.get('last_price', 0)
        except Exception:
            pass
        return 0

    def run_loop(self):
        print("🟢 Monitoring Telegram Signals for Autonomous Execution...")
        while True:
            try:
                if not os.path.exists(EXCEL_LOG_PATH):
                    time.sleep(5)
                    continue
                    
                df = pd.read_excel(EXCEL_LOG_PATH)
                open_trades = df[df['status'].isin(['NEW_SIGNAL', 'OPEN'])]
                
                updated = False
                
                for idx, row in open_trades.iterrows():
                    inst = str(row['instrument'])
                    parsed = self._parse_instrument(inst)
                    
                    if not parsed:
                        continue # Not an index, ignore for now
                        
                    index_name, strike, opt_type = parsed
                    
                    if inst not in self.active_contracts:
                        sec_id = self.get_security_id(index_name, strike, opt_type)
                        if sec_id:
                            self.active_contracts[inst] = sec_id
                            print(f"🔗 Mapped {inst} -> Dhan Security ID: {sec_id}")
                    
                    sec_id = self.active_contracts.get(inst)
                    if not sec_id: continue
                    
                    ltp = self.get_ltp(sec_id)
                    if ltp <= 0: continue
                    
                    # Update live price in a custom column or process target
                    try:
                        entry = float(re.search(r'[\d\.]+', str(row['entry_range'])).group())
                        sl = float(re.search(r'[\d\.]+', str(row['stop_loss'])).group())
                        tgt = float(re.search(r'[\d\.]+', str(row['target'])).group())
                    except:
                        continue
                        
                    lot_size = INDEX_MAP[index_name]["lot"]
                    
                    # Autonomous Target & SL Logic
                    if ltp >= tgt:
                        print(f"✅ TARGET HIT: {inst} @ {ltp}")
                        df.at[idx, 'status'] = 'T1_HIT'
                        df.at[idx, 'pnl'] = (ltp - entry) * lot_size
                        df.at[idx, 'exit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        updated = True
                    elif ltp <= sl:
                        print(f"❌ SL HIT: {inst} @ {ltp}")
                        df.at[idx, 'status'] = 'CLOSED_SL'
                        df.at[idx, 'pnl'] = (ltp - entry) * lot_size
                        df.at[idx, 'exit_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        updated = True
                        
                # Dump live prices to JSON for the Dashboard
                live_prices_path = r"C:\25stragy\telegram_live_prices.json"
                live_price_dict = {}
                for inst, sec_id in self.active_contracts.items():
                    ltp = self.get_ltp(sec_id)
                    if ltp > 0:
                        live_price_dict[inst] = ltp
                
                with open(live_prices_path, 'w') as f:
                    json.dump(live_price_dict, f)
                        
                if updated:
                    df.to_excel(EXCEL_LOG_PATH, index=False)
                    
            except Exception as e:
                print(f"Engine Loop Error: {e}")
                
            time.sleep(3)

if __name__ == '__main__':
    executor = TelegramDhanExecutor()
    executor.run_loop()
