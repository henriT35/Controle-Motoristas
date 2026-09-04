# Relatório Final — v0.8.0.0

## Objetivo

Transformar a baseline local em um produto pronto para GitHub/Hostinger VPS, mantendo o robô SSW na mesma VPS, adicionando agendamento automático configurável e melhorando o envio WhatsApp para os motoristas.

## Decisões

- Deploy por Docker Compose e atualização por `git pull`.
- Sem domínio na primeira etapa: Nginx publica porta 80 pelo IP da VPS.
- PostgreSQL, Redis, Django, scheduler, robô SSW e Baileys ficam na mesma VPS em serviços independentes.
- `robot_ssw` não foi alterado; Linux é tratado pela imagem/entrypoint.
- Scheduler acorda a cada minuto e respeita um intervalo persistente em arquivo compartilhado, evitando migration apenas para essa configuração operacional.
- WhatsApp testa JID brasileiro com/sem 9 e só envia mensagens explicitamente criadas pelo Painel.

## Fluxo SSW

`Celery Beat → smart_scheduler → queue_import/lock → fila ssw → robot-worker → watchdog → robot_ssw 036 → Import Engine → PostgreSQL`.

O botão **Atualizar agora** entra no mesmo fluxo, portanto não cria uma segunda arquitetura de execução.

## Fluxo WhatsApp

`Central → gerar lote → WhatsAppMessage(PENDING) → Baileys → onWhatsApp(com/sem 9) → sendMessage → resultado → SENT/FAILED`.

## Persistência na VPS

Volumes nomeados preservam banco, Redis, `local_data`, media e inbox/importações. A sessão Baileys permanece dentro de `local_data/whatsapp/baileys_auth` e não é versionada no GitHub.

## Limitação deliberada

O primeiro deploy sem domínio é HTTP. Isso atende ao requisito de publicação direta pelo IP, mas não oferece sigilo de transporte para tokens/credenciais de sessão do navegador. Endurecimento HTTPS deve ser planejado antes de exposição ampla fora do ambiente controlado.
