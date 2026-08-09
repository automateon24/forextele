import re

with open('live_strategy_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

find_crash = """                    exc = future.exception()
                    if exc:
                        logging.error(f"[{sym_or_engine}] Thread CRASHED: {exc}. Restarting...")
                    else:
                        logging.warning(f"[{sym_or_engine}] Thread Exited. Restarting...")"""

replace_crash = """                    exc = future.exception()
                    if exc:
                        logging.error(f"[{sym_or_engine}] Thread CRASHED: {exc}. Restarting...")
                        try:
                            # Send Alert to Dashboard
                            alert_path = BASE_DIR / "alerts.json"
                            import json, datetime
                            alerts = []
                            if alert_path.exists():
                                with open(alert_path, "r", encoding="utf-8") as af:
                                    try: alerts = json.load(af)
                                    except: pass
                            alerts.append({
                                "source": f"Strategy Engine ({sym_or_engine})",
                                "message": f"Thread crashed: {str(exc)}. Engine is attempting auto-restart.",
                                "level": "CRITICAL",
                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            with open(alert_path, "w", encoding="utf-8") as af:
                                json.dump(alerts, af, indent=2)
                        except: pass
                    else:
                        logging.warning(f"[{sym_or_engine}] Thread Exited. Restarting...")"""

code = code.replace(find_crash, replace_crash)

# Let's also add an alert if MT5 disconnected
find_mt5_dc = """                THREAD_STATUS[symbol] = "Error: MT5 Disconnected"
                init_mt5() # Attempt auto-reconnect
                time.sleep(5)"""

replace_mt5_dc = """                THREAD_STATUS[symbol] = "Error: MT5 Disconnected"
                
                # Send Alert
                try:
                    alert_path = BASE_DIR / "alerts.json"
                    alerts = []
                    if alert_path.exists():
                        with open(alert_path, "r", encoding="utf-8") as af:
                            try: alerts = json.load(af)
                            except: pass
                    # Throttle alerts so we don't spam
                    if not any(a["source"] == "MT5 Terminal" for a in alerts[-3:]):
                        alerts.append({
                            "source": "MT5 Terminal",
                            "message": f"MT5 Disconnected on {symbol} thread. Attempting auto-reconnect.",
                            "level": "WARNING",
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        with open(alert_path, "w", encoding="utf-8") as af:
                            json.dump(alerts, af, indent=2)
                except: pass
                
                init_mt5() # Attempt auto-reconnect
                time.sleep(5)"""

code = code.replace(find_mt5_dc, replace_mt5_dc)

with open('live_strategy_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Injected Crash Alerting into live_strategy_executor.py!")
