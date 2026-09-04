# Painel Motoristas v0.9.2.0

Painel web operacional/executivo para rotas, motoristas, CT-es, romaneios, ocorrências SSW, comprovantes retidos, retiradas, oportunidades regionais, ranking, Portal do Motorista e comunicação WhatsApp.

A v0.9.2.0 fecha a lógica da **Nota Geral V3 explicável** e corrige a interpretação dos comprovantes retidos pelo **estado consolidado atual do CTRC**, sem alterar o core homologado `robot_ssw/`.

## Stack

- Python / Django server-rendered;
- SQLite no modo local/homologação simples;
- PostgreSQL na VPS;
- Redis + Celery + Celery Beat;
- Playwright/Chromium no robô SSW 036;
- Node.js + Baileys para WhatsApp;
- Nginx + Gunicorn em Docker na VPS;
- Waitress + Cloudflare Quick Tunnel para modo online temporário no Windows.

## Nota Geral V3

Uma única nota de 0 a 100:

- **Gestão de Comprovantes — 50%**: mede como o motorista trata ações de comprovantes atribuíveis a ele; idade do documento é indicador de gestão, não culpa automática.
- **Qualidade Operacional — 35%**: mede a taxa proporcional de tentativas sem ROM13 confirmado manualmente como responsabilidade do motorista.
- **Regularidade — 15%**: mede ações obrigatórias cumpridas corretamente ÷ ações obrigatórias exigidas.

Produtividade bruta não aumenta a Nota Geral. Volumes operacionais continuam visíveis como estatísticas.

### ROM13

`13 — ENTREGA PREJUDICADA PELO HORÁRIO` gera evento **PENDENTE**, sem impacto. O coordenador decide:

- responsabilidade do motorista → impacta Qualidade;
- não foi responsabilidade → neutro;
- verificar → neutro até decisão.

Mesma tentativa + mesmo ROM13 = um evento. Nova tentativa + novo ROM13 = nova avaliação independente.

### ROM34 e comprovantes

`34 — MERCADORIA EM CONFERÊNCIA NO CLIENTE` é evidência da **origem da retenção**, não falha de Qualidade.

- CTRC atual `34` → retenção ativa;
- CTRC atual `1/ENTREGUE` → resolvido automaticamente pelo SSW, sem inventar quem recuperou e sem bônus;
- outro CTRC atual (`60`, `53`, `91` etc.) → `ACOMPANHANDO_SSW`, não é retirada obrigatória.

`original_driver` e `recovery_driver` são fatos independentes.

## Portal do Motorista

O Portal continua 100% web por token individual revogável. A área de Ranking/Minha Avaliação mostra:

- Nota Geral e posição;
- diferença para a posição imediatamente acima;
- os três pilares, pesos e contribuições;
- ROM13 que impactaram, foram neutros ou ainda estão em análise;
- Regularidade e omissões identificáveis;
- bônus validados e projeção das oportunidades;
- histórico de snapshots da nota;
- ações disponíveis agora.

Regra de produto: **nenhuma redução de nota sem um fato explicável**.

## Retirada Exata e Ouro

Retirada Exata possui três respostas:

- `RETIREI` → evidência + validação;
- `AINDA NÃO LIBERADO` → observação obrigatória, neutro;
- `NÃO FOI POSSÍVEL TENTAR` → justificativa obrigatória, neutro/auditável.

Se uma Retirada Exata foi realmente apresentada e a data operacional encerrou sem manifestação, vira omissão de **Regularidade**.

🏆 Oportunidade de Ouro é sempre opcional. Ignorar nunca penaliza; recuperação validada recebe bônus maior configurável.

## Executar no Windows

Local:

```bat
EXECUTAR_LOCAL.bat
```

Online temporário sem domínio:

```bat
EXECUTAR_ONLINE.bat
```

Parar:

```bat
PARAR_LOCAL.bat
PARAR_ONLINE.bat
```

Antes de homologar uma nova instalação, execute:

```bat
VERIFICAR_BUILD.bat
```

O boot **não cria migrations automaticamente**. Em ambiente Django válido, exige `makemigrations --check` e aplica apenas migrations versionadas.

## Reconciliação de comprovantes existentes

Primeiro faça dry-run:

```powershell
python manage.py reconcile_retained_proofs --dry-run
```

Depois, se o resultado estiver correto:

```powershell
python manage.py reconcile_retained_proofs
```

A reconciliação preserva `original_driver/original_manifest`, não inventa `recovery_driver` e registra auditoria.

## VPS

Arquitetura prevista em `docker compose`:

`nginx + web + postgres + redis + worker + beat + robot-worker + whatsapp`

Deploy típico:

```bash
git pull
docker compose up -d --build
```

Sem domínio inicialmente: `http://IP_PUBLICO_DA_VPS`.

## Segurança / Git

Nunca versionar:

- `.env` real;
- credenciais SSW;
- sessão Baileys;
- banco local/produção;
- `local_data` real;
- logs;
- uploads reais;
- `.venv`;
- `node_modules`;
- `__pycache__` / `.pyc`.

## Documentação principal

- `docs/RANKING_V3.md`
- `docs/AVALIACAO_V3_EXPLICAVEL.md`
- `docs/VALIDACAO_ROM13.md`
- `docs/REGULARIDADE.md`
- `docs/RETENCOES_SSW.md`
- `docs/PORTAL_MOTORISTA.md`
- `docs/PERFORMANCE.md`
- `docs/ROTINAS_SSW.md`
- `docs/VPS_HOSTINGER_GITHUB.md`
- `docs/QA_RELEASE_V0_9_2_0.md`
- `docs/REGRAS_PARA_PROXIMO_AGENTE.md`
- `CONTEXTO_MESTRE_PROXIMO_CHAT_PAINEL_MOTORISTAS_v0_9_2_0.md`

## Parte congelada

`robot_ssw/` é core homologado. Não alterar para corrigir UI, ranking, banco, Portal, WhatsApp, scheduler, retenção, cache ou performance.


## VPS — v0.9.2.0 R3

A preparação recomendada para Hostinger/VPS sem domínio está em `LEIA_PRIMEIRO_VPS_R3.md` e `docs/VPS_HOSTINGER_GITHUB.md`. O arquivo ativo do Docker Compose é `.env` (copie de `.env.vps.example`). Use `bash deploy/vps/preflight.sh` antes do primeiro deploy.
