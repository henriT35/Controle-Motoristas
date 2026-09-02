# BUGS — RODADA 01 — V0.2.1

## Resumo

```text
P0 confirmados: 0
P1 tratados no código: 8
P2 tratados no código: 6
P3 tratados no código: 1
Total registrado: 15
Runtime retestado neste ambiente: 0 (Django indisponível)
Testes automatizados adicionados/expandido: sim
```

> Critério de fechamento: os itens abaixo possuem correção aplicada e, quando possível, teste automatizado correspondente. O status **Runtime pendente** significa que o reteste final deve ser executado no Windows com `TESTAR_SISTEMA.bat`. Não foi fabricado PASS de runtime.

---

## BUG-001 — Rota do dia usava data de emissão do romaneio
- **Tela:** Operação de Hoje / indicadores por período
- **Prioridade:** P1
- **Resultado anterior:** romaneio criado em D-1 podia ficar associado a D-1 mesmo saindo para entrega em D0.
- **Esperado:** `SAIDA PARA ENTREGA` em D0 define a data operacional.
- **Correção:** serviços centrais `route_exit_occurrences`, `operational_manifest_ids`, `manifests_for_operational_date`, `operational_movements_for_period` e `operational_date_for_manifest`.
- **Teste:** cenário 30/08 emissão → 31/08 saída.
- **Status:** correção aplicada; runtime pendente.

## BUG-002 — ENTREGUE posterior podia fazer a rota desaparecer do dia de saída
- **Tela:** Operação de Hoje
- **Prioridade:** P1
- **Resultado anterior:** consultas dependentes de estado/data atual não preservavam corretamente o vínculo operacional.
- **Esperado:** 08:00 saída + 12:30 entregue continua rota do mesmo dia.
- **Correção:** rota usa histórico de ocorrência `SAIDA PARA ENTREGA`, não o status atual.
- **Teste:** incluído em `apps/operations/tests.py`.
- **Status:** correção aplicada; runtime pendente.

## BUG-003 — Dashboard/Motoristas/Clientes/Relatórios filtravam por data de movimento/emissão
- **Tela:** múltiplas
- **Prioridade:** P1
- **Resultado anterior:** métricas podiam cair no dia/mês errado quando romaneio foi preparado antecipadamente.
- **Esperado:** agregações operacionais usam a data de saída da rota.
- **Correção:** telas passaram a usar `operational_movements_for_period`/`operational_date_map`.
- **Status:** correção aplicada; runtime pendente.

## BUG-004 — Importação fora de ordem podia regredir status do CT-e
- **Tela:** Importações / banco
- **Prioridade:** P1
- **Cenário:** importar arquivo novo (`ENTREGUE`) e depois histórico (`SAIDA PARA ENTREGA`).
- **Esperado:** status atual continua no evento mais recente/avançado; histórico antigo permanece como ocorrência.
- **Correção:** atualização temporal do CT-e evita regressão por arquivo histórico.
- **Teste:** `test_older_file_imported_later_does_not_regress_current_cte_status`.
- **Status:** correção aplicada; runtime pendente.

## BUG-005 — Romaneio BAIXADO podia regredir para PENDENTE
- **Tela:** Importações / banco
- **Prioridade:** P1
- **Correção:** ranking de status impede downgrade operacional em reprocessamento antigo.
- **Teste:** `test_manifest_status_does_not_regress_from_baixado_to_pendente`.
- **Status:** correção aplicada; runtime pendente.

## BUG-006 — Retenção histórica mais antiga importada depois não ajustava a origem
- **Tela:** Comprovantes / importação
- **Prioridade:** P1
- **Esperado:** data/origem da retenção representa o primeiro evento conhecido.
- **Correção:** backfill da data, motorista/romaneio original quando evento mais antigo é descoberto.
- **Teste:** `test_older_retention_imported_later_backfills_origin_date`.
- **Status:** correção aplicada; runtime pendente.

