import re

with open('backtest_high_res.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_logic = '''            atr = atr_s.iloc[i]
            if pd.isna(atr) or atr == 0: atr = atr_fallback
            
            # --- DYNAMIC TIME-BASED RISK/REWARD ---
            golden_hours = dna.get('golden_hours', [])
            if golden_hours and utc_h in golden_hours:
                tp_atr_dynamic = max(dna.get('golden_rr', 3.0), 0.2)
            else:
                tp_atr_dynamic = max(dna.get('fallback_rr', 2.0), 0.2)
                
            sl_pts = (sl_atr*atr)/point
            tp_pts = (tp_atr_dynamic*atr)/point'''

code = code.replace("            atr = atr_s.iloc[i]\n            if pd.isna(atr) or atr == 0: atr = atr_fallback\n            sl_pts = (sl_atr*atr)/point\n            tp_pts = (tp_atr*atr)/point", new_logic)

with open('backtest_high_res.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Updated backtest_high_res.py to use dynamic Time DNA successfully!")
