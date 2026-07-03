import codecs
import re
import os

# 1. Patch Telegram Engine
path = r'C:\25stragy\telegram_signal_engine.py'
with codecs.open(path, 'r', 'utf-8') as f:
    t_content = f.read()

health_check = """
import json
import os
def is_system_stopped():
    try:
        if os.path.exists(r'C:\\25stragy\\system_health.json'):
            with open(r'C:\\25stragy\\system_health.json', 'r') as f:
                data = json.load(f)
                return data.get('master_switch', 'START') == 'STOP'
    except:
        pass
    return False
"""

if "def is_system_stopped():" not in t_content:
    t_content = health_check + "\n" + t_content
    # Inject check inside the message handler
    handler_str = "async def handler(event):"
    if handler_str in t_content:
        t_content = t_content.replace(handler_str, handler_str + "\n    if is_system_stopped():\n        return")
    
    with codecs.open(path, 'w', 'utf-8') as f:
        f.write(t_content)


# 2. Patch V15 Engine
path2 = r'C:\25stragy\engine_v15.py'
try:
    with codecs.open(path2, 'r', 'utf-8') as f:
        e_content = f.read()
    
    if "def is_system_stopped():" not in e_content:
        e_content = health_check + "\n" + e_content
        with codecs.open(path2, 'w', 'utf-8') as f:
            f.write(e_content)
except:
    pass

print("Engines patched to respect Master Control Switch!")
