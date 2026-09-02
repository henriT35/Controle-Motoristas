# Painel Motoristas — documentação V0.2.2

Esta pasta documenta o sistema e preserva os mockups aprovados em `docs/mockups/`.

## Estado da versão
- Django server-rendered com design dark executivo.
- SQLite para execução local rápida; PostgreSQL como banco oficial/alvo.
- Importador SSW individual e em lote.
- Histórico de ocorrências preservado.
- Data operacional de rota baseada em `SAIDA PARA ENTREGA` (código 85).
- Regra código 34 → comprovante retido.
- Entrega da mercadoria separada da recuperação do comprovante.
- Score configurável e indicadores por motorista/cliente/bairro.
- Operação de Hoje com rotas e oportunidades de retirada.
- Relatórios HTML/XLSX/PDF.
- Configurações, permissões e auditoria.
- Ponto de extensão do robô SSW mantido em `apps/ssw/services.py`.

## Documentos principais
- `BUSINESS_RULES.md`: regras operacionais consolidadas.
- `SSW_IMPORT.md`: importação, deduplicação e múltiplos meses.
- `PROOFS.md`: banco de comprovantes e recuperação.
- `SCORE.md`: fórmula de avaliação.
- `TESTING.md`: testes e captura visual.
- `BUGS_RODADA_01.md`: bugs identificados/corrigidos na V0.2.1.
- `RELATORIO_CORRECOES_V0_2_1.md`: fechamento técnico da release.
- `CHANGELOG.md`: histórico de versões.

- `BUG_NOTEBOOK.md`: funcionamento do Caderno de Bugs integrado.
- `RELATORIO_CORRECOES_V0_2_2.md`: fechamento da V0.2.2.
