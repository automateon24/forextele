import sys, time, datetime
import pandas as pd

# Add project root to path
sys.path.append(r"C:\25stragy")
sys.path.append(r"C:\cursor\options\niftyopt")

import engine_v15
from engine_v15 import update_telegram_managed_trades

# Mock Dhan API responses
fake_ltp = 100.0

def mock_api_call(func, *args, **kwargs):
    if "ticker_data" in str(func):
        # Return fake prices
        return {
            "status": "success",
            "data": {
                "data": {
                    "NSE_FNO": {
                        "999999": {"last_price": fake_ltp}
                    }
                }
            }
        }
    if "expiry_list" in str(func):
        return {"status": "success", "data": {"data": ["2026-06-30"]}}
    if "option_chain" in str(func):
        return {
            "status": "success",
            "data": {
                "oc": {
                    "24000": {
                        "ce": {"security_id": "999999", "last_price": 100.0}
                    }
                }
            }
        }
    return {"status": "error"}

# Monkey patch engine_v15
engine_v15._api_call = mock_api_call

def run_simulation():
    global fake_ltp
    
    # 1. Setup the fake excel row
    print("[1] Setting up fake Telegram signal...")
    excel_path = r"C:\25stragy\telegram_signals.xlsx"
    df = pd.read_excel(excel_path)
    
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fake_trade = {
        'instrument': 'NIFTY 50 24000 CE',
        'action': 'BUY',
        'status': 'NEW_SIGNAL',
        'timestamp': today,
        'entry_range': 100.0,
        'stop_loss': 80.0,
        'target': 150.0,
        'pnl': 0.0
    }
    
    # Remove old simulations to keep it clean
    df = df[df['instrument'] != 'NIFTY 50 24000 CE']
    df = pd.concat([df, pd.DataFrame([fake_trade])], ignore_index=True)
    df.to_excel(excel_path, index=False)
    
    # Reset internal cache for simulation
    engine_v15.tele_sec_cache = {}
    
    print("[2] Commencing Market Simulation...")
    
    # Scenario: Price moves up to +18% (activates TSL), dips slightly, then crashes to hit the TSL floor.
    # TSL Activation >= 115
    # TSL Floor at 118 peak = max(118 * 0.95, 105) = 112.1
    scenarios = [
        (100.0, "Entry price (no exit expected)"),
        (110.0, "Moving into profit (no exit expected)"),
        (118.0, "TSL Activation Level crossed (>115), peak logged"),
        (116.0, "Small dip (should NOT exit, TSL floor is 112.1)"),
        (109.0, "Crash below TSL floor (EXPECT EXIT -> TSL_HIT_AT_COST)")
    ]
    
    for px, desc in scenarios:
        fake_ltp = px
        print(f"\n--- Injecting Fake LTP: {px} ({desc}) ---")
        now = datetime.datetime.now()
        
        # Trigger the engine's tracking logic
        update_telegram_managed_trades(now)
        
        # Read back excel to see status
        df_check = pd.read_excel(excel_path)
        trade = df_check[df_check['instrument'] == 'NIFTY 50 24000 CE'].iloc[-1]
        print(f"-> Status: {trade['status']} | PnL: Rs. {trade['pnl']} | Exit Time: {trade.get('exit_time')}")
        
        if trade['status'] != 'NEW_SIGNAL':
            print("\n✅ AI TRADING ENGINE EXITED TRADE SUCCESSFULLY.")
            break
            
        time.sleep(0.5)

if __name__ == "__main__":
    run_simulation()