## BUG-007 — Recuperação aceitava datas operacionalmente inválidas
- **Tela:** Comprovantes
- **Prioridade:** P1
- **Casos:** data anterior à retenção ou futura.
- **Correção:** validação server-side antes de marcar como recuperado.
- **Testes:** ambos os cenários em `apps/proofs/tests.py`.
- **Status:** correção aplicada; runtime pendente.

## BUG-008 — Criticidade tratava limite de 15 dias de forma inconsistente
- **Tela:** Comprovantes/Dashboard
- **Prioridade:** P1
- **Regra:** crítico somente com **mais de 15 dias** no default.
- **Teste:** 15 dias = não crítico; 16 dias = crítico.
- **Status:** correção aplicada; runtime pendente.

## BUG-009 — Oportunidade de retirada podia contar o mesmo comprovante mais de uma vez
- **Tela:** Operação de Hoje
- **Prioridade:** P2
- **Correção:** resumo usa conjuntos de IDs; match exato prevalece sobre regional.
- **Teste:** cobertura em `apps/operations/tests.py`.
- **Status:** correção aplicada; runtime pendente.

## BUG-010 — Match de CNPJ era sensível a máscara/pontuação
- **Tela:** Operação de Hoje / Comprovantes
- **Prioridade:** P2
- **Correção:** `normalize_identifier` remove máscara de CNPJ/CPF/CEP para comparação.
- **Status:** correção aplicada; runtime pendente.

## BUG-011 — Cliente podia duplicar por variação de pontuação no nome/CNPJ
- **Tela:** Clientes / importação
- **Prioridade:** P2
- **Cenário:** `ATACADAO S A` x `ATACADAO S.A.` com mesmo CNPJ.
- **Correção:** cache de identidade por CNPJ + nome normalizado.
- **Testes:** cenários com/sem CNPJ em `apps/ssw/tests.py`.
- **Status:** correção aplicada; runtime pendente.

## BUG-012 — Operação de Hoje não consolidava corretamente entregas/oportunidades da rota
- **Tela:** Operação de Hoje
- **Prioridade:** P2
- **Correção:** cards usam CT-es concluídos por ocorrência, clientes únicos, bairros, cidades e oportunidades únicas por comprovante.
- **Status:** correção aplicada; runtime pendente.

## BUG-013 — Faltava importação prática de vários meses
- **Tela:** Importações SSW / Windows
- **Prioridade:** P2
- **Correção:** `IMPORTAR_LOTE_SSW.bat`, comando `import_ssw_batch` e seleção múltipla na interface.
- **Comportamento:** ordenação por período detectado e continuidade após falha individual.
- **Status:** implementado; runtime pendente.

## BUG-014 — Sidebar desaparecia em largura menor sem experiência de navegação equivalente
- **Tela:** interface global
- **Prioridade:** P2
- **Correção:** drawer/menu mobile e ajustes de CSS/JS.
- **Status:** correção aplicada; validação visual pendente.

## BUG-015 — Captura de homologação usava data do último romaneio e diretório da versão anterior
- **Tela:** ferramenta de homologação
- **Prioridade:** P3
- **Correção:** `capture_screens.py` usa `latest_operational_date()` e grava em `docs/homologacao/v0_2_1/`.
- **Status:** correção aplicada; execução Playwright pendente no Windows.

---

# Pendências não classificadas como bug corrigível localmente

## ROBÔ-SSW-001 — Playwright no SSW real
Dependência externa de integração. Exige credenciais e validação das telas do SSW. A aplicação mantém contratos/execuções sem simular sucesso.

## HOMOLOGAÇÃO-RUNTIME-001 — Testes Django e screenshots reais
Executar no Windows:

```text
TESTAR_SISTEMA.bat
CAPTURAR_TELAS.bat
```

Somente depois desses comandos deve-se marcar a V0.2.1 como runtime/visualmente homologada.
