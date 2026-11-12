# Vexo Reader — Android nativo experimental

**Projeto standalone independente** dentro de vexo-mlkit-lab, criado em uma branch própria para não modificar a implementação dos demais agentes.

## Para que serve

Ler a tela que o usuário autorizar no Android com **MediaProjection** e **Google ML Kit Text Recognition** (modelo latino incluído no APK), extrair dados de oferta (preço, minutos/km, endereços, nota quando identificável) e salvar **ofertas observadas** na base SQLite **do próprio aparelho**.

É um leitor de ofertas, NÃO um automatizador de aceite, NÃO um detector oficial da 99 e NÃO comprova que uma corrida foi aceita/finalizada.

## UI

Tela nativa em modo escuro com acentos ciano/verde, monitor de frames/leituras OCR **medidos**, painel de oferta estilo Vexo LAB, regiões de campos em verde, botão de iniciar/parar e histórico de até 200 registros locais. Quando não há dados reais, a tela exibe traços em vez de números inventados.

## Execução

1. Instale o APK debug da workflow **Vexo Reader - APK standalone** (GitHub Actions > artefatos).
2. Abra Vexo Reader, toque **Iniciar leitura** e aceite o diálogo do Android.
3. Se o Android oferecer **Um único app** ou **Tela inteira**, selecione conscientemente qual aplicativo será compartilhado.
4. Abra a tela de ofertas *autorizada* e depois volte ao Vexo Reader para conferir as **ofertas observadas**.
5. Toque **Parar** ou pare na notificação persistente. Use **Apagar** para excluir o histórico.

Somente testar com o veículo parado. Não operar a interface nem conferir campos dirigindo.

## Arquitetura implementada neste MVP

- Captura: foreground service com tipo mediaProjection, consentimento por sessão, MediaProjection.Callback, ImageReader.acquireLatestImage(), parada explícita e resize do mesmo VirtualDisplay.
- Visual: amostra de brilho 32×24 por frame para detectar mudanças expressivas. **Não é KLT, não rastreia identidade do card automaticamente**. Não reivindicar FPS ou latências arbitrárias.
- OCR: ML Kit empacotado, uma leitura de cada vez, intervalo mínimo 700ms, recorte proporcional de 15% a 100% da altura da tela, sem cópias de frames em fila.
- Validade: epoch da geometria/transição visual, geração de sessão, descarte por idade >2300ms, limpeza da prévia, duas leituras semânticas iguais antes de persistir e deduplicação por assinatura/epoch.
- Parser pt-BR: preço R$, duas pernas com minutos e quilômetros, linhas de endereços e nota quando disponível. Valores improváveis rejeitados.
- Persistência: SQLite local, no máximo 200 registros; imagens, OCR bruto e localização não são enviados a servidores. Manifest sem permissão de rede.

## Limitações conhecidas: importantes

- Não há prova de funcionamento real da 99 nem acurácia de 99%. O parser ainda depende do layout e da ordem de texto retornada pelo ML Kit.
- O rastreador de brilho é apenas evidência superficial; troca A→B com pixels muito semelhantes pode não mudar a epoch. OCR posterior detecta diferenças semânticas, mas não garante distinguir episódios visuais iguais. Não use como contagem financeira definitiva.
- O recorte é amplo (85% da tela), não as três ROIs totalmente adaptativas do conceito. A UI mostra o contorno dos **campos de dados**, não é overlay sobre outro app.
- Sem notificação de oferta acionável, sem auto aceitar, sem API da 99, sem inferir se uma oferta é ao vivo, Galeria ou replay; **nunca marcar como corrida concluída**.
- Se a captura Android estiver limitada a um único app, trocar para Galeria não passa a capturar a Galeria. Telas protegidas por FLAG_SECURE podem surgir pretas.
- A equipe precisa validar o APK, a performance, a correção da transição A→B e o respeito à privacidade em aparelho físico antes de usar em produção.

## Build

Este módulo não utiliza o Gradle do laboratório principal:

    cd reader-standalone
    gradle --no-daemon testDebugUnitTest assembleDebug

APK: app/build/outputs/apk/debug/app-debug.apk

Versões: Java 17, AGP 8.7.3, Gradle 8.11.1, compile/target SDK 35, min SDK 26, ML Kit 16.0.1.

## Segregação

Tudo fica em reader-standalone/ e na workflow específica. Não altera app/, outros workflows, PRs dos agentes ou branch main até revisão. Build e testes do novo código ainda precisam passar na CI.
