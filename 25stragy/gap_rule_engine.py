import json
import os
from datetime import datetime
import pandas as pd

# Global Configurations based on User Spec
CONFIG = {
    "indices": ["NIFTY", "BANKNIFTY", "SENSEX", "MIDCPNIFTY"],
    "time_cutoff": "15:25",
    "risk_lots_per_trade": 1,
    "slippage_pct": 0.05,
    "brokerage_per_order": 20.0
}

OUTPUT_DIR = r"C:\25stragy\gap_predictions"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_global_context():
    """
    Fetch SGX Nifty (GIFT Nifty), S&P500, etc.
    Proxying global drift for Phase 1.
    """
    return 0.45 # Mock positive drift > 0.40 to trigger rule

def score_index(index_name: str, sgx_return: float):
    """
    Apply the fast heuristic Rule-Based Engine.
    In Production, this will consume exact Dhan API 15:25 snapshots.
    """
    # MOCK DATA INGESTION (Phase 1 Stub)
    # This will be replaced by gap_data_ingestion.py hooking into dhanhq
    last_15m_return = 0.30 if index_name == "NIFTY" else -0.15
    futures_premium = 0.25 if index_name == "BANKNIFTY" else 0.10
    closing_imbalance_pct = 0.65
    news_flag = False
    
    # 1. Scoring Logic
    vote_sum = 0
    rationale = []
    
    # SGX Rule
    if sgx_return >= 0.40:
        vote_sum += 1
        rationale.append(f"SGX/GIFT Strong (+{sgx_return:.2f}%)")
    elif sgx_return <= -0.40:
        vote_sum -= 1
        rationale.append(f"SGX/GIFT Weak ({sgx_return:.2f}%)")
        
    # Futures Rule
    if futures_premium >= 0.20:
        vote_sum += 1
        rationale.append(f"Futures Premium High (+{futures_premium:.2f}%)")
    elif futures_premium <= -0.20:
        vote_sum -= 1
        rationale.append(f"Futures Discounted ({futures_premium:.2f}%)")
        
    # Auction/Imbalance Rule
    if closing_imbalance_pct >= 0.60:
        vote_sum += 1
        rationale.append(f"Buy Imbalance ({closing_imbalance_pct*100:.0f}%)")
    elif closing_imbalance_pct <= 0.40:
        vote_sum -= 1
        rationale.append(f"Sell Imbalance ({closing_imbalance_pct*100:.0f}%)")
        
    # Momentum Rule
    if last_15m_return >= 0.25:
        vote_sum += 1
        rationale.append(f"Bullish 15m Momentum (+{last_15m_return:.2f}%)")
    elif last_15m_return <= -0.25:
        vote_sum -= 1
        rationale.append(f"Bearish 15m Momentum ({last_15m_return:.2f}%)")
        
    # 2. Decision Logic
    if vote_sum >= 2:
        decision = "gap_up"
        probability = 0.65 + (vote_sum * 0.05)
        conf = "high" if vote_sum >= 3 else "medium"
    elif vote_sum <= -2:
        decision = "gap_down"
        probability = 0.65 + (abs(vote_sum) * 0.05)
        conf = "high" if vote_sum <= -3 else "medium"
    else:
        decision = "neutral"
        probability = 0.50
        conf = "low"
        
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "index": index_name,
        "decision_time": "15:25",
        "prediction": decision,
        "probability": round(probability, 2),
        "expected_gap_pct": round(vote_sum * 0.15, 2),
        "confidence_bucket": conf,
        "recommended_lots": CONFIG["risk_lots_per_trade"] if decision != "neutral" else 0,
        "rationale": rationale,
        "news_override_flag": news_flag
    }

