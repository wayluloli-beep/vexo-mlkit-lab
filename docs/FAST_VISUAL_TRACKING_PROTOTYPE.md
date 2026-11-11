# Vexo — prova de rastreamento visual rápido (protótipo NÃO integrado)

**Objetivo definido pelo proprietário:** o card aparece por ~5 segundos ou menos. Cada milissegundo importa. O estado visual da janelinha deve acompanhar o card, sem travar esperando OCR, sem piscar e sem continuar após desaparecer. No modo Galeria/laboratório, permitir inspecionar campos reconhecidos sem fingir que foto antiga é corrida ativa.

Este PR é deliberadamente um **PROTÓTIPO ISOLADO E SEM EFEITO NO APK**. Adiciona código puro Java + testes, mas não conecta o rastreamento ao \`ImageReader\`, não cropa OCR real e não altera alertas. O app existente ainda usa 700 ms como intervalo mínimo de OCR e seu fluxo normal continua igual até integração avaliada. Não afirmar "30 FPS" ou "100 ms" reais sem instrumentação no dispositivo.

## O que foi entregue

1. \`FastCardVisualTracker.java\`: recebe um provedor de **luminância amostrada** (não cria bitmap/cópia da tela), guarda 96 valores efêmeros em RAM de uma região **já confirmada** como card por um detector independente, e procura a mesma região dentro de ~24 pixels a cada frame recebido. Busca grosseira + refinamento de 1 pixel. Se o card some ou não corresponde, retorna \`disappeared\` **no próprio frame**, para que a integração oculte números antigos imediatamente. Se a região reaparecer, retorna \`appeared\`; não envia notificação, não considera foto da Galeria oferta real nem fornece ID de corrida.
2. \`FastOcrScheduler.java\`: um OCR por vez, só para um card presente, sem fila de frames antigos; por exemplo, janela mínima de 120 ms **não é duração de leitura ML Kit nem promessa de 8 FPS OCR**. Um callback antigo, após desaparecimento/STOP/restart, não pode concluir o ticket atual. A sessão \`epoch\` e a validação de frescor/FinancialGuard do serviço Android continuam obrigatórias.
3. **48 testes JUnit sintéticos escritos no total** (\`FastCardVisualTrackerTest\`: 12, \`FastOcrSchedulerTest\`: 9). Verificam drift 1px, 9 deslocamentos, ausência em primeiro frame, não piscar com 301 frames, rejeição de fundo sem textura, STOP/reset, tempo monotônico, um só OCR em voo e invalidação imediata de resultado antigo. Resultados precisam de CI no SHA da branch; testes unitários não são medição de FPS/latência nem prova da 99.

## Arquitetura solicitada, da mais rápida à mais cara

\`\`\`text
MediaProjection (com permissão Android) -> ImageReader (frames contínuos)
  |  sempre, para cada frame recebido, sem esperar o ML Kit:
  +-- ROI visual leve (detecção/track, coordenadas, presença)
  |     +-- sumiu? esconder números e invalidar OCR em voo NA HORA
  |     +-- apareceu? mostrar estado neutro "analisando..." imediatamente
  |
  +-- OCR sob demanda, crop ROI (somente 1 em voo, sempre imagem recente)
        +-- parser devolve campos vistos/ausentes/incertos
        +-- estados são visíveis no laboratório sem virar oferta ativa
        +-- no modo ao vivo: classificador + FinancialGuard + idade real do
            frame + episódio + 2 observações coerentes -> números no card
            e possível notificação (motorista decide)
\`\`\`

**Atenção:** 30 frames recebidos por segundo NÃO significam 30 inferências ML Kit por segundo. No relatório v3 no telefone: p50 individual OCR=482 ms, p95=1252 ms, máximo=3447 ms. O novo rastreador barato pode reagir antes da inferência, porém só depois do OCR completar é possível mostrar números confirmados. Para mostrar valores em menos de 0,5 s, precisamos medir e otimizar o **recorte ROI**, aquecimento e processamento no aparelho real. Não inventar resultados.

## Complemento: gatilho inicial e leitura RGBA sem copiar tela

- \`FastRoiActivityProbe.java\`: com referência **de um frame comprovadamente sem oferta** e uma ROI configurada, compara 96 pontos na mesma região de todos os frames. Qualquer mudança relevante gera \`risingEdge\` **no primeiro frame recebido** para pedir OCR. Mudanças A→B **sem retorno ao mapa** também produzem `changedSincePrevious` para solicitar nova inspeção, mas NÃO autorizam uma segunda notificação como corrida distinta. Voltar à imagem de fundo sinaliza \`returnedToBaseline\`. Uma mudança de MAP, anúncio ou Galeria também pode disparar; isto é **somente um gatilho de investigação**, não prova de card da 99 e nunca pode emitir aviso financeiro sozinho.
- \`RgbaLumaPixels.java\`: adaptador de \`Image.Plane\` RGBA com \`rowStride\` e \`pixelStride\`, lendo luminância por ponto de um \`ByteBuffer\` read-only. Não faz \`Bitmap.createBitmap\` nem cópia de frame. O objeto é **transitório e só pode ser usado antes de \`Image.close()\`**, jamais guardado por uma thread de OCR.
- \`FastRoiActivityProbeTest.java\` (10 casos) e \`RgbaLumaPixelsTest.java\` (6 casos) completam a prova sintética. Total na branch: **35 testes JUnit escritos** (12 visual + 9 scheduler + 10 probe + 6 RGBA). Só chamar de PASS depois da conclusão do CI no HEAD exato.

*Fluxo recomendado para a primeira oferta:* o ROI fixo, posicionado a partir de perfil de tela/ancoragem e validado em configuração de laboratório, detecta visualmente alteração. Isso dispara OCR da região. Depois que o parser/classificador confirma o card, \`FastCardVisualTracker.armFromVerifiedCard\` passa a segui-lo com ±24px sem depender de novas inferências. Se o card some, esconder números e invalidar callbacks; se apenas mudou o mapa, o classificador deve recusar o alerta. Não existe garantia universal de ROI na 99 sem testes de variantes/densidades/rotação.

## NOVO: descoberta automática adaptativa e laboratório visual dentro do APK

- \`AdaptiveCardRegionDetector.java\` varre a tela em grade de resolução LIMITADA (até 72×128 pontos), com tamanho proporcional à tela e sem posições fixas. Uma tela anterior confirmada **sem oferta** estabelece referência; mudanças em componentes conectados geram propostas de regiões retangulares. Captura de app inteiro, mapa animado, banner, Galeria ou pop-up podem produzir o mesmo sinal: **NÃO é detector semântico da 99 nem autorização de notificação**. Mudança de orientação/tamanho invalida a referência, que só pode ser reconstruída quando uma nova tela sem oferta for confirmada.
- \`AdaptiveCardRegionDetectorTest.java\`: 11 testes artificiais para posições distintas, paisagem, A→B sem mapa, card estável, desaparecimento, fullscreen, resize, STOP e relógio monotônico.
- \`VisualRadarLabActivity.java\`: experiência visual sintética no Android: card A surge, desloca, card B substitui, some e reaparece; contadores de frames e região detectada, com caixa de tracking. É acessível pelo botão **“Testar radar visual modular (simulação)”** na tela inicial. Essa tela usa pixels **gerados em memória** para exercitar as classes verdadeiras do rastreador, **não usa câmera, MediaProjection, OCR, fotos pessoais ou conexão com o app 99**. Não informa FPS preciso; a função de desenho pede quadros a cada 33 ms mas o sistema operacional pode executar menos.
- O Android Manifest registra a Activity experimental sem exportar para outros aplicativos. **48 testes Java sintéticos escritos (37 anteriores + 11 novos)**, que precisam passar no CI do HEAD correspondente.

### Teste no telefone (DEPOIS da compilação no CI)

1. Instalar apenas o APK **experimental** do PR #43, mantendo versão anterior instalada se os IDs diferirem; nunca usar esta versão como assistente de decisão em corrida.
2. Abrir **VEXO → “Testar radar visual modular (simulação)”** com carro parado. Observe caixa verde durante o card em movimento, troca A→B, sumiço e retorno. Não é necessário ligar MediaProjection.
3. Verifique que não aparece cálculo/alerta de oferta real. Faça vídeo de tela **somente da simulação**, se desejar comparar velocidade; nenhuma imagem real de passageiro deve ser enviada.
4. Para aferição real, integrar detector ao \`LiveCaptureService\` antes do OCR throttle, testar com consentimento Android e confirmar tempos/P95 no hardware. O experimento não prova a captura automática da 99.


## Próxima integração, isolada pelo agente Android

1. Criar adaptador \`Pixels\` sobre \`Image.Plane\` RGBA com \`rowStride/pixelStride\`; amostrar só 96×(busca) pontos. **Não** converter o frame inteiro a grayscale/Bitmap a 30 FPS. O tracker deve rodar **antes** de \`CaptureThrottle.begin\`; esse gate limita somente OCR, não presença visual. Medir CPU e tempo total da callback (P50/P95), usar FPS **reais recebidos**, não assumir 30.
2. Resolver **detecção inicial do retângulo do card**: o protótipo só consegue \`armFromVerifiedCard\` quando já existe ROI confiável. Implementar primeiro uma ROI ancorada/configurável baseada no layout do 99, com fallback de busca e controle contra falso card em mapa/propaganda/Galeria. Acompanhar drift, orientação/resize e não tomar caixa fixa como prova de uma corrida. Sem isso, rastreamento "30 FPS" não encontra oferta nova sozinho.
3. Rodar OCR **somente dentro da ROI** quando houver card novo/alteração relevante, no máximo um em voo, sem bloquear coleta de frames. Evitar crop que corte dígitos; fallback diagnóstico no laboratório. Captura externa só com consentimento nativo; não burlar \`FLAG_SECURE\`.
4. Separar três estados independentes: presença visual, campos OCR e anúncio. Na primeira perda de correspondência, esconder **apenas o card financeiro**, não destruir a captura. Quando OCR/candidato chega atrasado de uma tela anterior, descartá-lo por \`epoch\`, versão visual e frescor. Preservar o teto de 3 s como última proteção, **não** como cadência do rastreador e sem esperar 3 s para esconder UI.
5. Modo Galeria/Laboratório: **sem alerta de corrida disponível** para imagens/MP4 antigos. Não mostrar dados fictícios persistentes como se tivessem sido capturados na tela nova. Provar em E2E que "Tela inteira" vs "Um único app" muda o que o Vexo recebe.
6. Medir antes/depois em aparelho parado: (a) surgimento visual→estado "analisando" (alvo experimental P95 ≤100 ms **após frame recebido**, não garantia), (b) surgimento→números validados (alvo aspiracional P95 ≤500 ms no aparelho), (c) desaparecimento→ocultar UI (alvo experimental 1–2 frames; em 30 FPS 33–67 ms), (d) FPS visual efetivo, (e) acurácia por **episódio** e latência por campo, (f) consumo CPU/bateria/tela. Essas metas podem não ser atingíveis com ML Kit no hardware atual.
7. Agente 3 revisa consentimento, STOP/callback tardio, privacidade e overlay (FLAG_NOT_TOUCHABLE/SECURE). **Nenhuma aceitação/rejeição automática da 99**, nenhuma retenção de screenshot/OCR ou upload de dados privados.

**Limitação de identidade:** dois cards podem ter muitos pixels iguais, e uma imagem de Galeria também pode combinar com o modelo. \`FastCardVisualTracker\` NÃO comprova que uma corrida está ativa nem separa uma nova corrida com mesma aparência. O \`OfferEpisodeGate\` e classificador precisam continuar protegendo *avisos*, sem bloquear observação ou deixar resumo velho visível. Não promover APK de produção até E2E integrado, falsos positivos controlados e testes de segurança.
