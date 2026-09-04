# HANDOFF MESTRE — PAINEL MOTORISTAS

**Data do handoff:** 03/09/2026  
**Última baseline funcional empacotada:** `v0.8.2.0`  
**Versão-alvo da grande rodada em andamento:** `v0.9.0.0`  
**Repositório GitHub:** `https://github.com/henriT35/Controle-Motoristas.git`

> Este documento é a fonte de continuidade para o próximo chat/agente. Antes de alterar o projeto, leia este arquivo, `REGRAS_IMUTAVEIS.md`, `PROCESSO_DE_ATUALIZACAO.md`, `PROMPT_IMPLEMENTACAO_V0_9_0_0.txt` e a documentação do robô SSW.

## 1. O que é o projeto

Painel web operacional/executivo para acompanhar motoristas, romaneios, CT-es, ocorrências do SSW, comprovantes retidos, oportunidades de retirada, recuperação de comprovantes, clientes, mapa operacional, WhatsApp e automações de sincronização.

Stack atual:

- Python / Django server-rendered;
- SQLite para homologação/local simples;
- PostgreSQL como alvo de produção;
- Redis + Celery/Celery Beat na VPS;
- Playwright/Chromium para o robô SSW 036;
- Node.js + Baileys para WhatsApp;
- Nginx/Gunicorn em Docker na VPS;
- Windows PowerShell/Waitress + Cloudflare Quick Tunnel para execução local/online temporária.

## 2. Baseline e regra de versionamento

A versão funcional mais recente consolidada antes desta rodada é a **v0.8.2.0**. A v0.9.0.0 é uma rodada maior ainda em implementação/homologação. Não promover uma v0.9 incompleta para produção só porque os arquivos compilaram.

Fluxo correto:

1. partir sempre de uma baseline completa;
2. criar cópia de trabalho;
3. alterar a cópia;
4. executar QA possível;
5. gerar PATCH somente com diferenças em relação à baseline declarada;
6. aplicar o PATCH em uma cópia limpa da baseline;
7. comparar resultado;
8. só então gerar nova baseline completa e SHA-256.

## 3. O que NÃO pode ser alterado silenciosamente

### `robot_ssw`

O core do robô SSW é congelado/homologado. Correções de scheduler, fila, bridge, importação, dashboard, WhatsApp, mapa e Portal devem ser feitas fora dele.

Sempre comparar o diretório `robot_ssw` byte a byte com a baseline de origem antes de empacotar uma nova versão. Se for inevitável alterar o core, documentar motivo e executar re-homologação ponta a ponta da opção 036.

### Regras temporais

Não usar:

- data de importação como data da rota;
- data de emissão como prova única da execução;
- CTRC consolidado para promover todos os romaneios históricos do CT-e.

A tentativa/romaneio é a unidade operacional. Um CT-e pode ter várias tentativas, em romaneios e motoristas diferentes.

## 4. Regras temporais e de retenção já confirmadas

- Ocorrência ROM `85 — SAIDA PARA ENTREGA`: melhor evidência de execução da tentativa.
- Sem ROM85 datado, outro fato ROM datado pode inferir a data operacional.
- Relatórios antigos sem `DATA OCORR ROM` podem usar reconstrução histórica somente quando existe casamento seguro ROM↔CTRC do mesmo fato e sem ambiguidade entre tentativas.
- Ocorrência ROM `13 — ENTREGA PREJUDICADA PELO HORÁRIO`: encerra aquela tentativa. Nova saída pode usar outro romaneio e outro motorista. A tentativa antiga não pode reaparecer como rota de hoje.
- Ocorrência ROM `34 — MERCADORIA EM CONFERÊNCIA NO CLIENTE`: evidência principal da origem da retenção.
- CTRC34 é consolidado e só pode ser fallback quando não existe evidência ROM34 adequada.
- `original_driver` e `original_manifest` devem apontar para a tentativa que realmente originou a retenção.
- Status posterior ambíguo, como `60 - DOCUMENTOS`, `53 - AVARIA`, `91 - INDENIZAÇÃO`, não deve ser interpretado automaticamente como comprovante recuperado. Estado adequado: **VERIFICAR**, salvo evidência conclusiva.
- `original_driver` e `recovery_driver` são fatos independentes; nunca sobrescrever origem ao registrar recuperação.

## 5. Robô SSW / Opção 036

O robô consulta **Consulta e Reimpressão de Romaneios — opção 036**.

Parâmetros operacionais conhecidos:

- Unidade: `BEL`;
- Excel: `S`;
- período fornecido pelo programa/scheduler;
- o relatório é baixado e importado pelo Painel.

A v0.8.2.0 acrescentou scheduler real no Windows. `EXECUTAR_LOCAL.bat` e `EXECUTAR_ONLINE.bat` iniciam também `manage.py run_ssw_scheduler --poll-seconds 30`.