def run_prediction_pipeline():
    print(f"🚀 Running 15:25 IST Gap Prediction Pipeline...")
    sgx_ret = fetch_global_context()
    print(f"🌐 Global Context (GIFT Nifty Proxy): {sgx_ret:.2f}%")
    
    results = []
    for idx in CONFIG["indices"]:
        decision = score_index(idx, sgx_ret)
        results.append(decision)
        print(f"[{idx}] -> {decision['prediction'].upper()} | Conf: {decision['confidence_bucket']} | Lots: {decision['recommended_lots']}")
        
    # Save output to JSON
    today = datetime.now().strftime("%Y-%m-%d")
    out_file = os.path.join(OUTPUT_DIR, f"gap_prediction_{today}.json")
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=4)
        
    # Inject into Dashboard (live_portfolio_paper_trades.csv)
    csv_path = r"C:\cursor\options\niftyopt\data\live_portfolio_paper_trades.csv"
    try:
        df = pd.DataFrame()
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            
        import math
        import calendar
        from dhanhq import dhanhq
        
        # Init Dhan
        CLIENT_ID = "1101936133"
        TOKEN_FILE = r"C:\cursor\options\niftyopt\config\dhan_tokens.json"
        dhan = None
        try:
            with open(TOKEN_FILE, 'r') as tf:
                tk = json.load(tf)
                dhan = dhanhq(CLIENT_ID, tk.get('access_token'))
        except:
            pass
            
        # Load live states to get spot and expiry
        live_states = {}
        try:
            with open(r"C:\cursor\options\niftyopt\data\live_index_states.json", "r") as fs:
                live_states = json.load(fs)
        except:
            pass
            
        atm_steps = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100, "FINNIFTY": 50, "MIDCPNIFTY": 25}
        
        # Prevent duplicates on same-day runs
        if not df.empty and 'strategy' in df.columns:
            today_str = datetime.now().strftime("%Y-%m-%d")
            mask = (df['strategy'] == 'Gapup_ai') & (df['entry_time'].astype(str).str.startswith(today_str))
            df = df[~mask]
            
        new_records = []
        for r in results:
            if r["prediction"] == "neutral": continue
            
            idx_name = r['index']
            state = live_states.get(idx_name, {})
            spot = state.get("spot", 0)
            exp_date_str = state.get("expiry_date", "2026-07-28")
            
            try:
                dt = datetime.strptime(exp_date_str, "%Y-%m-%d")
                exp_fmt = f"{dt.day:02d} {calendar.month_abbr[dt.month].upper()}"
            except:
                exp_fmt = "28 JUL"
                
            if spot > 0:
                step = atm_steps.get(idx_name, 50)
                atm_strike = int(round(spot / step) * step)
            else:
                atm_strike = 24000
                
            opt_type = "CE" if r["prediction"] == "gap_up" else "PE"
            inst_str = f"{idx_name} 2026-07-{exp_date_str.split('-')[-1]} {float(atm_strike)} {opt_type}" # V15 format
            
            # Fetch LTP from Dhan if possible
            entry_px = 0.0
            opt_sec_id = ""
            if dhan and spot > 0:
                try:
                    sec_map = {"NIFTY":13, "BANKNIFTY":25, "SENSEX":51, "FINNIFTY":27, "MIDCPNIFTY":21}
                    exch_seg = "IDX_I"
                    exp_res = dhan.expiry_list(under_security_id=sec_map.get(idx_name,13), under_exchange_segment=exch_seg)
                    if exp_res.get('status') == 'success':
                        nearest_exp = exp_res['data']['data'][0]
                        oc_res = dhan.option_chain(under_security_id=sec_map.get(idx_name,13), under_exchange_segment=exch_seg, expiry=nearest_exp)
                        if oc_res.get('status') == 'success':
                            strike_key = f"{float(atm_strike):.6f}"
                            strike_data = oc_res['data']['data']['oc'].get(strike_key)
                            if strike_data:
                                opt_sec_id = str(strike_data['ce']['security_id'] if opt_type == 'CE' else strike_data['pe']['security_id'])
                                
                    if opt_sec_id:
                        import time
                        time.sleep(0.6) # Prevent rate limits
                        exch_fno = "BSE_FNO" if idx_name == "SENSEX" else "NSE_FNO"
                        tick = dhan.ticker_data(securities={exch_fno: [int(opt_sec_id)]})
                        if tick and tick.get('status') == 'success':
                            try:
                                entry_px = tick['data']['data'][exch_fno][str(opt_sec_id)]['last_price']
                            except KeyError:
                                pass
                except Exception as ex:
                    print(f"Dhan Fetch Error: {ex}")
            
            if entry_px <= 0:
                entry_px = 100.0 # Ultimate fallback
                
            
            record = {
                "index": idx_name,
                "strategy": "Gapup_ai",
                "direction": opt_type,
                "strike": atm_strike,
                "option_name": inst_str,
                "lots": r["recommended_lots"],
                "entry_time": datetime.now().strftime("%Y-%m-%d 15:30:00"),
                "entry_price": entry_px,
                "entry_spot": spot,
                "highest_premium": entry_px,
                "spot_sl_level": round(spot * 0.99 if opt_type == 'CE' else spot * 1.01, 2),
                "exit_price": "",
                "exit_time": "",
                "exit_reason": "",
                "pnl_rs": "",
                "status": "OPEN",
                "regime": "NORMAL",
                "option_security_id": opt_sec_id
            }
            new_records.append(record)
            
        if new_records:
            df_new = pd.DataFrame(new_records)
            df_combined = pd.concat([df, df_new], ignore_index=True)
            df_combined.to_csv(csv_path, index=False)
            print(f"✅ Injected {len(new_records)} Gap Trades into V15 Portfolio Database!")
    except Exception as e:
        print(f"❌ Failed to inject into Dashboard: {e}")
            
    print(f"✅ Prediction artifact saved to: {out_file}")

if __name__ == "__main__":
    run_prediction_pipeline()
