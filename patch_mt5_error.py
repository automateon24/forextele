import re

with open('real_mt5_execution.py', 'r', encoding='utf-8') as f:
    code = f.read()

find_err = """        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order failed definitively! Retcode: {result.retcode} Comment: {result.comment}")
            return False"""

replace_err = """        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Order failed definitively! Retcode: {result.retcode} Comment: {result.comment}")
            # Write to alerts
            try:
                alert_path = BASE_DIR / "alerts.json"
                import json, datetime
                alerts = []
                if alert_path.exists():
                    with open(alert_path, "r", encoding="utf-8") as af:
                        try: alerts = json.load(af)
                        except: pass
                alerts.append({
                    "source": f"MT5 Execution ({symbol})",
                    "message": f"Order Failed: {result.comment} (Code {result.retcode}). Price: {final_price} | SL: {sl} | TP: {tp}",
                    "level": "CRITICAL",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                with open(alert_path, "w", encoding="utf-8") as af:
                    json.dump(alerts, af, indent=2)
            except: pass
            return False"""

code = code.replace(find_err, replace_err)

with open('real_mt5_execution.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Injected MT5 Error Reporting into real_mt5_execution.py!")
