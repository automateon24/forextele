import joblib
import pandas as pd
from pathlib import Path
from swarm_engine import CHANNEL_BLACKLIST

BASE_DIR = Path(r"c:\anlyzeforex\forextele")
MODEL_PATH = BASE_DIR / "final_model_sucess.joblib"

def test_ml_retrained_model():
    print("=" * 70)
    print("TEST 1: RETRAINED ML MODEL INFERENCE & ADAPTIVE THRESHOLDS")
    print("=" * 70)

    assert MODEL_PATH.exists(), "ML Model file does not exist!"
    model = joblib.load(MODEL_PATH)

    test_samples = [
        {"symbol": "USDCHF", "strategy": "ZERO_HERO", "direction": "BUY", "session": "LONDON", "hour": 9, "weekday": 2, "rsi_val": 32.0, "adx_val": 18.0, "atr": 12.0, "sl_pts": 360.0, "tp_pts": 480.0, "expected_threshold": 0.52},
        {"symbol": "GBPJPY", "strategy": "TREND_SURFER", "direction": "BUY", "session": "NY", "hour": 14, "weekday": 3, "rsi_val": 58.0, "adx_val": 28.0, "atr": 25.0, "sl_pts": 750.0, "tp_pts": 1000.0, "expected_threshold": 0.52},
        {"symbol": "GOLD", "strategy": "BREAKOUT_PRO", "direction": "SELL", "session": "LONDON", "hour": 10, "weekday": 1, "rsi_val": 72.0, "adx_val": 31.0, "atr": 4.5, "sl_pts": 1350.0, "tp_pts": 1800.0, "expected_threshold": 0.58},
        {"symbol": "BTCUSD", "strategy": "MOMENTUM_BURST", "direction": "BUY", "session": "NY", "hour": 16, "weekday": 4, "rsi_val": 65.0, "adx_val": 29.0, "atr": 450.0, "sl_pts": 13500.0, "tp_pts": 18000.0, "expected_threshold": 0.68}
    ]

    for item in test_samples:
        expected_t = item.pop("expected_threshold")
        df = pd.DataFrame([item])
        prob = model.predict_proba(df)[0][1]
        approved = prob >= expected_t
        print(f"[{item['symbol']}] {item['strategy']} {item['direction']} -> Win Prob: {prob:.1%} (Threshold: {expected_t:.0%}) -> Status: {'APPROVED' if approved else 'VETOED'}")

def test_channel_blacklist():
    print("\n" + "=" * 70)
    print("TEST 2: TELEGRAM CHANNEL BLACKLIST GATE")
    print("=" * 70)

    test_channels = ["Binance 360", "Sureshot FX VIP", "GOLD DREAMS TRADER", "Crypto World Updates", "JOSEFINA TRADER0"]

    for ch in test_channels:
        ch_lower = ch.lower()
        is_blocked = any(bl in ch_lower for bl in CHANNEL_BLACKLIST)
        print(f"Channel: '{ch}' -> Status: {'REJECTED (Blacklisted)' if is_blocked else 'PASSED (Allowed)'}")

if __name__ == "__main__":
    test_ml_retrained_model()
    test_channel_blacklist()
