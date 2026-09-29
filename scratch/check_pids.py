import psutil

for p in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'forextele' in cmd or 'terminal64' in (p.info['name'] or '').lower():
            if 'SepPro' not in cmd:
                print(f"PID {p.info['pid']}: {p.info['name']} | CMD: {cmd[:90]}")
    except Exception:
        pass
