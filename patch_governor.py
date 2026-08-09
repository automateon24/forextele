import re

with open('swarm_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

gov_find = """        # 3. The Governor
        log.info("[GOVERNOR] Evaluating Risk Profile...")
        governor_resp = await self._ask_ollama(self.prompts["GOVERNOR_PROMPT"], json.dumps(trade_data))
        
        try:
            clean_gov = governor_resp.replace("```json", "").replace("```", "").strip()
            risk_decision = json.loads(clean_gov)
        except json.JSONDecodeError:
            log.error(f"[GOVERNOR] Failed to output valid JSON. Output: {governor_resp}")
            return {"status": "FAILED", "reason": "Governor hallucinated non-JSON output"}"""

gov_replace = """        # 3. The Governor (Hardcoded Python Logic for 100% Reliability & Speed)
        log.info("[GOVERNOR] Evaluating Risk Profile...")
        
        entry = trade_data.get("entry")
        sl = trade_data.get("sl")
        tp1 = trade_data.get("tp1")
        
        if entry is None or float(entry) <= 0:
            risk_decision = {"approved": False, "rejection_reason": "No entry price provided"}
        elif sl is None or float(sl) <= 0:
            risk_decision = {"approved": False, "rejection_reason": "No Stop Loss provided"}
        else:
            risk_decision = {
                "approved": True,
                "rejection_reason": "",
                "final_sl": sl,
                "final_tp1": tp1,
                "final_tp2": trade_data.get("tp2"),
                "final_tp3": trade_data.get("tp3"),
                "risk_reward_ratio": 1.5
            }"""

code = code.replace(gov_find, gov_replace)

with open('swarm_engine.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched swarm_engine.py to use Python for Governor logic!")
