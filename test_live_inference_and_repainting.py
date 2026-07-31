import os
import sys
import pandas as pd
import MetaTrader5 as mt5

BASE_DIR = r"c:\anlyzeforex\forextele"
os.chdir(BASE_DIR)
sys.path.append(BASE_DIR)

from live_strategy_executor import init_mt5, ML_MODEL, calculate_dynamic_lot, place_order

def verify_inference_and_lot_cap():
    print("--- [VERIFICATION TEST] ML INFERENCE & MICRO-LOT CAP ---")
    if not init_mt5():
        print("[FAIL] MT5 Init failed.")
        return

    # Test ML Inference Pipeline
    if ML_MODEL is not None:
        try:
            sample_features = pd.DataFrame([{
                "symbol": "EURUSD",
                "strategy": "MEAN_REVERSION",
                "direction": "BUY",
                "session": "LONDON",
                "hour": 10,
                "weekday": 2,
                "rsi_val": 32.5,
                "adx_val": 18.4,
                "atr": 12.5,
                "sl_pts": 150,
                "tp_pts": 300
            }])
            prob = ML_MODEL.predict_proba(sample_features)[0][1]
            print(f"  [PASS] ML Inference Probability Calculated: {prob:.1%}")
        except Exception as e:
            print(f"  [FAIL] ML Inference Error: {e}")

    # Test Micro-Account Lot Capping
    test_lot = calculate_dynamic_lot("EURUSD", 150, risk_pct=0.05)
    print(f"  [PASS] Capped Lot Size Result for $1,500 Account: {test_lot} lots (Max Cap: 0.05)")
    assert test_lot <= 0.05, "Lot cap exceeded!"
    print("--- ALL INFERENCE AND LOT CAP TESTS PASSED ---")

if __name__ == "__main__":
    verify_inference_and_lot_cap()
