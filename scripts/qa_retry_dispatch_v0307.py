from __future__ import annotations
import ast
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
dispatch_path = root / 'apps' / 'ssw' / 'dispatch.py'
views_path = root / 'apps' / 'ssw' / 'views.py'

errors = []
for p in (dispatch_path, views_path):
    if not p.is_file():
        errors.append(f'arquivo ausente: {p}')

if not errors:
    dispatch_src = dispatch_path.read_text(encoding='utf-8', errors='replace')
    views_src = views_path.read_text(encoding='utf-8', errors='replace')
    try:
        tree = ast.parse(dispatch_src)
    except SyntaxError as exc:
        errors.append(f'dispatch.py inválido: {exc}')
        tree = None

    fn = None
    if tree:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'dispatch_robot_run':
                fn = node
                break
    if fn is None:
        errors.append('dispatch_robot_run não encontrado')
    else:
        kwonly = [a.arg for a in fn.args.kwonlyargs]
        if 'priority' not in kwonly:
            errors.append("dispatch_robot_run precisa aceitar keyword-only 'priority'")
        else:
            idx = kwonly.index('priority')
            default = fn.args.kw_defaults[idx]
            if not isinstance(default, ast.Constant) or default.value is not False:
                errors.append("priority deve ter default False")

    if 'run_ssw_robot_guarded' not in dispatch_src:
        errors.append('watchdog run_ssw_robot_guarded ausente no dispatch')
    if 'if priority:' not in dispatch_src:
        errors.append('ramo de retry prioritário ausente')
    if 'dispatch_robot_run(new_run.pk, priority=True)' not in views_src:
        errors.append('views.py não possui a chamada de retry esperada com priority=True')

if errors:
    print('QA RETRY DISPATCH: FAIL')
    for e in errors:
        print('-', e)
    sys.exit(1)

print('QA RETRY DISPATCH: PASS')
print('- dispatch_robot_run(run_id, *, priority=False): OK')
print('- retry_failed_run(... priority=True): OK')
print('- watchdog preservado: OK')
