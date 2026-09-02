# Relatório de Correções — V0.2.1

Data de fechamento: 31/08/2026  
Base: V0.2.0 sem Docker  
Objetivo: Rodada 01 de bugs, com foco em data operacional de rotas, importação temporal e múltiplos meses.

## Correções principais

### Data operacional da rota
Foi criada uma camada central para separar **data de emissão do romaneio** de **data operacional da rota**. `SAIDA PARA ENTREGA` (código 85) passa a ser a fonte principal. Isso afeta Operação de Hoje, Dashboard, Motoristas, Clientes e Relatórios.

### Histórico preservado após ENTREGUE
Uma rota continua pertencendo ao dia em que saiu para entrega mesmo que depois o CT-e receba `ENTREGUE` ou outra ocorrência.

### Importação temporal
O importador foi endurecido para arquivos sobrepostos/fora de ordem:
- histórico não deve regredir status atual;
- romaneio BAIXADO não volta a PENDENTE;
- ocorrências antigas são preservadas;
- retenção histórica mais antiga pode corrigir a origem/data do comprovante.

### Identidades e duplicidade
- CNPJ/CPF/CEP normalizados sem máscara para comparação.
- Cliente com mesmo CNPJ e variação de pontuação no nome não deve duplicar.
- Mesmo comprovante não é contado duas vezes nas oportunidades gerais.

### Comprovantes
- recuperação rejeita data futura;
- recuperação rejeita data anterior à retenção;
- criticidade default é estritamente `> 15 dias`;
- motorista original e motorista de recuperação continuam separados.

### Vários meses SSW
Foi implementado:
- `IMPORTAR_LOTE_SSW.bat`;
- `manage.py import_ssw_batch`;
- seleção múltipla em `/ssw/importacoes/`.

Arquivos são ordenados pelo período detectado. Uma falha não apaga importações concluídas anteriormente no lote.

### Interface/responsividade
Sidebar/menu recebeu comportamento mobile/drawer e a tela Operação de Hoje foi reforçada com indicadores e cobertura regional baseados na data operacional.

## Testes adicionados/expandidos
A suíte no código cobre cenários de:
- romaneio D-1 + saída D0;
- emissão e saída no mesmo dia;
- saída seguida de entrega;
- saída sem data (fallback);
- retenção e recuperação;
- limite 15/16 dias;
- regressão de status por arquivo histórico;
- duplicidade de cliente por pontuação;
- retenção mais antiga importada depois;
- oportunidade única.

## Validações executadas no empacotamento
- compilação estática Python;
- leitura do parser puro no arquivo SSW de homologação;
- busca por artefatos locais proibidos antes de ZIP;
- atualização de referências de versão/captura.

## Validação não executada aqui
O ambiente de geração não possui Django instalado. Assim, não foi executado:

```text
manage.py check
manage.py test
Playwright contra o Django real
```

Essas validações estão empacotadas para o Windows por `TESTAR_SISTEMA.bat` e `CAPTURAR_TELAS.bat`.

## Banco
- Homologação local rápida: SQLite.
- Banco oficial/alvo: PostgreSQL.

## Dependência externa
O robô Playwright para autenticação/navegação no SSW real permanece pendente, por depender de credenciais e interface externa.

## Próxima ação recomendada
1. executar V0.2.1 no Windows;
2. importar um arquivo e um lote mensal;
3. rodar `TESTAR_SISTEMA.bat`;
4. rodar `CAPTURAR_TELAS.bat`;
5. enviar bugs/evidências restantes para Rodada 02.
