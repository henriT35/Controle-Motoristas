# QA — Lógica Operacional v0.8.1.0

## Fonte
Lote real fornecido em 02/09/2026 com 10 execuções do relatório SSW 036 e 25.145 linhas. Os arquivos reais não são incorporados ao repositório/pacote de produção.

## Regressões reproduzidas

1. **CTRC34 repetido em várias tentativas**: 15 CT-es mudam de romaneio/motorista quando ROM34 passa a ter precedência. Em 10 casos observados na análise, o motorista também muda.
2. **Estado pós-retenção ambíguo**: 12 CT-es terminam em código diferente de retenção/entrega; exemplos observados: 60 DOCUMENTOS, 53 OCORRENCIA DE MERCADORIA C/ AVARIA e 91 MERCADORIA EM INDENIZACAO.
3. **Código 13 e nova tentativa**: 5 CT-es do snapshot recente reproduzem uma tentativa antiga encerrada por `ENTREGA PREJUDICADA PELO HORARIO` seguida de nova rota, inclusive com troca de motorista.
4. **DATA OCORR ROM vazia**: relatórios antigos apresentam grande volume de fatos ROM sem data. A reconstrução só aceita casamento ROM↔CTRC do mesmo fato quando existe uma única tentativa candidata e uma única data CTRC; conflitos permanecem não confirmados.

## Regras congeladas nesta versão
- ROM = fato da tentativa/romaneio.
- CTRC = estado consolidado do CT-e.
- ROM34 vence CTRC34 para origem da retenção.
- ROM13 encerra a tentativa, não o CT-e.
- CTRC85 ao vivo seleciona no máximo uma tentativa elegível por CT-e.
- Código não conclusivo após retenção => `VERIFICAR`.
- Só entrega comprovada pode recuperar automaticamente.
- Emissão/importação não criam data operacional histórica.

## Limites do QA executado neste ambiente
Foi executada validação sintática de todos os arquivos Python e uma reprodução independente das regras sobre os 10 relatórios reais. O servidor Django completo não foi executado neste ambiente porque as dependências Django não estão instaladas localmente. A suíte `django.test` foi ampliada no pacote para ser executada no ambiente Windows/VPS com as dependências do projeto.
