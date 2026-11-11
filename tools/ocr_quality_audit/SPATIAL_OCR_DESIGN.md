# Parecer técnico para o agente Android: recuperar a precisão por visão espacial

**Escopo:** desenho técnico independente, não é código Android aplicado. Sem merge. Evidência conhecida: relatório 0.3.3 com 106/111 campos corretos em dez prints; cinco divergências. Leitura real de imagens e causas raízes ainda não confirmadas.

## O gargalo concreto no código atual

Na branch Android `feature/ocr-visual-stress-emulator`, `BatchOcrActivity.scanNext()` chama:

```java
recognizer.process(InputImage.fromBitmap(bitmap, 0))
    .addOnSuccessListener(text ->
        addEvaluation(item, OfferParser.parse(text.getText()), null, text.getText()));
```

Essa operação **descarta a geometria** do resultado `Text`: o `OfferParser.parse(String)` só recebe texto plano. `OfferParser.parseLegs()` coleta regex de distâncias e associa as duas primeiras ocorrências pela posição na string. `OfferParser.parse()` busca `surge` por regex no texto global. Esses comportamentos são comprovados pela leitura do código; que *causem* cada erro é hipótese a validar nos prints originais.

ML Kit Text Recognition v2 já expõe `getTextBlocks()`, `getLines()`, `getElements()`, `getSymbols()`, `getBoundingBox()`, `getCornerPoints()` e, quando aplicável, `getConfidence()`. Não exige novo modelo nem treinamento. Referência oficial: https://developers.google.com/ml-kit/vision/text-recognition/v2/android

## Três mudanças com prioridade e custo

**1) P0 — Preservar geometria e segmentar a região correta da oferta (mudança inicial).**

- Manter `OfferParser.parse(text.getText())` como caminho de referência.
- Introduzir representação leve/efêmera `SpatialToken{text, box, lineId, regionId, source}` baseada em `Text.Line`/`Text.Element`/`Text.Symbol`; coordenadas em pixels e relativas ao card, nunca coordenadas absolutas presumidas para todos os modelos.
- Identificar o card por âncoras de layout reconhecidas e separar da barra do celular/navegação. Usar as posições relativas a *âncoras efetivamente detectadas* (`Moto`, `Negocia`, `Prioritário`, tempo/distância, ícones e regiões numéricas). Layout não reconhecido -> permanecer no parser antigo + revisão, não forçar mapeamento.
- Associar valor e unidade na mesma região/linha. Para `surge`, evitar buscar `x` em toda a tela; para distância, distinguir `pickupKm` e `tripKm` pela posição/linha e relacionamento com minutos. Não assumir que os dois primeiros matches globais são sempre os dois trajetos.
- **Importante:** uma leitura `42,8x` pode conter raio ⚡ fundido como um único *símbolo*, e caixas OCR **não garantem** separar o ícone. Se o ícone não aparece isolado geometricamente, NÃO eliminar o caractere `4` automaticamente.
- Custo: uma extração adicional de tokens/O(n), sem segunda inferência ML Kit. Risco: layouts alterados, associação errada entre regiões.

**2) P0 — Segunda leitura apenas de campos incertos com ROI do bitmap original.**

- Disparar somente quando `surge`/`tripKm` estiver ausente, plausivelmente corrompido ou em conflito com posição da oferta. O gatilho de anomalia não serve para reconstruir valor.
- Calcular ROI a partir de linhas/âncoras com margem para **não cortar o primeiro dígito**; validar limites com `Rect.intersect()`. Construir recorte de `Bitmap` **em memória**; testar imagem nativa e uma ampliação controlada (ex.: 2×) ou contraste como variantes **opcionais**, sem alterar o bitmap de origem. O ganho precisa ser medido por layout; nitidez artificial pode piorar.
- Chamar `recognizer.process(InputImage.fromBitmap(crop, 0))` apenas para ROI incerta e de forma assíncrona. A leitura original é mantida, inclusive quando a ROI falha.
- **Ciclo de vida:** atualmente `scanNext()` recicla o bitmap em `addOnCompleteListener`; passar a reciclá-lo **somente após o encadeamento da última leitura**, evitando acesso a `Bitmap` reciclado. Reciclar as variantes temporárias também.
- Limitar a 1 ROI principal por campo incerto (ou orçamento de até duas passagens condicionais), evitando rodar OCR múltiplas vezes em todo o frame. Medir latência p50/p95 e memória por perfil no emulador antes de definir orçamento para uma futura captura contínua.
- Custo: cada `process()` adicional é uma inferência, aumentando latência/CPU/bateria/memória; em modo streaming precisará de fila/throttling e descarte de frames antigos. Risco: ROI errada, perda de contexto, exagero de contraste, cortes de texto.

**3) P0 — Fusão conservadora de candidatos + sinal de confiança local.**

