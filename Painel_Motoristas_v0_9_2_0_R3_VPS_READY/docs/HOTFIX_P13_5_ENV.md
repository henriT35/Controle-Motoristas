# Hotfix p13.5 — leitura de `.env` com valores entre aspas

## Causa
O configurador p13.4 grava todas as variáveis em formato dotenv seguro, por exemplo:

```env
SSW_OPTION="036"
SSW_UNIT="BEL"
```

O bridge p13.3 fazia parse manual da linha e mantinha as aspas no valor. Assim, comparava `"036"` com `036` e retornava falso erro de divergência.

## Correção
- `check_robot_ready()` passa a usar `dotenv_values()` do `python-dotenv`.
- Fallback manual também remove aspas externas.
- `SSW_OPTION` e `SSW_UNIT` são normalizados antes da comparação.
- Build do bridge: `0.2.2-p13.5`.

## Não altera
- credenciais;
- `.env`;
- banco de dados;
- core Playwright homologado;
- seletores da opção 036.
