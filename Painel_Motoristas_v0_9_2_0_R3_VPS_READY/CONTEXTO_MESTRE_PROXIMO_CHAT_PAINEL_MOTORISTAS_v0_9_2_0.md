# CONTEXTO MESTRE — PRÓXIMO CHAT — PAINEL MOTORISTAS v0.9.2.0

**Data:** 03/09/2026  
**Baseline atual:** `v0.9.2.0` candidata à homologação externa  
**Baseline de origem desta rodada:** `v0.9.1.0` corrigida/hotfixada  
**Repositório:** `https://github.com/henriT35/Controle-Motoristas.git`

> Leia este documento antes de alterar o projeto. Em seguida leia `docs/REGRAS_PARA_PROXIMO_AGENTE.md`, `docs/RANKING_V3.md`, `docs/VALIDACAO_ROM13.md`, `docs/REGULARIDADE.md`, `docs/RETENCOES_SSW.md`, `docs/PORTAL_MOTORISTA.md`, `docs/ROTINAS_SSW.md`, `docs/PERFORMANCE.md` e o QA da release.

## 1. Objetivo do sistema

Painel operacional/executivo para acompanhar motoristas, CT-es, romaneios, tentativas de entrega, ocorrências do SSW, comprovantes retidos, retiradas exatas, oportunidades regionais, recuperações, ranking explicável, Portal do Motorista, WhatsApp e automações SSW.

A unidade operacional principal é a **tentativa/romaneio**. Um mesmo CT-e pode possuir várias tentativas e motoristas diferentes ao longo do tempo.

## 2. Stack

- Python / Django server-rendered;
- SQLite no local/homologação simples;
- PostgreSQL na produção;
- Redis + Celery + Celery Beat na VPS;
- Playwright/Chromium no robô SSW opção 036;
- Node.js + Baileys no WhatsApp;
- Nginx + Gunicorn em Docker na VPS;
- Waitress + Cloudflare Quick Tunnel no Windows para acesso temporário sem domínio.

## 3. Parte congelada

`robot_ssw/` é homologado e **não pode ser alterado silenciosamente**.

Na v0.9.2.0 ele foi comparado integralmente com a v0.9.1.0 corrigida: **17/17 arquivos idênticos, 0 diferenças de caminho e 0 diferenças SHA-256**.

Pode alterar ao redor do core: UI, templates, models, services, cache, scheduler externo, bridge, fila, importação, ranking, Portal, mapa, WhatsApp Django, Docker e infraestrutura.

## 4. Nota Geral V3 — decisão vigente

Existe uma única Nota Geral de **0 a 100**.

Pesos padrão configuráveis:

- Gestão de Comprovantes: **50%**;
- Qualidade Operacional: **35%**;
- Regularidade: **15%**.

Produtividade bruta não aumenta a nota. CT-es, entregas, peso, toneladas, volume, valor de frete, clientes e romaneios são apenas estatísticas operacionais.

A comparação entre motoristas com 50 e 300 tentativas usa proporção, não contagem bruta.

## 5. Qualidade Operacional — ROM13

Código usado inicialmente: **ROM13 — ENTREGA PREJUDICADA PELO HORÁRIO**.

ROM13 **não penaliza automaticamente**.

Cada ROM13 cria um `DriverQualityEvent` ligado à tentativa/`DeliveryMovement` e ao motorista daquela tentativa, com estado inicial `PENDING`.

Decisão do coordenador:

- `DRIVER_RESPONSIBLE`: penaliza Qualidade; motivo visível obrigatório;
- `NOT_RESPONSIBLE`: neutro;
- `VERIFY`: neutro até decisão;
- evento pendente: neutro.

Fórmula:

`Qualidade = (tentativas - ROM13 validados como culpa) / tentativas × 100`.

Mesma tentativa + mesmo ROM13 importado várias vezes = um evento. Nova tentativa + novo ROM13 = nova avaliação; pode penalizar novamente o mesmo motorista ou um novo motorista se a culpa for validada.

ROM34 **não entra na Qualidade**.

## 6. Regularidade — 15%

Regularidade deixou de ser 100 fixo.

Conceito:

`ações obrigatórias cumpridas / ações obrigatórias avaliáveis × 100`.

