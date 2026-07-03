import ast
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\engine_v15.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.read().splitlines()

target_functions = [
    "get_numerical_strike",
    "resolve_target_strike",
    "get_dynamic_hard_exit",
    "update_active_trades_exits"
]

with open(path, "r", encoding="utf-8", errors="ignore") as f:
    node = ast.parse(f.read(), filename=path)

for item in node.body:
    if isinstance(item, ast.FunctionDef) and item.name in target_functions:
        start = item.lineno - 1
        end = item.end_lineno
        print(f"=== Function: {item.name} (Lines {start+1}-{end}) ===")
        for idx in range(start, end):
            print(f"  {idx+1}: {lines[idx]}")
        print()
