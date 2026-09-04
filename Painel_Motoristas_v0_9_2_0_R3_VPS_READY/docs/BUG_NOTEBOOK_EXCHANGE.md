# Troca do Caderno de Bugs — Patch 0.2.2-p1

O Caderno de Bugs agora pode ser exportado e reimportado pelo próprio Painel Motoristas.

## Exportar

Na tela `/bugs/`, clique em **Exportar Caderno**.

O sistema gera um ZIP no formato:

```text
PAINEL_MOTORISTAS_BUGS_AAAA-MM-DD_HH-MM.zip
├── BUGS.md
├── bugs.json
├── resumo.json
├── LEIA-ME.txt
└── prints/
    ├── BUG-0001_....png
    └── ...
```

- `BUGS.md`: versão humana, ideal para leitura e envio no chat.
- `bugs.json`: versão estruturada para conciliação/reimportação.
- `resumo.json`: contadores, versão e distribuição por prioridade/status/tela.
- `prints/`: cópia das evidências anexadas aos bugs.

Envie o **ZIP inteiro**, não apenas o Markdown, para manter as imagens vinculadas.

## Importar

Clique em **Importar Caderno**, escolha um ZIP gerado pelo Painel e confirme.

Cada bug recebe um `sync_id` UUID permanente. Na reimportação:

- mesmo `sync_id` → atualiza o bug existente;
- `sync_id` novo → cria um novo bug;
- o ID numérico local não é usado como chave de sincronização;
- anexos existentes são preservados quando o pacote não fornece nova evidência;
- a operação é transacional: em falha grave, o lote não é parcialmente aplicado.

## Segurança

- somente staff/admin pode exportar/importar;
- limite do ZIP: 128 MB;
- limite de conteúdo descompactado: 512 MB;
- proteção contra caminhos `../` dentro do ZIP;
- anexos importados continuam limitados a 8 MB por evidência;
- toda exportação/importação gera `AuditLog`.
