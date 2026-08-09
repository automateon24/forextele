import csv
from datetime import datetime
import os

md_table = []
md_table.append('| Time | Channel | Raw Signal | Action | Status | Reason |')
md_table.append('|---|---|---|---|---|---|')

try:
    with open('c:/anlyzeforex/forextele/signals_audit.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if '2026-07-15' in row['Timestamp']:
                time_val = row['Timestamp'].split(' ')[1]
                channel = row['Channel'].strip()[:20]
                raw = row['Raw_Signal'].strip().replace('\n', ' ')
                if len(raw) > 40: raw = raw[:37] + '...'
                
                parsed = row['Parsed_Signal'].strip()
                action = 'None'
                if parsed.startswith('{'):
                    try:
                        import ast
                        p = ast.literal_eval(parsed)
                        action = f"{p.get('action','')} {p.get('symbol','')}"
                    except:
                        pass
                else:
                    action = parsed[:25]

                status = row['Status']
                reason = row['Reason']
                
                md_table.append(f"| {time_val} | {channel} | {raw} | {action} | {status} | {reason} |")
except Exception as e:
    print(e)

os.makedirs('c:/anlyzeforex/forextele/artifacts', exist_ok=True)
with open('c:/anlyzeforex/forextele/artifacts/telegram_signals_report.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_table))
print('Created!')
