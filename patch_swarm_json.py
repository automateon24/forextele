import re

with open('swarm_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

log_audit_find = """        with open(audit_file, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Account", "Channel", "Raw_Signal", "Parsed_Signal", "Status", "Reason", "Trade_Number"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                account_id,
                channel_name,
                clean_raw,
                parsed_str,
                status,
                reason,
                trade_num
            ])"""

log_audit_replace = """        with open(audit_file, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Account", "Channel", "Raw_Signal", "Parsed_Signal", "Status", "Reason", "Trade_Number"])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                account_id,
                channel_name,
                clean_raw,
                parsed_str,
                status,
                reason,
                trade_num
            ])
            
        # Write to JSON log for Dashboard visibility
        json_log_file = BASE_DIR / "message_ai_log.json"
        try:
            logs = []
            if json_log_file.exists():
                with open(json_log_file, "r", encoding="utf-8") as jf:
                    logs = json.load(jf)
            
            # Keep only last 200 logs
            if len(logs) > 200:
                logs = logs[-200:]
                
            entry = {
                "channel_name": channel_name,
                "message": raw_message,
                "ai_reply": json.dumps(parsed_data) if parsed_data else '{"action": "NO_TRADE"}',
                "order_status": "Success" if status == "SUCCESS" else "Failed",
                "error_msg": reason if status != "SUCCESS" else None,
                "ticket": parsed_data.get("ticket", None) if parsed_data else None,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logs.append(entry)
            
            with open(json_log_file, "w", encoding="utf-8") as jf:
                json.dump(logs, jf, indent=2)
        except Exception as e:
            log.error(f"Failed to write to JSON log: {e}")"""

code = code.replace(log_audit_find, log_audit_replace)

with open('swarm_engine.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched swarm_engine.py to log to message_ai_log.json!")
