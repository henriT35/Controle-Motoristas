# QA COMPLETO — Painel Motoristas v0.3.0.2 → v0.3.0.3

**Rodada:** QA_2026_08_31_001  
**Objetivo:** regressão, idempotência, concorrência, resiliência e caça a corrupção silenciosa.  
**Resultado desta rodada:** **CONDICIONAL** — os testes portáteis/estáticos executáveis no ambiente de construção passaram; a suíte Django completa precisa ser executada no Windows do Painel antes de homologar definitivamente.

## Regra de segurança

Nenhum banco real foi alterado nesta rodada de construção. Não havia Django instalado no ambiente do agente e o acesso ao PyPI estava indisponível, portanto os testes ORM/Django não foram simulados nem marcados como PASS sem evidência.

Para o Windows foi adicionado `qa_import_idempotency`, que testa repetição dentro de uma `transaction.atomic()` e faz **rollback por padrão**, preservando o banco.

## Evidências executadas no ambiente de construção

| Teste | Resultado | Evidência |
|---|---|---|
| Compilação/sintaxe Python | PASS | 138 arquivos Python compilados sem erro |
| Core homologado do robô | PASS | 6/6 hashes SHA-256 do manifesto |
| Contrato Playwright homologado | PASS | `► → 036+Enter → popup → S/BEL/DDMMAA → click → download` |
| Parser no relatório real | PASS | 2.838 linhas |
| CT-es distintos no relatório real | PASS | 2.566 |
| CT-es distintos retidos | PASS | 152 |
| Romaneios com `SAIDA PARA ENTREGA` | PASS | 18 |
| Validação de números/datas/horas no arquivo real | PASS | 0 linhas inválidas |
| Engine v2 sem `get_or_create/update_or_create` | PASS | 0 chamadas no engine otimizado |
| Lock cross-processo presente | PASS estrutural | implementação adicionada e compilada |
| Fingerprint semântico de ocorrência | PASS estrutural | descrição normalizada na identidade |

### Saída do QA portátil

```text
PASS | Sintaxe Python                   | 138 arquivos; erros=0
PASS | Core homologado                  | 6/6 hashes OK
PASS | Lock de importação               | serialização cross-processo
PASS | Fingerprint ocorrência           | descrição normalizada
PASS | Validação silenciosa removida    | número/data/hora inválidos viram WARNING/ignorado
PASS | Engine v2 sem upsert por linha   | calls=[]
PASS | Dataset real parse               | rows=2838, ctes=2566, retained=152, route_manifests=18
PASS | Dataset real validação           | linhas inválidas=0
```

## Bugs encontrados durante a inspeção

### QA-0001 — P1 — corrida entre importações simultâneas

**Problema:** a v0.3.0.2 não possuía lock cross-processo na aplicação dos dados. Duas importações simultâneas poderiam passar pela pré-carga antes da gravação. Constraints protegiam várias entidades, porém `DeliveryOccurrence` não possui unique constraint semântica, então havia risco real de duplicação de ocorrência em concorrência.

**Correção:** `apps/ssw/import_lock.py` serializa a fase de aplicação entre processo Django e worker do robô.

**Reteste local obrigatório:** duas importações simultâneas do mesmo relatório.

### QA-0002 — P1 — ocorrência igual com diferença cosmética podia duplicar

**Problema:** a chave usava a descrição crua. `ENTREGUE` e ` Entregue!!! ` eram identidades diferentes.

**Correção:** identidade usa código + `normalize_text(description)` + data/hora + origem.

### QA-0003 — P1 — valor financeiro inválido virava zero silenciosamente

**Problema:** `parse_br_decimal()` mantém fallback tolerante para compatibilidade, porém o Engine v2 não validava antes de chamar o parser. Texto inválido podia virar `Decimal('0')` sem evidência.

**Correção:** validação explícita de `FRETE CTRC`, `VLR MERC`, `PESO CALCULO`, `QTDE VOL`, datas e horas. Linha inválida é ignorada com `WARNING` e exemplo rastreável. O arquivo real usado na homologação possui zero linhas inválidas nessa validação.

### QA-0004 — P2 — arquivo inválido podia falhar antes de existir ImportRun

**Problema:** parser executava antes da criação da execução. Arquivo vazio/corrompido gerava mensagem na interface, porém podia não deixar histórico técnico.

**Correção:** a view registra `ImportRun ERROR` quando a falha ocorre antes de o importador conseguir criar sua execução.

### QA-0005 — P2 — duas abas podiam registrar o mesmo período ativo

**Problema:** havia consulta `active`/criação sem seção crítica. Dois requests verdadeiramente simultâneos podiam ambos concluir que não existia job ativo.

**Correção:** lock de fila separado (`ssw-queue.lock`) envolve consulta + criação. Jobs `QUEUED/DISPATCHED/RUNNING` da mesma janela/tipo são reutilizados.

### QA-0006 — P2 — importação manual interrompida podia ficar RUNNING

**Problema:** upload manual roda no processo Django. Se o servidor fosse encerrado durante a operação, o registro podia permanecer `RUNNING` após o restart.

