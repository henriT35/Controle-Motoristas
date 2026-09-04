# Web Performance — v0.3.0

## Operação de Hoje
Antes, cada romaneio buscava novamente todos os comprovantes abertos. O serviço agora:

1. carrega todos os movimentos das rotas do dia uma vez;
2. carrega os comprovantes abertos uma vez;
3. indexa movimentos por cliente e CNPJ;
4. resolve match exato/regional em memória;
5. calcula entregas de todos os cards com uma única consulta de ocorrências;
6. reutiliza os movimentos carregados para KPIs e bairros.

## Perfil do Motorista
A evolução de 12 meses deixou de executar 12 consultas operacionais independentes. Agora uma janela única de 12 meses é carregada e distribuída por mês usando o mapa de data operacional.

## Clientes
Comprovantes recuperados do período usam `Prefetch(..., to_attr=...)`. Não é mais executado `client.retained_proofs.filter(...)` dentro do loop.

## Comprovantes
Os KPIs de aguardando/disponível/recuperado/crítico/valor foram consolidados em uma única agregação SQL.

## Histórico SSW
Duração média passou de iteração sobre todas as execuções para `AVG` no banco.

## Caderno de Bugs
Listagem agora é paginada em 50 registros. Detalhes continuam sob demanda.

## Configuração
`SystemSettings.load()` usa cache local de 60 segundos e invalidação imediata em `save/delete`. Não há nova dependência Redis.

## Contexto global
Última sincronização SSW recebe cache curto de 15 segundos para evitar consulta repetida em todo render de cabeçalho.

## ECharts
Instâncias são registradas em um único registry e compartilham um listener de resize com debounce. O polling da importação foi ajustado para 1,2 s.

## Benchmark

```bash
python manage.py benchmark_system --repeat 3
```

O comando mostra melhor/média em milissegundos e quantidade de queries por página crítica.
