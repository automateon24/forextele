import re

with open(r'C:\cursor\options\niftyopt\dashboard_server.py', 'r', encoding='utf-8') as f:
    code = f.read()

pattern = re.compile(r'(if status in \["CLOSED_SL", "MANUAL_BOOK", "T3_HIT", "TSL_HIT_AT_COST", "TSL_HIT_AT_T1", "SL_HIT"\]:.*?tele_realized \+= pnl_val.*?telegram_completed\.append\(trade_obj\).*?else:.*?tele_margin \+= cap_utilized.*?telegram_active\.append\(trade_obj\))', re.DOTALL)

replacement = """if status in ["CLOSED_SL", "MANUAL_BOOK", "T3_HIT", "TSL_HIT_AT_COST", "TSL_HIT_AT_T1", "SL_HIT", "EOD_CLOSE", "EOD_CLOSE_UNTRACKED"]:
                    is_hold_overnight = False
                    if "2626583811" in chan_id or "2412774015" in chan_id or "2264960458" in chan_id or "2231238486" in chan_id:
                        is_hold_overnight = True
                        
                    if is_hold_overnight and status in ["EOD_CLOSE", "EOD_CLOSE_UNTRACKED"]:
                        tele_margin += cap_utilized
                        trade_obj["status"] = "OPEN (OVERNIGHT)"
                        telegram_active.append(trade_obj)
                    else:
                        tele_realized += pnl_val
                        telegram_completed.append(trade_obj)
                else:
                    tele_margin += cap_utilized
                    telegram_active.append(trade_obj)"""

if pattern.search(code):
    code = pattern.sub(replacement, code)
    with open(r'C:\cursor\options\niftyopt\dashboard_server.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print('Successfully applied python regex patch')
else:
    print('Failed to find regex target in code')