Entram prospectivamente e, desde 01/09/2026, podem ser reconstruídas de forma determinística pela rota:

- Retiradas Exatas materializadas automaticamente quando o motorista esteve naquele cliente/parada com comprovante ativo, mesmo que ele não abra o Portal;
- obrigação de registrar ressalva/evidência quando aplicável após o marco de ativação v0.9.2.0.

Cumprida:

- RETIREI;
- AINDA NÃO LIBERADO + observação;
- NÃO FOI POSSÍVEL TENTAR + justificativa;
- ressalva obrigatória registrada.

Falha:

- ação obrigatória apresentada e encerrada sem nenhuma manifestação.

Neutro/fora do denominador:

- Ouro ignorado;
- dia sem ação obrigatória;
- ROM13/ROM34 como fatos de outro pilar;
- cliente não liberou quando o motorista registrou corretamente.

Há `driver_v3_regularity_window_days` configurável e `driver_v3_actions_activation_date` para impedir punição retroativa de fatos históricos que nunca foram apresentados ao motorista pelo Portal.

## 7. Gestão de Comprovantes — 50%

Regra conceitual principal: **idade do comprovante não é culpa automática do motorista**.

Um comprovante pode estar retido há muitos dias sem o motorista ter voltado ao cliente. O painel pode mostrar a idade para priorização da gestão, mas a nota só considera fatos atribuíveis/ações efetivamente executáveis.

`AINDA NÃO LIBERADO` corretamente informado é neutro e não reduz a nota.

Omissão de Retirada Exata pertence à Regularidade e não deve ser descontada novamente neste pilar.

Recuperação rejeitada pode produzir impacto de gestão; recuperação pendente não é bônus definitivo.

## 8. Retirada Exata e Ouro

### Retirada Exata

Ação obrigatória quando existe comprovante pendente no próprio cliente/parada da rota.

Respostas:

- `RETIREI`: exige evidência e validação;
- `AINDA NÃO LIBERADO`: observação obrigatória, neutro;
- `NÃO FOI POSSÍVEL TENTAR`: justificativa obrigatória, neutro/auditável.

A v0.9.2.0 persiste a oportunidade **quando ela é apresentada**, permitindo provar uma omissão real sem inferir retroativamente.

### Oportunidade de Ouro

É extra/regional e sempre opcional:

- ignorou = neutro;
- tentou = neutro;
- cliente não liberou = neutro;
- recuperou + coordenador aprovou = bônus maior configurável.

Ouro ignorado nunca reduz nenhum pilar.

## 9. Original driver x recovery driver

- `original_driver`: motorista da tentativa que originou a retenção;
- `original_manifest`: romaneio da tentativa que originou a retenção;
- `recovery_driver`: motorista que realmente recuperou.

Nunca sobrescrever origem ao recuperar. Resolução automática pelo SSW nunca inventa `recovery_driver`.

## 10. Retenção — ROM34 x estado atual CTRC

A v0.9.2.0 corrigiu a interpretação.

**ROM34 = origem/histórico da retenção.**  
**CTRC atual = estado consolidado atual do CT-e.**

Regras:

- ROM34 + CTRC atual 34 → `AGUARDANDO RETIRADA`;
- ROM34 + CTRC atual 1/ENTREGUE → `RECUPERADO` operacionalmente por SSW;
- ROM34 + 60/53/91/outro não conclusivo → `ACOMPANHANDO_SSW`;
- `VERIFICAR` fica reservado a ambiguidade estrutural real.

Resolução por SSW:

- `resolution_source=SSW`;
- não cria `recovery_driver`;
- não cria bônus;
- não depende de um horário técnico inferido.

## 11. Casos reais que motivaram a correção

### BNU046259-4

ROM34 histórico sem data/hora confiável, enquanto o CTRC atual está `1 ENTREGUE`. O sistema antigo podia inventar 12:00 e concluir erroneamente que a entrega das 11:02 ocorreu “antes” da retenção. Isso não pode mais acontecer.

### CWB055520-7

O SSW mostra correções/estornos de data e estado consolidado `1 ENTREGUE`. O relatório 036 não contém histórico completo suficiente para reconstruir toda a linha do tempo, portanto o estado consolidado atual governa a resolução operacional.

