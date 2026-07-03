import psutil
import datetime

print("=======================================================================")
print("          PYTHON PROCESS HIERARCHY TRACE")
print(f"          Time: {datetime.datetime.now()}")
print("=======================================================================")

for p in psutil.process_iter():
    if 'python' in p.name().lower():
        pid = p.pid
        ppid = p.ppid()
        try:
            p_proc = psutil.Process(ppid)
            p_name = p_proc.name()
            p_cmd = p_proc.cmdline()
        except Exception:
            p_name = "Unknown/Dead"
            p_cmd = []
        
        try:
            cmd = p.cmdline()
            ctime = datetime.datetime.fromtimestamp(p.create_time()).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            cmd = []
            ctime = "Unknown"
            
        print(f"PID: {pid}")
        print(f"  Started: {ctime}")
        print(f"  Command: {cmd}")
        print(f"  Parent PID: {ppid}")
        print(f"  Parent Name: {p_name}")
        print(f"  Parent Command: {p_cmd}")
        print("-" * 71)
