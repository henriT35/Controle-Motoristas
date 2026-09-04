from pathlib import Path
import ast
import builtins
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "apps" / "ssw" / "views.py"

tree = ast.parse(TARGET.read_text(encoding="utf-8-sig"), filename=str(TARGET))
defined = set(dir(builtins))
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        defined.add(node.name)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            defined.add(alias.asname or alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if alias.name != "*":
                defined.add(alias.asname or alias.name)

issues = []
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        for decorator in node.decorator_list:
            for child in ast.walk(decorator):
                if isinstance(child, ast.Name) and child.id not in defined:
                    issues.append((node.lineno, child.id))

if issues:
    for line, name in issues:
        print(f"ERRO: decorator/nome global não resolvido em apps/ssw/views.py:{line}: {name}")
    sys.exit(1)

required = "from django.views.decorators.http import require_POST"
source = TARGET.read_text(encoding="utf-8-sig")
if required not in source:
    print(f"ERRO: import obrigatório ausente: {required}")
    sys.exit(1)

print("OK: decorators de apps/ssw/views.py estão resolvidos; require_POST importado.")