QA privado da v0.9.2.0: 12 relatórios reais, 27.126 linhas, ambos os casos passaram. Não publicar esses relatórios no Git.

## 12. Portal do Motorista — transparência

O Portal continua web por token individual, revogável/regenerável mediante aprovação quando necessário.

A área Ranking/Minha Avaliação deve responder: **“Por que estou nessa posição?”**

Exibe:

- Nota Geral;
- posição;
- quanto falta para o imediatamente acima;
- período e tentativas avaliadas;
- três pilares, pesos e contribuições;
- ROM13 negativos, neutros e pendentes;
- ações de Regularidade cumpridas/omitidas;
- bônus validados;
- histórico de snapshots;
- o que afetou a nota;
- o que o motorista pode fazer agora.

Regra de produto: **nenhuma redução de nota sem evento explicável**.

## 13. Central de Avaliações do coordenador

Existe fluxo para revisar ROM13 com:

- motorista/tentativa/romaneio/data/cliente/CT-e;
- responsabilidade / sem responsabilidade / verificar;
- motivo visível ao motorista;
- observação interna opcional;
- reabertura/reversão;
- histórico/auditoria;
- invalidação de cache/recalculo.

A Central também sinaliza Retiradas Exatas sem manifestação, obrigações de ressalva não cumpridas e recuperações pendentes.

## 14. Eventos/modelos v0.9.2.0

Principais novos registros:

- `DriverQualityEvent`;
- `DriverScoreSnapshot`;
- `ProofPickupOpportunity`;
- `ProofRetentionObligation`;
- campos de estado/resolução SSW em `RetainedProof`;
- configurações de Regularidade/ativação em `SystemSettings`.

Migrations versionadas:

- `apps/core/migrations/0003_v0_9_2_0_evaluation_settings.py`;
- `apps/drivers/migrations/0003_v0_9_2_0_quality_events.py`;
- `apps/proofs/migrations/0003_v0_9_2_0_opportunities_and_ssw_state.py`.

Não rodar `makemigrations` automaticamente em produção.

## 15. Reconciliação da base existente

Dry-run:

```powershell
python manage.py reconcile_retained_proofs --dry-run
```

Aplicação explícita após revisar o resumo:

```powershell
python manage.py reconcile_retained_proofs
```

Preserva origem, não inventa recuperador, registra auditoria e invalida cache.

## 16. Cache e performance

Mudanças relevantes invalidam cache operacional: importação SSW, ROM13 validado/reaberto, resposta de retirada, recuperação validada/rejeitada, reconciliação, alteração de configurações e fatos de avaliação.

Instrumentação usa prefixos `PERF`, incluindo Portal, ranking, quality events e reconciliação.

Não recalcular todo o histórico a cada request quando existir fato pré-processável/cacheável.

## 17. Scheduler / automação

Windows:

`EXECUTAR_LOCAL.bat` e `EXECUTAR_ONLINE.bat` mantêm o scheduler externo Django. O core do robô não mudou.

VPS:

- Celery Beat agenda;
- `robot-worker` executa fila `ssw`;
- somente um robô por vez;
- housekeeping diário da avaliação sincroniza eventos/obrigações, fecha oportunidades e fotografa notas.

## 18. WhatsApp

Fluxo oficial continua **Node.js + Baileys**. Não reintroduzir login por navegador/Playwright.

Sessão Baileys é persistente e nunca deve ir ao Git. Telefone BR mantém tentativa de resolução com/sem nono dígito.

## 19. VPS / GitHub

Arquitetura alvo:

- nginx;
- web Django/Gunicorn;
- PostgreSQL;
- Redis;
- Celery worker;
- Celery Beat;
- robot-worker SSW;
- whatsapp Baileys.

`restart: unless-stopped`.

Sem domínio inicialmente: `http://IP_PUBLICO_DA_VPS`.

Nunca versionar `.env`, credenciais, sessão Baileys, banco, `local_data`, logs, uploads reais, relatórios SSW privados, `node_modules` ou `.venv`.

## 20. Scripts/comandos importantes

Windows:

- `EXECUTAR_LOCAL.bat`;
- `EXECUTAR_ONLINE.bat`;
- `PARAR_LOCAL.bat`;
- `PARAR_ONLINE.bat`;
- `VERIFICAR_BUILD.bat`;
- `INSTALAR_BOT_WHATSAPP.bat`.

