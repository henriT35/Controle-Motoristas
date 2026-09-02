# Caderno de Bugs — V0.2.2

O Caderno de Bugs é uma funcionalidade **dentro do próprio Painel Motoristas**, destinada à homologação e acompanhamento das correções.

## Acesso

URL:

```text
/bugs/
```

O item **Caderno de Bugs** aparece na sidebar para usuários `is_staff`/administradores. As verificações também são feitas no backend; não é apenas ocultação visual.

## Registro

Cada bug pode guardar:

- tela;
- URL/caminho específico;
- título;
- prioridade P0/P1/P2/P3;
- status;
- descrição;
- resultado atual;
- resultado esperado;
- passos para reproduzir;
- print/anexo;
- navegador/ambiente;
- responsável;
- notas técnicas;
- correção aplicada;
- resultado do reteste;
- versão do sistema;
- usuário que registrou;
- datas de criação, atualização e resolução.

## Telas disponíveis

- Login;
- Dashboard Executivo;
- Operação de Hoje;
- Motoristas;
- Perfil do Motorista;
- Comprovantes Retidos;
- Clientes;
- Relatórios;
- Importações SSW;
- Histórico do Robô SSW;
- Configurações;
- Geral/Navegação;
- Backend/Banco/Regras.

## Prioridades

- **P0 — Bloqueador:** quebra, perda de dados ou operação impossível.
- **P1 — Crítico:** regra de negócio ou função principal incorreta.
- **P2 — Importante:** função incompleta, filtro ou indicador incorreto.
- **P3 — Visual/Polimento:** alinhamento, densidade, estilo e microinteração.

## Status

```text
Aberto
Em análise
Em correção
Aguardando reteste
Falhou no reteste
Corrigido
Fechado
```

## Evidências

Anexos aceitos:

```text
PNG, JPG, JPEG, WEBP, PDF, TXT, LOG
```

Limite: **8 MB por bug**.

No modo local os arquivos ficam em `media/bug_reports/`. Em produção, `MEDIA_ROOT` deve ser servido pelo servidor de mídia/infraestrutura adequada.

## Fluxo recomendado

```text
Registrar
→ Classificar
→ Reproduzir
→ Em análise
→ Em correção
→ Aguardando reteste
→ Corrigido
→ Fechado
```

Se o reteste falhar:

```text
Aguardando reteste
→ Falhou no reteste
→ Em correção
```

## Atalho contextual

Nas telas internas, usuários autorizados visualizam um botão flutuante **Registrar bug**. Ele abre `/bugs/` com a tela e o caminho atual pré-selecionados, reduzindo erro de classificação durante a homologação.

## Auditoria

Criação e atualização geram `AuditLog` com ações:

```text
BUG_CREATED
BUG_UPDATED
```

O Caderno não apaga automaticamente bugs corrigidos; o histórico é preservado.
