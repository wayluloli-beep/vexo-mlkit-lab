# Vexo Frankenstein: Meu veículo (integração controlada)

## Objetivo
Transplantar **somente** a experiência "Meu veículo" do Vexo legado para a versão mais nova, mantendo Aura Sync, Gemini, OCR, dados financeiros e navegação. Referência visual fornecida: Chevrolet Vectra 2010 vermelho com imagem do carro, cabeçalho, placa, ícones de injeção, óleo, combustível e pneus, popover P0524 e botões "Simular alertas".

## Estado comprovado
- Este repositório já contém a montagem da página `veiculo.html` via `qa/extract-vehicle.cjs` e `qa/r19/materialize.sh`, com seleção de veículo preservada.
- A base deste branch é `vexo-r22-google-tts`, NÃO o APK `Vexo-Aura-1_8.apk`.
- O APK 1.8 enviado na conversa não é código-fonte versionado neste repositório e **não foi fundido**.
- Não assumir que uma imagem do print é um asset licenciado ou acessível no GitHub; utilizar apenas imagens existentes no projeto ou fornecidas para uso.

## Dez frentes de revisão
1. Inventário de versões, package id, assinatura e migração de dados.
2. Isolamento da tela de veículo sem trocar o motor de navegação.
3. Galeria de fotos por modelo/ano/cor e fallback acessível.
4. Campos reais de veículo e edição de placa.
5. Alertas simulados visualmente identificados.
6. Descrição correta de DTCs; P0524 é condição de pressão de óleo **baixa** (sinal/diagnóstico depende de veículo e leitura real), não uma prova obtida do carro.
7. Separação rígida entre alertas fictícios e dados OBD2 verificados.
8. Regressão de Aura, OCR, TTS, Gemini, contas e armazenamento.
9. Compilação e testes automatizados; testes de WebView/Android ainda exigem execução.
10. Entrega de APK teste assinado, separado do app real, com backup antes de qualquer substituição.

## Limites e critérios de aceite
- A tela abre, exibe veículo cadastrado e permite selecionar modelo disponível.
- Botões Injeção / Óleo / Reserva / Pneu mostram **simulação** sem simular conexão OBD2.
- Nenhum DTC fictício altera registros do carro ou se apresenta como falha real.
- Nenhum código de OCR, captura, Gemini, Aura, financeiro ou pagamentos é removido.
- Sem usar estatísticas inventadas de leitura OCR.
- Compilação GitHub Actions prova empacotamento, não prova visual ou funcionamento em aparelho.
- Integração verdadeira com o APK 1.8 depende de seu código-fonte ou de um projeto Android equivalente, com assets e assinatura compatíveis.

## Como validar a base legada
A ação automatizada no arquivo `.github/workflows/frankenstein-veiculo.yml` materializa o projeto R19, aplica as camadas R20/R21/R22, verifica que `veiculo.html` existe e compila um APK de depuração. Esse APK é **comparativo do legado R22**, e não um APK 1.8.
