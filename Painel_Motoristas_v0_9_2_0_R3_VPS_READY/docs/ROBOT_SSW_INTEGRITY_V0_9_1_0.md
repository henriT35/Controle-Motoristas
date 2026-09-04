# Integridade `robot_ssw` — v0.9.1.0

## Resultado

- Origem efetivamente disponível para comparação: árvore de continuidade baseada na v0.8.2.0 com handoff v0.9.0.0.
- Baseline funcional oficial v0.9.0.0: **não foi fornecida**; portanto não é correto afirmar comparação direta com um ZIP oficial inexistente no material recebido.
- Arquivos de projeto em `robot_ssw/` (sem caches Python gerados pelo QA): **17**.
- Diferenças de caminho: **0**.
- Diferenças de SHA-256/conteúdo: **0**.
- Resultado: **100%% idêntico à origem efetivamente fornecida**.

## Arquivos e SHA-256

| Arquivo | SHA-256 | Comparação |
|---|---|---|
| `.env.example` | `d73bfcb896537734d3ebdab1348ce992bc21cf578b53bd5eedd83a6590fc3570` | MATCH |
| `.gitignore` | `34c9928fe7cd97c0d41467b017783ec9be2b063289c0d93b7ae92e104befa515` | MATCH |
| `HOMOLOGATED_CORE.sha256` | `7b7d58357603c97e8abf02663608939436ddaed7c1d33ec144395f415a607fbb` | MATCH |
| `P13_BUILD.txt` | `febbaa136603e5b27f73e1097bb7b1f734322413b7ca1e0a7526163cd543864d` | MATCH |
| `README_CORE_HOMOLOGADO.md` | `f60d7cd42f5a50f007e6c479608c7eaa16ce5a70cbffb6877fd5f883b868e931` | MATCH |
| `contract_test.py` | `0e24f952d82e145a66b3d630d48cbb70fdda8c5507f5451c93ff98abc6ff579e` | MATCH |
| `diagnostics_real.py` | `097cb0cd3ac017a1a6fd9f1513bd1310c43fbc6c2601b5f17ea373f671836cee` | MATCH |
| `integration_example.py` | `495549b86357fcaea3cdf3bf1255d4d139eda33b3e5446105c255ec6d379b0e4` | MATCH |
| `mock_contract_test.py` | `e2a6be56a75a88b83c25d38c69f711f2916f47798e13f208fa1d33d8d217bbf6` | MATCH |
| `requirements.txt` | `9f234ce171a0497bcd04466031b130d29205f17c3323042649c8146f612a58ed` | MATCH |
| `robot_ssw/__init__.py` | `a135fed7a45224a84eb046a420017269b27d01ce7c5407b26e647918341895f4` | MATCH |
| `robot_ssw/cli.py` | `d767b5e5ee0759c865eca30b7672d64704b4f651b7cb691b380f1838c9c07afc` | MATCH |
| `robot_ssw/config.py` | `ad3e67d239522484aef3694ed49c76f253d4fe11ba1f64c29421bb16631813fe` | MATCH |
| `robot_ssw/io_utils.py` | `e7e4c2887288a0b3c3cec64718eb06df1fefc7394d5f4d393acfb7143c5da66e` | MATCH |
| `robot_ssw/models.py` | `b65db540795898942ec01e93c973391c40f3bc4571b95213e5e041381984f68b` | MATCH |
| `robot_ssw/worker.py` | `ba8c21d9a7a38666712bbfba6e18005c38405682a52632403883762db46c341e` | MATCH |
| `run_robot.py` | `e77db76fe8b41b21e8dd23ec294bd0383c3734b062678fa5e333d0a75b366392` | MATCH |

## Regra para a próxima versão

Antes de empacotar qualquer release, remover `__pycache__`/`.pyc` e repetir comparação integral de caminhos + SHA-256. UI, scheduler externo, fila, banco, importação, ranking, mapa, WhatsApp Django, Portal, Docker e performance devem continuar evoluindo fora deste core.