Django:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test
python manage.py reconcile_retained_proofs --dry-run
```

Git/VPS:

```text
git status
git add .
git commit -m "..."
git push

git pull
docker compose up -d --build
```

## 21. QA da v0.9.2.0

PASS neste ambiente:

- compileall;
- 14 scripts QA portáteis/estáticos;
- 221 arquivos Python no QA portátil;
- Node syntax;
- shell syntax;
- real retention QA com 12 relatórios/27.126 linhas;
- BNU046259-4;
- CWB055520-7;
- mock opção 036;
- `robot_ssw` integral 17/17 idêntico.

HOMOLOGAÇÃO EXTERNA PENDENTE:

- Django não está instalado neste ambiente, portanto `check`, `makemigrations --check` e `test` não rodaram;
- migrations reais SQLite/PostgreSQL;
- navegador/resoluções reais;
- SSW real;
- WhatsApp real;
- Docker/VPS real;
- benchmark HTTP cache frio/quente.

Consultar `docs/QA_RELEASE_V0_9_2_0.md`.

## 22. Decisões que NÃO devem ser revertidas

- tentativa/romaneio é a unidade operacional;
- ROM85 é evidência preferencial de saída;
- ROM34 é origem da retenção e não é Qualidade;
- CTRC atual entregue pode encerrar retenção sem inventar recuperação humana;
- código 13 pode encerrar a tentativa na lógica temporal já homologada;
- ROM13 só penaliza a Qualidade após validação humana;
- novo ROM13 em nova tentativa pode penalizar novamente;
- volume bruto não é nota;
- Ouro ignorado é neutro;
- “Ainda não liberado” corretamente informado é neutro;
- Regularidade mede ações obrigatórias, não produtividade;
- `original_driver` e `recovery_driver` são independentes;
- Baileys não volta para login via navegador;
- nenhum horário inferido pode se passar por evidência temporal real;
- nenhuma nota deve ser caixa-preta.

## 23. Procedimento para a próxima versão

1. partir da baseline completa v0.9.2.0;
2. copiar para árvore de trabalho;
3. ler docs e regras imutáveis;
4. não alterar `robot_ssw`;
5. implementar na cópia;
6. executar QA portátil e, quando disponível, Django/runtime;
7. remover caches/artefatos locais;
8. comparar `robot_ssw` byte a byte;
9. gerar patch somente do diff da baseline declarada;
10. aplicar o patch extraído sobre cópia limpa da baseline;
11. comparar caminhos e SHA-256 com a nova baseline;
12. atualizar VERSION/CHANGELOG/docs;
13. gerar ZIPs + SHA-256;
14. documentar claramente qualquer homologação externa pendente.


## Hotfix pós-release — nome de índice ProofPickupOpportunity

Na primeira execução real do `EXECUTAR_ONLINE.bat` no Windows, o Django detectou `models.E034` porque `proofs_opp_driver_date_kind_idx` tinha 31 caracteres. O nome foi corrigido para `proofs_opp_drv_date_kind_idx` no model, migration v0.9.2.0 e contratos de QA. Não houve mudança funcional, de dados ou em `robot_ssw/`. Reexecutar `EXECUTAR_ONLINE.bat` e confirmar que a etapa `Validando migrations versionadas` avança sem esse E034.

### Performance R2 — decisão arquitetural

O diagnóstico real mostrou Dashboard frio 17,15 s, dos quais apenas 0,42 s eram SQL; `ranking.movements` e `ranking.events` dominavam o tempo. O Dashboard quente já respondeu em 0,118 s.

Por isso `DriverScoreSnapshot` agora guarda uma fotografia completa de navegação. Em cache miss, o Ranking tenta o snapshot persistente antes de qualquer reconstrução histórica. O cálculo pesado é realizado em startup/pós-import/validação e protegido por lock para evitar cache stampede. `ImportRun` não invalida mais o ranking por simples atualização de status.

Retirada Exata/Regularidade é contabilizada por motorista + cliente/parada + data, agrupando todos os comprovantes da mesma visita. O histórico desde 01/09/2026 é materializado pela rota e não depende da abertura do Portal.
