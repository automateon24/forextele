import ast
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\25stragy\engine_v15.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    node = ast.parse(f.read(), filename=path)

print(f"=== Structure of {path} ===")
for item in node.body:
    if isinstance(item, ast.ClassDef):
        print(f"Class: {item.name}")
        for subitem in item.body:
            if isinstance(subitem, ast.FunctionDef):
                print(f"  Method: {subitem.name}")
    elif isinstance(item, ast.FunctionDef):
        print(f"Function: {item.name}")