**Correção:** `bootstrap_local` reconcilia `ImportRun` MANUAL/RUNNING no próximo startup e marca como ERROR/reprocessável. Jobs do robô não são afetados.

### QA-0007 — P3 — proteção apenas parcial contra clique duplo

**Problema:** upload já desabilitava o botão via JavaScript, mas os formulários de período/reprocessamento não possuíam a mesma proteção visual.

**Correção:** `data-single-submit=1` + bloqueio do submit no `app.js`. A proteção real de servidor continua sendo o lock de fila.

## Testes automatizados adicionados

A suíte do projeto agora possui **50 métodos de teste**, incluindo **14 testes extremos novos** em `apps/ssw/tests_extreme.py`.

Novos cenários automatizados:

- mesmo arquivo 10 vezes;
- mesmo conteúdo com nome diferente;
- linhas embaralhadas;
- duplicidade dentro do próprio arquivo;
- descrição de ocorrência com variação cosmética;
- recuperação manual preservada após reimportação;
- mesmo CNPJ com nome totalmente alterado;
- linha numérica inválida rastreável;
- solicitação ativa duplicada reutiliza ImportRun;
- janeiro→agosto dividido sem lacunas e com janela <=31 dias;
- arquivo vazio gera histórico ERROR;
- fevereiro bissexto;
- datas invertidas;
- exclusividade do lock.

## Ferramentas de QA incluídas

### `TESTAR_QA_EXTREMO_V0_3_0_3.bat`

Executa no Windows:

1. `manage.py check`;
2. testes SSW/extremos/operação/comprovantes/core/bugs/relatórios;
3. auditoria somente leitura do banco;
4. healthcheck.

### `TESTAR_REPETICAO_SSW_V0_3_0_3.bat`

Pede um relatório real e executa:

```text
1ª importação
+ 9 reimportações idênticas
+ cópia com nome diferente
+ cópia com linhas embaralhadas
```

Tudo dentro de uma transação com **rollback por padrão**.

A aprovação exige:

- `stats.new = 0` nas reimportações;
- contagens de entidades de negócio iguais ao estado após a primeira importação;
- fingerprint operacional idêntico;
- ImportRun pode variar dentro do teste, mas é revertido junto com a transação.

### `VERIFICAR_INTEGRIDADE_SSW_V0_3_0_3.bat`

Auditoria somente leitura para detectar:

- CPF duplicado;
- placa duplicada;
- CTRC duplicado;
- romaneio duplicado;
- endereço duplicado;
- movimento CTe+romaneio duplicado;
- comprovante duplicado;
- CNPJ normalizado associado a múltiplos clientes;
- ocorrência semanticamente duplicada.

## Testes NÃO EXECUTADOS neste ambiente

Os seguintes cenários foram implementados/cobertos por testes ou ferramentas, mas **não são marcados como PASS nesta máquina**, porque Django não está instalado e o ambiente não possui acesso à internet para instalar a dependência:

- 50 testes Django completos;
- importação real 2x/5x/10x via ORM;
- concorrência real entre dois requests Django;
- transaction rollback do engine real;
- recuperação manual ORM após reimportação;
- permissões Admin/Coordenador/Analista via client Django;
- DEBUG=False e static via servidor Django;
- benchmark de queries ORM;
- stress 10k/25k/50k;
- reinício real do servidor durante importação;
- teste multiusuário HTTP.

Esses testes devem ser executados pelo script no Windows antes de declarar homologação final.

## Matriz resumida

| Cenário | Estado nesta rodada |
|---|---|
| Core robô homologado | PASS |
| Parser real | PASS |
| Integridade dos hashes | PASS |
| Sintaxe do projeto | PASS |
| Validação do arquivo real | PASS |
| Mesmo arquivo 10x via Django | NÃO EXECUTADO AQUI / teste automatizado criado |
| Arquivo renomeado via Django | NÃO EXECUTADO AQUI / teste automatizado criado |
| Linhas embaralhadas via Django | NÃO EXECUTADO AQUI / teste automatizado criado |
| Concorrência real | NÃO EXECUTADO AQUI / lock implementado + teste criado |
| Período >31 dias | regra inspecionada + teste criado |
| Fora de ordem | teste existente preservado |
| Retenção + entregue | teste existente preservado |
| Recuperação manual + reimportação | teste novo criado |
| Valor inválido | bug reproduzido no parser v0.3.0.2 e correção adicionada |
| Restart durante MANUAL | correção adicionada; reteste local pendente |

## Critério de homologação no Windows

Executar, nesta ordem:

```text
TESTAR_QA_EXTREMO_V0_3_0_3.bat
TESTAR_REPETICAO_SSW_V0_3_0_3.bat
VERIFICAR_INTEGRIDADE_SSW_V0_3_0_3.bat
```

Somente homologar se os três terminarem com `PASS/OK` e não houver P0/P1 pendente.

## Estado de aprovação

**Ainda não declarar “zero bugs”.** A rodada encontrou sete problemas e os corrigiu no código, mas a regressão Django completa precisa rodar no ambiente real. A versão corrigida recebe o número **v0.3.0.3 — QA Hardening**.
