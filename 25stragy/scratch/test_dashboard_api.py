import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    r = requests.get("http://127.0.0.1:8000/api/data", timeout=5)
    data = r.json()
    print("Dashboard Response Status:", r.status_code)
    print("Self Learning Audit present:", "self_learning_audit" in data)
    if "self_learning_audit" in data:
        print("Tuning Audit Records Count:", len(data["self_learning_audit"]))
        print("First record keys:", list(data["self_learning_audit"][0].keys()) if data["self_learning_audit"] else "None")
except Exception as e:
    print("Error calling dashboard server:", e)