- Retornar `Candidate{field, value, source(full|roi), bbox, hasUnit, layoutAnchor, ambiguous}`, e um estado `VERIFIED_CANDIDATE | REVIEW_REQUIRED | ABSENT` separado da quantidade de campos básicos lidos.
- A regra inicial de aceite de recuperação deve exigir **candidato em ROI de oferta reconhecida**, unidade coerente, contexto plausível, evidência visual direta e ausência de candidatos conflitantes. Duas leituras da mesma rede ML Kit são *correlacionadas*, então concordância entre elas sozinha NÃO é prova independente.
- Se o OCR global diz `1,8` e a ROI diz `11,8`, **não preencher `11,8` apenas por plausibilidade**. Primeiro registrar conflito/revisão. Só permitir override depois de validação nas imagens corretas, evidência dos pixels do primeiro `1`, geometria/texto coerentes e decisão aprovada de produto.
- Se o global diz `42,8x` e a ROI diz `2,8x`, NÃO aplicar `replaceFirst("4", "")`; inspecionar origem espacial do caractere extra, identificar o ícone em região separada quando visualmente possível e aceitar `2,8x` somente com evidência contextual. Se ambíguo, sinalizar `surge=unknown`, nunca `surge=0`.
- `FinancialGuard.assess()` precisa separar `basicFieldsUsable` (preço, tempo, distância para métricas que dependem somente desses campos) de `fullFinancialIndicatorsVerified` (surge e perKm quando presentes/esperados). **Não bloquear necessariamente todo cálculo básico se um campo opcional está ausente**; bloquear apenas as recomendações/cálculos dependentes, e jamais presumir multiplicador zero.
- Custo: baixo se integrado com dados já extraídos; maior complexidade de regra. Risco: falso positivo de recuperação; o fallback para `REVIEW_REQUIRED` protege mais do que completar com chute.

## Primeira alteração pequena sugerida para o próximo PR Android

**Apenas o campo `surge`**: em `BatchOcrActivity.scanNext()`, manter `Text` em vez de reduzir a `getText()` imediatamente; implementar `SpatialSurgeResolver.resolve(Text, Bitmap, OfferParser.Offer)` atrás de `ENABLE_SPATIAL_SURGE=false` por padrão; localizar âncora visual da oferta e tentar uma única ROI **quando surge estiver missing/ambiguous**. Entregar candidato **separado** do parser inicial e razões de revisão; não sobrescrever automaticamente valor financeiro na fase 1. Na fase 2, habilitar recuperação apenas se passar critérios com evidência espacial e testes negativos.

Pseudocódigo (illustrativo, *não* é código pronto para compilar):

```text
onMlKitSuccess(textResult, originalBitmap):
    baseline = OfferParser.parse(textResult.getText())
    geometry = SpatialTokens.fromBlocksLinesElements(textResult)
    decision = ReviewState.from(baseline)
    if FEATURE_SPATIAL_SURGE and needsReview("surge", baseline, geometry):
        roi = findCardSurgeRoiByAnchors(geometry, originalBitmap.bounds)
        if roi exists:
            retry = await recognizer.process(InputImage.fromBitmap(cropWithMargin(roi), 0))
            candidate = parseSurgeOnly(retry, roi, anchorContext=true)
            decision = fuseConservatively(baseline.surge, candidate, geometry)
    // Don't recycle originalBitmap until optional OCR task completes.
    saveOnlyAggregateReportAndFlags(noRawTextOrImages)
    if decision.isAmbiguous: markSurgeAsReviewRequired()
    // No accept/cancel action; driver decides.
```

**Rollback:** `ENABLE_SPATIAL_SURGE=false` (sem alterar o parser legado), reversão da etapa ROI se elevar falsos positivos ou latência/memória. Tratar tempo limite/falha da segunda leitura como `REVIEW_REQUIRED`, não substituir valor por chute.

**Aceite técnico inicial (ambiente digital, não precisão em produção):** PR draft separado com resultados A/B no mesmo conjunto sintético, controle negativo com `surge` ausente, `42,8x`, `42,2x`, `2,8x`, `2,2x`, diferentes temas, distância de navegação fora do card e recorte que inclui o primeiro dígito. Registrar latência e falsos positivos; nenhum aceite/cancelamento automatizado; sem dados privados em logs.

**Aceite para declarar melhora real:** replay privado das dez imagens originais com rótulos humanos conferidos e versão antiga/nova; medir acerto literal por campo, por oferta e falsos positivos, sem confundir **bloqueio seguro** com **acerto de OCR**. O PR #6 já tenta corrigir `perKm=1,28/km`; não duplicar. O PR #12 é um bom primeiro ambiente de regressão visual sintética.

## Limite da auditoria

Esta documentação foi adicionada **somente** em `tools/ocr_quality_audit/`. A auditoria Python não executa o modelo ML Kit Android; não seria adequado simular seu comportamento com OCR de outra engine (Tesseract etc.) e afirmar ganho no app. Concentrei a colaboração em desenho de intervenção, regras de integração, rollback e critérios de avaliação.