Na VPS, Celery Beat consulta a agenda e o `robot-worker` dedicado executa jobs da fila `ssw`. Apenas um job SSW deve operar por vez.

## 6. Rotinas SSW — direção da v0.9

A interface precisa ser simplificada para uma **Central de Rotinas** única.

Cada rotina deve ter:

- nome;
- ativa/inativa;
- tipo de período;
- período efetivo;
- frequência;
- janela diária;
- próxima execução;
- último resultado;
- status;
- ações Executar agora / Editar / Pausar / Excluir.

Tipos essenciais:

- **Janela recente:** hoje, últimos 2, 3, 7 dias etc.;
- **Período fixo:** exemplo 01/01/2026–31/12/2026, limitado à data atual enquanto o fim estiver no futuro.

Bug visual conhecido: o modal/formulário atual pode abrir deslocado/por baixo da sidebar em resolução menor. Referência em `docs/referencias_visuais_v0_9/bug_modal_rotinas_sidebar.png`.

## 7. WhatsApp

Fluxo atual oficial: **Node.js + Baileys**. Não voltar para login por Chrome/Edge/Playwright/CDP.

Sessão persistente: `local_data/whatsapp/baileys_auth/` e volume persistente na VPS.

Telefone brasileiro: o bridge deve testar/resolver variações com e sem o nono dígito quando necessário, especialmente casos DDD 91.

Direção da v0.9:

- unificar motoristas da operação, cadastros e “requer atenção” numa única lista;
- cada motorista recebe badges e ações no mesmo card/linha;
- manter “Gerar e enviar para todos”;
- permitir editar telefone;
- tela de QR deve virar um único card compacto com status + QR + instruções + ações.

## 8. Portal Web do Motorista

Tudo é web; não criar aplicativo Android/iOS.

Acesso por token individual, revogável/regenerável. O motorista deve poder solicitar novo acesso, mas o pedido não pode gerar automaticamente novo token sem validação do coordenador.

Objetivo v0.9 do Portal:

- operação;
- comprovantes;
- oportunidades;
- ranking;
- perfil;
- foto da ressalva quando comprovante fica retido;
- foto/PDF de recuperação;
- “Ainda não liberado” sem penalização;
- “Não foi possível tentar” com justificativa/auditoria;
- oportunidade regional (“Oportunidade de Ouro”) sempre opcional e nunca penalizada quando ignorada.

## 9. Retirada exata x oportunidade de ouro

### Retirada exata

Existe comprovante no próprio cliente/parada da rota.

- recuperou + coordenador validou → bônus padrão;
- cliente informou “ainda não liberado” → neutro;
- não conseguiu tentar + justificativa → auditável, sem penalização automática forte;
- ignorou oportunidade exata sem qualquer ação/justificativa → pode haver impacto leve configurável.

### Oportunidade de ouro

Comprovante próximo da região/caminho, mas não é obrigação direta da parada.

- não tentou → neutro;
- tentou e não conseguiu → neutro;
- recuperou + validado → bônus maior;
- nunca penalizar por não aproveitar oportunidade regional.

## 10. Ranking / avaliação — decisão de produto mais recente

Produtividade bruta **não deve entrar diretamente na nota** porque os motoristas usam veículos/rotas/cargas diferentes.

Quantidade absoluta de CT-es, peso, frete e volume continuam como estatísticas operacionais, não como qualidade.

Experiência principal deve mostrar **uma Nota Geral (0–100)**. Componentes internos propostos para V3:

- Gestão de comprovantes: 50%;
- Qualidade operacional: 35%;
- Regularidade: 15%.

Pesos e bônus precisam ser configuráveis/calibráveis. Não hardcodar valores de simulação como regra definitiva.

Não penalizar várias vezes o mesmo evento. Exemplo: código 13 não pode derrubar três componentes simultaneamente pelo mesmo fato.

Motorista deve ver:

- posição;
- nota;
- quanto falta para posição imediatamente acima;
- impacto projetado de cada oportunidade;
- posição projetada considerando o ranking atual;
- histórico/conquistas;
- informação explícita de que “Ainda não liberado” não penalizou.

Prêmio do Top 3 é apenas informação/configuração do sistema. A recompensa real é decisão da gestão fora do software.

Referências visuais:

- `portal_motorista_ranking_oportunidades.png`;
- `ranking_admin_incentivos.png`.

## 11. Performance

Problema real relatado: Operação → Dashboard pode levar **mais de 10 segundos** em período anual.

Não mascarar com spinner. Atacar processamento real:

- profiling por etapa;
- N+1;
- `select_related`/`prefetch_related`;
- agregações no banco;
- índices;
- evitar reconstruir mapa temporal várias vezes;
- memoização por request;
- cache por período;
- Redis na VPS e LocMem local;
- invalidação depois de importações/alterações;
- pré-processamento após SSW;
- lazy loading do gráfico/séries pesadas;
- paginação.

Não prometer tempo exato sem medir no banco real.

## 12. Dashboard / gráfico

