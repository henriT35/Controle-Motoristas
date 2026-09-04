# Patch 0.2.2-p7 — Instalador e autodetecção do Robô SSW

## Diagnóstico que motivou o patch
O diagnóstico do p6 mostrava corretamente:
- Adapter do Painel: SIM
- Robô real detectado: NÃO
- Pronto para executar: NÃO

Isso significa que o bridge do Painel estava instalado, porém os arquivos do robô real ainda não estavam disponíveis dentro de `robot_ssw`.

Também havia aviso `Invalid line: ﻿DJANGO_DEBUG=1`, causado por BOM UTF-8 no início do `.env.local`.

## Alterações
- `INSTALAR_ROBO_SSW.bat`: recebe um ZIP/pasta local do robô e instala dentro de `robot_ssw`.
- backup automático do conteúdo anterior do robô em `local_data/robot_backups/`.
- preservação de `painel_adapter.py` e `credenciais.local.json`.
- auto-descoberta de funções compatíveis também em subpastas e arquivos com nomes não convencionais.
- novo modo `painel_adapter.py --discover-only` para diagnosticar o robô sem exigir login e sem abrir navegador.
- `ssw_robot_doctor` passa a mostrar o arquivo/função efetivamente encontrado.
- `.env.local` lido com `utf-8-sig`, aceitando arquivos com BOM sem gerar aviso.
- `CORRIGIR_ENV_LOCAL.bat` para normalizar o arquivo existente para UTF-8 sem BOM.

## Funções aceitas pelo contrato
- `executar_tarefa`
- `buscar_relatorio`
- `executar`
- `run_task`
- `run`

A função pode receber o objeto `task`, parâmetros nomeados ou `**kwargs` conforme o adapter.

## Uso
1. Aplicar o patch.
2. Executar `INSTALAR_ROBO_SSW.bat` e selecionar o ZIP original do robô.
3. Executar `CONFIGURAR_CREDENCIAIS_SSW.bat` se necessário.
4. Executar `TESTAR_INTEGRACAO_ROBO_SSW.bat`.
5. Somente solicitar uma importação no Painel quando aparecer `Pronto para executar: SIM`.

## Observação
O instalador não altera banco, uploads ou Caderno de Bugs. Credenciais locais existentes são preservadas.
