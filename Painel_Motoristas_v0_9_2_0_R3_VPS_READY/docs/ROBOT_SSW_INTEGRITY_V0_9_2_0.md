# Integridade `robot_ssw` — v0.9.2.0

## Resultado

- Baseline comparada: **v0.9.1.0 corrigida**.
- Arquivos considerados após remover caches Python: **17**.
- Diferenças de caminho: **0**.
- Diferenças de SHA-256/conteúdo: **0**.
- Resultado: **100% idêntico byte a byte à baseline v0.9.1.0 corrigida**.
- Nenhuma implementação da v0.9.2.0 foi feita dentro de `robot_ssw/`.

## Arquivos e SHA-256

| Arquivo | SHA-256 |
|---|---|
| `.env.example` | `d73bfcb896537734d3ebdab1348ce992bc21cf578b53bd5eedd83a6590fc3570` |
| `.gitignore` | `34c9928fe7cd97c0d41467b017783ec9be2b063289c0d93b7ae92e104befa515` |
| `HOMOLOGATED_CORE.sha256` | `7b7d58357603c97e8abf02663608939436ddaed7c1d33ec144395f415a607fbb` |
| `P13_BUILD.txt` | `febbaa136603e5b27f73e1097bb7b1f734322413b7ca1e0a7526163cd543864d` |
| `README_CORE_HOMOLOGADO.md` | `f60d7cd42f5a50f007e6c479608c7eaa16ce5a70cbffb6877fd5f883b868e931` |
| `contract_test.py` | `0e24f952d82e145a66b3d630d48cbb70fdda8c5507f5451c93ff98abc6ff579e` |
| `diagnostics_real.py` | `097cb0cd3ac017a1a6fd9f1513bd1310c43fbc6c2601b5f17ea373f671836cee` |
| `integration_example.py` | `495549b86357fcaea3cdf3bf1255d4d139eda33b3e5446105c255ec6d379b0e4` |
| `mock_contract_test.py` | `e2a6be56a75a88b83c25d38c69f711f2916f47798e13f208fa1d33d8d217bbf6` |
| `requirements.txt` | `9f234ce171a0497bcd04466031b130d29205f17c3323042649c8146f612a58ed` |
| `robot_ssw/__init__.py` | `a135fed7a45224a84eb046a420017269b27d01ce7c5407b26e647918341895f4` |
| `robot_ssw/cli.py` | `d767b5e5ee0759c865eca30b7672d64704b4f651b7cb691b380f1838c9c07afc` |
| `robot_ssw/config.py` | `ad3e67d239522484aef3694ed49c76f253d4fe11ba1f64c29421bb16631813fe` |
| `robot_ssw/io_utils.py` | `e7e4c2887288a0b3c3cec64718eb06df1fefc7394d5f4d393acfb7143c5da66e` |
| `robot_ssw/models.py` | `b65db540795898942ec01e93c973391c40f3bc4571b95213e5e041381984f68b` |
| `robot_ssw/worker.py` | `ba8c21d9a7a38666712bbfba6e18005c38405682a52632403883762db46c341e` |
| `run_robot.py` | `e77db76fe8b41b21e8dd23ec294bd0383c3734b062678fa5e333d0a75b366392` |

## Regra imutável

`robot_ssw/` continua congelado. UI, scheduler externo, fila, importação, banco, ranking, Portal, comprovantes, WhatsApp Django, cache, mapa e infraestrutura devem ser corrigidos ao redor do core. Se um dia for inevitável alterar o core, a versão não pode ser tratada como homologada sem re-homologação ponta a ponta da opção 036.