O gráfico Evolução Operacional precisa suportar períodos longos:

- ampliar;
- ESC para fechar;
- zoom;
- pan/navegação;
- slider/range;
- “Todo período”;
- tooltip;
- clique do dia continua abrindo Operação daquele dia;
- não eliminar dados silenciosamente.

## 13. Operação de Hoje

Nos cards de cada motorista/romaneio, exibir diretamente os dois números:

- retiradas exatas;
- oportunidades regionais/de ouro.

Ambos podem existir ao mesmo tempo e ambos devem ser clicáveis.

## 14. Mapa operacional

Problema confirmado em Marituba/Abaetetuba: resultado de Nominatim pode devolver o polígono do município e o sistema aceitar como se fosse bairro.

Regras:

- município e bairro são entidades diferentes;
- nunca pintar município inteiro como bairro;
- validar tipo/nível/endereço da feature retornada;
- falha de cache não pode ser eterna;
- permitir retry;
- remover limite artificial de 25 bairros;
- normalizar aliases (`ALMIR GABRIEL/ALMIR GRABRIEL`, `PARQUE VERDE/PARK VERDE` etc.);
- valores como ZONA RURAL, nome do próprio município ou estabelecimento não devem gerar polígono falso;
- quando não houver geometria confiável, usar lista/marker/fallback textual e continuar funcionando.

## 15. Deploy alvo — GitHub → Hostinger VPS

Repositório: `https://github.com/henriT35/Controle-Motoristas.git`

Arquitetura alvo:

- nginx;
- web Django/Gunicorn;
- PostgreSQL;
- Redis;
- Celery worker;
- Celery Beat;
- robot-worker SSW/Playwright;
- whatsapp Node/Baileys.

Sem domínio inicialmente: `http://IP_PUBLICO_DA_VPS`.

Boot automático: `restart: unless-stopped`.

Volumes persistentes para banco, Redis, `local_data`, media e imports.

Nunca subir ao Git:

- `.env` / `.env.local` / `.env.vps`;
- senha/token/chave;
- credenciais SSW;
- sessão Baileys;
- banco SQLite/PostgreSQL;
- logs reais;
- uploads/media reais;
- `node_modules`;
- `.venv`.

## 16. Como iniciar no Windows

Local:

`EXECUTAR_LOCAL.bat`

Online temporário sem domínio:

`EXECUTAR_ONLINE.bat`

Parar:

`PARAR_LOCAL.bat` / `PARAR_ONLINE.bat`

Logs importantes:

- `local_data/logs/server.err.log`;
- `local_data/logs/server.out.log`;
- `local_data/logs/scheduler.err.log`;
- `local_data/logs/scheduler.out.log`;
- logs do SSW/bridge já existentes no projeto.

WhatsApp:

`INSTALAR_BOT_WHATSAPP.bat` uma vez; depois gerenciar pela Central WhatsApp.

## 17. Como atualizar pelo Git

PC de desenvolvimento:

```powershell
git status
git add .
git commit -m "descricao da versao"
git push
```

VPS:

```bash
git pull
docker compose up -d --build
```

Antes de `git add .`, conferir obrigatoriamente se nenhum segredo/local_data/media/banco/sessão entrou no staging.

## 18. QA mínimo antes de qualquer nova baseline

- compilar todos os `.py`;
- validar sintaxe JS;
- `manage.py check` quando Django estiver disponível;
- testes Django quando ambiente permitir;
- regressão dos imports reais;
- validação visual em resoluções menores;
- patch aplicado sobre cópia limpa;
- comparação byte a byte de `robot_ssw`;
- SHA-256 dos pacotes;
- documentar exatamente o que NÃO foi testado.

## 19. Dados reais de regressão

Foi enviado um ZIP com **10 relatórios SSW reais** cobrindo janeiro até 02/09/2026. Esses arquivos foram usados para descobrir bugs de temporalidade, retenção e tentativa. O arquivo precisa ser mantido como material de QA privado/local e não deve ser publicado no GitHub se contiver dados operacionais reais.

Principais achados já discutidos:

- ROM34 x CTRC34 pode atribuir retenção a romaneio/motorista errado;
- relatórios antigos têm `DATA OCORR ROM` vazia em grande volume;
- código 13 seguido de nova tentativa pode gerar duplicidade de rota se CTRC85 for aplicado a todos os romaneios;
- status 60/53/91 pós-retenção é ambíguo e exige VERIFICAR.

## 20. Prioridade para o próximo chat

1. Ler toda a documentação deste handoff.
2. Confirmar a baseline real antes de modificar arquivos.
3. Não alterar `robot_ssw`.
4. Continuar a implementação da v0.9.0.0 usando `PROMPT_IMPLEMENTACAO_V0_9_0_0.txt` como checklist.
5. Priorizar performance + Portal/ranking/provas + UX unificada.
6. Gerar release somente após patch dry-run + QA + hashes.
