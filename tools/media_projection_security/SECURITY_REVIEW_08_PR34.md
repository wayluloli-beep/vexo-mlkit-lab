# Revisão 08 — PR #34, diagnóstico v2 e callbacks de sessão

**Data:** 11/11/2026. **Autor:** Agente 3, auditoria independente MediaProjection. **PR auditado:** https://github.com/wayluloli-beep/vexo-mlkit-lab/pull/34, branch `feature/capture-context-evidence-counters`, SHA inspecionado inicialmente `6b3ffdb14422b5d61481c155a430b492c6fa3c37`.

## Prova de aparelho versus prova de código

Os relatos de **diagnósticos agregados voluntários** na Issue #21 dão dois resultados que não podem ser confundidos:

- **Tela fictícia no aparelho:** 194 frames, 9 OCR concluídos, 1 alerta. Prova que captura MediaProjection + ImageReader + OCR + notificação conseguiram completar um ciclo com conteúdo fictício. Não prova acurácia numérica nem 99 aberta diretamente.
- **Vídeo privado da 99 reproduzido na Galeria:** status final **CAPTURE_STOPPED**, 3.439 frames, 83/83 OCR concluídos, 0 alertas, 1 candidato, 82 UNCERTAIN, 0 rejeições financeiras. Prova captura autorizada do REPRODUTOR e STOP, mas **não prova** que candidato era o card verdadeiro nem que 1/83 represente acurácia; muito conteúdo era mapa/galeria/anúncio.
- Nenhuma mídia/print/texto OCR/endereço/token/relatório privado foi copiado para GitHub pela auditoria.

## Achado P0 — centavos confundidos com marcador 99 no novo diagnóstico

No novo `ScreenContextClassifier.diagnosticEvidenceMask`, `modality=has(t,"\\b(?:99|moto|...)\\b")` e `EVIDENCE_LITERAL_99` é marcado por `t.contains("99")`. Em texto fictício `R$0,99`, a parte `99` depois de vírgula satisfaz a âncora de palavra. Assim, um **preço de propaganda** marca equivocadamente plataforma/modalidade e âncora. Os testes Java do PR #34 detectaram o erro, no [CI 43078793764](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43078793764): `78 tests completed, 2 failed`, casos `CaptureContextEvidenceTest.adWithPriceHasNoOfferContext` e `counterOverlapDoesNotEqualClassificationAndResetWorks`.

É erro comprovado na **instrumentação diagnóstica**, não prova de que a versão do usuário emitiu um alerta indevido. Também revisar `LiveCaptureService.evaluate` usando `text.contains("99")` para não tomar centavos por âncora, sempre preservando requisitos financeiros e as duas leituras seguras. Solicitação de correção publicada no PR #34, comentário [#6804241669](https://github.com/wayluloli-beep/vexo-mlkit-lab/pull/34#issuecomment-6804241669).

## Achado P1 — contadores novos sem guarda de epoch no momento da escrita

`LiveCaptureService.evaluate(String text,long session)` chama `LiveCaptureState.recordContextEvidence(mask)` **antes de entrar em `synchronized(sessionLock)` e verificar `sessionAlive(session)`**. O callback ML Kit confere epoch antes de chamar evaluate, mas STOP/restart pode acontecer antes do incremento; `recordContextEvidence` usa somente `if(active)`, então uma leitura antiga pode contar na sessão nova. **Risco de corrida de threads por inspeção do código, ainda não reproduzido no dispositivo.** A correção indicada é associar a contagem ao mesmo lock + epoch do STOP ou epoch/token validado atomicamente, com testes callback pendente, STOP e novo consentimento.

## Achado P1 — callback de visibilidade atrasado

`MediaProjection.Callback.onCapturedContentVisibilityChanged` da stack #34 altera `capturedVisible` e `LiveCaptureState.capturedContentVisibility` sem verificar epoch/active/stopping sob `sessionLock`. Um callback antigo poderia alterar o estado da captura seguinte. A auditoria acrescentou `visibility_callback_review.py` e 8 regressões sintéticas: exigir guarda epoch, sessão ativa, parada não iniciada, lock compartilhado com STOP e os dois writes dentro do lock. A inspeção read-only do PR #34 no [run 43080122222](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43080122222) mostrou **1 PASS / 2 FAIL**: STOP invalida a sessão no lock, mas callback não checa epoch/STOP sob lock e escreve visibilidade sem guarda. Isto não prova race observado; exigir JUnit/instrumentado do Android.

## Privacidade do JSON v2

`LiveCaptureState.safeDiagnosticReport` usa schema `vexo-live-capture-diagnostic-v2`, preserva campos técnicos v1 e inclui `contextEvidenceCounts` com oito contagens: `ocrReadsExamined`, preço como marcador binário, botão, modalidade, duas distâncias, dois tempos, marcador 99 e pista parcial de oferta. Não contém preço, OCR bruto, rota, imagem ou identificador no valor exportado conforme inspeção inicial. `CaptureContextEvidence` usa apenas oito `AtomicLong` e faz reset na nova sessão. Os contadores se sobrepõem, nunca são medida de acurácia.

O scanner independente `context_evidence_v2_review.py` verifica **exatamente** oito chaves e suas expressões `ev[0..7]`, sem chaves adicionais/dinâmicas; somente contadores em RAM; ausência de referências a texto bruto; reset; classificação não substituída por máscara; e bloqueia escrita de telemetria sem guarda epoch. No [CI de auditoria 43080122222](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43080122222) os **123 testes sintéticos Python passaram**, e a verificação read-only do PR #34 resultou em **5 PASS / 1 FAIL**: a falha é precisamente `V2_SESSION_GUARD_BEFORE_COUNT`. Os PASS são verificação estática/allowlist, não auditoria formal da ausência de vazamento.

## Pendências para equipe e gatilhos de aprovação

1. **Android — PR34:** corrigir regex/âncora 99 e 2 unitários; garantir escrita dos novos contadores sob sessionLock/epoch; adicionar teste STOP/restart com conclusão OCR atrasada. Manter **two-stable reads, FinancialGuard e consentimento Android**; não editar CSV ou prints reais.
2. **Android — visibilidade:** guard epoch/active/stopping e lock ao publicar callback; testar callback antigo após STOP/restart e esconder/dar visibilidade à nova sessão sem interferência.
3. **Agente OCR:** definir negativos de anúncio com `R$0,99` e outras quantias terminadas em `,99`, lista expirada e mapa; distinguir sinais de contexto por quadro sem transformar 83 OCRs de mapa/player em denominador de acurácia. Auditor não altera branch OCR.
4. **Produto:** não solicitar repetição do replay privado até saber que dados coletados são suficientes; manter exportação voluntária exclusivamente agregada. Próximo APK só após CI, segurança e consentimento real validarem nova versão.

**Limites da revisão:** scanners de Java são heurísticos, testes Python são sintéticos, e o arquivo de vídeo privado permanece fora do repositório. Nenhum merge nem alteração em Android/Gradle/main por este agente.
