# PROCESSO DE ATUALIZAÇÃO E EMPACOTAMENTO

## Fonte de verdade
A fonte de verdade é sempre a **baseline completa declarada**, nunca um patch antigo isolado.

## Fluxo de desenvolvimento
1. Descompactar a baseline.
2. Criar cópia de trabalho com nome da nova versão.
3. Registrar no CHANGELOG o escopo antes de editar.
4. Alterar somente módulos necessários.
5. Manter `robot_ssw` congelado.
6. Rodar QA estático e funcional disponível.
7. Comparar árvore com a baseline.
8. Montar PATCH somente com arquivos alterados/adicionados/removidos.
9. Aplicar o PATCH numa cópia limpa da baseline.
10. Comparar a cópia patchada com a árvore final.
11. Gerar baseline ZIP e patch ZIP.
12. Gerar `.sha256`.

## Patch
O patch deve conter:
- `payload/` com arquivos finais;
- lista de arquivos removidos, se houver;
- aplicador PowerShell compatível com Windows PowerShell 5.1;
- README indicando versão-base e instruções.

Evitar o erro antigo de `TrimStart('\\','/')` em PowerShell 5.1. Use `[char[]]` para separadores.

## Versionamento
- Patch pequeno/hotfix: incremento de patch.
- Mudança funcional relevante: minor.
- Rodada transversal com UX + domínio + fluxo: versão maior do ciclo, como v0.9.0.0.

## Verificação de segurança antes do ZIP/Git
Pesquisar por:
- `.env`;
- `local_data`;
- `*.sqlite3`;
- `node_modules`;
- `.venv`;
- `baileys_auth`;
- `credenciais.local.json`;
- logs/uploads reais.

## GitHub
Repositório: `https://github.com/henriT35/Controle-Motoristas.git`.

Primeiro push:
```powershell
git init
git add .
git status
git commit -m "Painel Motoristas"
git branch -M main
git remote add origin https://github.com/henriT35/Controle-Motoristas.git
git push -u origin main
```

Atualização:
```powershell
git add .
git status
git commit -m "descricao"
git push
```

VPS:
```bash
git pull
docker compose up -d --build
```
