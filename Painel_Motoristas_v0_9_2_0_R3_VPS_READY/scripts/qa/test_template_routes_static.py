from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
url_names = set()
for path in list((ROOT / 'apps').rglob('*urls.py')) + [ROOT / 'config' / 'urls.py']:
    text = path.read_text(encoding='utf-8', errors='replace')
    url_names.update(re.findall(r'name\s*=\s*["\']([^"\']+)', text))

unknown = []
for path in (ROOT / 'templates').rglob('*.html'):
    text = path.read_text(encoding='utf-8', errors='replace')
    for name in re.findall(r"\{%\s*url\s+['\"]([^'\"]+)", text):
        if ':' not in name and name not in url_names:
            unknown.append((str(path.relative_to(ROOT)), name))

if unknown:
    print('TEMPLATE ROUTE QA: FAIL')
    for path, name in unknown:
        print(f'- {path}: URL name inexistente: {name}')
    sys.exit(1)

print(f'TEMPLATE ROUTE QA: PASS — {len(url_names)} nomes conhecidos; nenhuma referência estática órfã')
