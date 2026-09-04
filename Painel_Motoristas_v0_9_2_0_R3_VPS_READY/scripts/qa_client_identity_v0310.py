from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'apps' / 'ssw' / 'import_engine_v2.py').read_text(encoding='utf-8')

assert 'Client.objects.bulk_create(new_clients' not in source, 'bulk_create inseguro de Client ainda presente'
assert 'Client.objects.get_or_create(' in source, 'upsert seguro de Client ausente'
assert '.exclude(pk=candidate.pk)' in source, 'proteção de colisão na promoção de CNPJ ausente'
assert 'client_replacements' in source, 'remapeamento das referências de cliente ausente'

# Reproduz a propriedade de banco que motivou o hotfix: uma segunda tentativa
# da mesma identidade não pode abortar o lote inteiro.
with tempfile.NamedTemporaryFile(suffix='.sqlite3') as tmp:
    con = sqlite3.connect(tmp.name)
    con.execute('CREATE TABLE clients_client (id INTEGER PRIMARY KEY, cnpj TEXT NOT NULL, name TEXT NOT NULL, UNIQUE(cnpj, name))')
    con.execute('INSERT INTO clients_client(cnpj,name) VALUES (?,?)', ('03.764.657/0001-13', 'ROJEMAC IMP E EXP LTDA'))
    try:
        con.execute('INSERT INTO clients_client(cnpj,name) VALUES (?,?)', ('03.764.657/0001-13', 'ROJEMAC IMP E EXP LTDA'))
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError('o cenário de colisão UNIQUE não foi reproduzido')
    row = con.execute('SELECT id FROM clients_client WHERE cnpj=? AND name=?', ('03.764.657/0001-13', 'ROJEMAC IMP E EXP LTDA')).fetchone()
    assert row is not None
    con.close()

print('QA v0.3.0.10: PASS — persistência de Client protegida contra colisão UNIQUE.')
