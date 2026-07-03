import json
import os
from datetime import datetime, timedelta
import pandas as pd

PREDICTIONS_DIR = r"C:\25stragy\gap_predictions"
TRAINING_DATA_FILE = r"C:\25stragy\gap_training_data.csv"

def get_yesterday_predictions():
    # In production, this calculates the last trading day. Using simple logic for demo.
    files = sorted([f for f in os.listdir(PREDICTIONS_DIR) if f.endswith('.json')])
    if not files:
        print("No predictions found from yesterday.")
        return None
        
    latest_file = os.path.join(PREDICTIONS_DIR, files[-1])
    with open(latest_file, 'r') as f:
        return json.load(f)

def analyze_morning_retrace(index_name: str, predicted_direction: str):
    """
    Simulates the 9:07 AM Pre-Open and 9:15 AM Fade/Follow-through analysis.
    In Production: This will fetch Live Pre-Open IEP, SGX Nifty Live, and VIX.
    """
    # MOCK DATA FOR PROTOTYPE
    actual_pre_open_gap = 0.50 if predicted_direction == "gap_up" else -0.50
    live_sentiment = 0.8 # Highly bullish
    
    # 9:07 AM Logic: Does the actual gap match the predicted direction?
    is_direction_correct = (predicted_direction == "gap_up" and actual_pre_open_gap > 0) or \
                           (predicted_direction == "gap_down" and actual_pre_open_gap < 0)
                           
    # 9:15 AM Logic: Will it fade (retrace) or follow-through?
    # Example logic: If it gaps up massively (>0.8%) but sentiment is cooling, it will fade.
    will_fade = False
    action = "HOLD_FOR_30_MINS"
    
    if is_direction_correct:
        if abs(actual_pre_open_gap) > 0.80 and live_sentiment < 0.5:
            will_fade = True
            action = "EXIT_AT_915_OPEN" # Lock in massive gap up before it retraces
    else:
        # Prediction was wrong (e.g. predicted Gap Up, but opened Gap Down)
        action = "EXIT_IMMEDIATELY_AT_915" # Cut losses immediately
        
    return {
        "actual_gap_pct": actual_pre_open_gap,
        "is_correct": is_direction_correct,
        "will_fade": will_fade,
        "recommended_action": action
    }

def update_self_learning_loop(predictions, results):
    """
    Appends the prediction and the actual morning outcome to the historical dataset.
    The AI (LightGBM) will use this file on weekends to retrain its probabilities.
    """
    records = []
    today = datetime.now().strftime("%Y-%m-%d")
    
    for p, r in zip(predictions, results):
        record = {
            "date": today,
            "index": p["index"],
            "predicted_dir": p["prediction"],
            "predicted_prob": p["probability"],
            "actual_gap_pct": r["actual_gap_pct"],
            "is_correct": r["is_correct"],
            "fade_occurred": r["will_fade"],
            "action_taken": r["recommended_action"]
        }
        records.append(record)
        
    df_new = pd.DataFrame(records)
    
    if os.path.exists(TRAINING_DATA_FILE):
        df_existing = pd.read_csv(TRAINING_DATA_FILE)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new
        
    df_combined.to_csv(TRAINING_DATA_FILE, index=False)
    print(f"🧠 Added {len(records)} records to Self-Learning Dataset: {TRAINING_DATA_FILE}")

def run_morning_exit():
    print("🌅 Running 9:07 AM Pre-Open & Exit Analysis...")
    predictions = get_yesterday_predictions()
    if not predictions: return
    
    results = []
    for p in predictions:
        res = analyze_morning_retrace(p["index"], p["prediction"])
        results.append(res)
        
        status = "✅ HIT" if res["is_correct"] else "❌ MISS"
        print(f"[{p['index']}] Pred: {p['prediction'].upper()} | Act: {res['actual_gap_pct']}% | {status} | Action: {res['recommended_action']}")
        
    update_self_learning_loop(predictions, results)
    print("✅ Morning loop complete. Awaiting 15:25 for next prediction.")

if __name__ == "__main__":
    run_morning_exit()
