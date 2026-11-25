# VEXO Web — continuidade do projeto

Aplicativo HTML/CSS/JavaScript com quatro módulos: Corridas, Driver, Fuel e Finance. Esta pasta é independente do projeto Android do repositório.

## Executar

Com Node.js instalado, execute `node server.cjs` nesta pasta e abra http://127.0.0.1:8765/. Não há build obrigatório. `index.html` e `central.html` são entradas equivalentes.

## Arquivos principais

- `mobile-original.html`: simulador ativo, aberto no quadro Corridas.
- `driver.html`, `fuel.html`, `finance.html`: dashboards preservados e adaptados.
- `data.js`: API local compartilhada, receitas, abastecimentos, despesas, metas e estado da oferta.
- `settings.js`: parâmetros manuais de combustível, consumo e custo fixo.
- `responsive.css`: ajustes comuns para celular.
- `chart.umd.min.js`: Chart.js 4.4.1, licença MIT mantida no cabeçalho.
- `test-local.cjs`: teste de navegador com Playwright e Microsoft Edge; requer pacote playwright e Edge instalado. Usa contexto isolado e dados fictícios.

## Estado real e limitações

Os dados ficam em localStorage, chave `vexo-data-v2`, e são compartilhados pelos módulos no mesmo navegador/origem. Não existe banco online, autenticação ou sincronização entre aparelhos. Este envio ao GitHub armazena o código; não publica o app.

O teste anterior confirmou geração/aceitação/finalização sem duplicar receita, dois abastecimentos, despesa, renderização dos três dashboards e largura de 390px. Os testes não demonstram sincronização entre dispositivos nem instalação PWA.

As ofertas usam IDs MOB-. Só finalizar gera receita. O orçamento é congelado ao aceitar. Sem ciclo completo de tanque cheio, a estimativa usa preço/consumo configurados. Finance mantém sua lógica de cobertura por ciclos e pode não apresentar lucro integral quando faltam dados; saldo de caixa é separado da estimativa de lucro.

Pendências: backend online autenticado, hospedagem HTTPS, reconexão e fila offline, PWA completa (manifesto, ícones e cache dos módulos), temporizador de ofertas, semáforos completos e testes de concorrência entre dispositivos. Não declarar essas funções prontas.

Os arquivos de protótipo `app.js`, `generator.html`, `styles.css`, `sw.js` e `manifest.webmanifest` são legados, não a implementação ativa dos quatro módulos. Não usar o financeiro simplificado do protótipo como fonte de cálculo. Os scripts de migração são históricos e não devem ser reexecutados.

## Para outra IA continuar

Use a branch `codex/vexo-web-local`, pasta `vexo-web-pwa`. Leia este documento e os módulos antes de editar. Preserve a identidade visual e cálculos existentes. Não reintroduza Google Sheets/Apps Script como dependência. Não grave dados de usuários, tokens, arquivos .env ou credenciais no repositório. Preserve o projeto Android fora desta pasta. Valide finalização idempotente, formulários e telas mobile após alterações.
