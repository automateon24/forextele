import sys
import os
import time

# Ensure we can import from src
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.common.messages import SignalMessage
from src.risk.engine import RiskEvaluator

def run_smoke_test():
    print("[SMOKE TEST] Initializing Risk Evaluator...")
    evaluator = RiskEvaluator()
    evaluator.load_config()
    print("[SMOKE TEST] Loaded Config:", evaluator.config)
    print("[SMOKE TEST] Loaded Kill Switch:", evaluator.kill_switch)
    print("[SMOKE TEST] ALL IMPORTS SUCCESSFUL. SKELETON IS HEALTHY.")
    sys.exit(0)

if __name__ == "__main__":
    run_smoke_test()
