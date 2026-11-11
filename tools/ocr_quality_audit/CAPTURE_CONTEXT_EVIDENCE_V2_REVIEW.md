# Vexo 0.4 — auditoria de evidência do OCR, schema v2

**Origem:** PR draft #34, branch Android `feature/capture-context-evidence-counters`, sem acessar vídeos, screenshots, áudio, endereços, rotas nem texto OCR. O único objetivo é interpretar **contagens agregadas** e manter a exportação voluntária segura.

## O que foi implementado no auditor independente

- `live_diagnostic_audit.py`: aceita **somente** (1) schema v1 sem latências, (2) v1 com seis latências, ou (3) schema `vexo-live-capture-diagnostic-v2` **com os seis campos de latência e o objeto `contextEvidenceCounts` exato**. Campos extras/ausentes, JSON com chaves duplicadas, tipos inválidos, valores booleanos tratados como números e conteúdo adicional de OCR/PII são rejeitados. As três strings de descrição são lidas, mas jamais devolvidas nos resultados.
- `contextEvidenceCounts` tem oito inteiros: `ocrReadsExamined`, `readsWithPriceMarker`, `readsWithActionButton`, `readsWithOfferModality`, `readsWithTwoDistances`, `readsWithTwoTimes`, `readsWith99Marker`, `readsWithPartialOfferEvidence`. Nenhum contador de sinal pode ultrapassar `ocrReadsExamined`; `ocrReadsExamined` não pode exceder OCR concluídos; o contador de oferta parcial depende do sinal de preço. Os sinais **se sobrepõem** e NÃO devem ser somados como uma distribuição de 100%.
- `compare_live_diagnostics.py`: impede comparação v1↔v2 como se fossem a mesma estrutura, calcula diferenças de indicadores v2 somente quando os relatórios individualmente são consistentes, e sinaliza contadores decrescentes/reinício. Sem ID/epoch/timestamp de captura no JSON, comparações são **condicionais**: `sessionContinuityProven=false` mesmo que todos cresçam.
- `tests/test_capture_diagnostic_v2.py`: **16 novos casos sintéticos**, cobrindo privacidade nested, enum, schemas, amostras, reset, leitura incerta e comparação. Com os 33 testes anteriores da pasta local dedicada, **49/49 testes locais PASS**, usando blobs SHA iguais aos códigos publicados no PR #7. Ainda **não** é confirmação do CI Python integral no GitHub.

## Como interpretar, sem transformar números em precisão

No replay local da Galeria reportado na Issue #21, 83/83 OCRs concluíram, um contexto virou candidato e 82 ficaram `UNCERTAIN`, com sessão encerrada corretamente. Os **82 são classificações incertas**, NÃO 82 erros do OCR. Muitas telas do replay podem ter sido mapa, anúncio, interface da Galeria ou oclusão. Sem rótulos por trecho do vídeo, não se pode dizer em que segundo o candidato apareceu, se pertencia à oferta, nem calcular taxa de acerto. O v2 permitirá saber, **somente em conjunto de contadores**, quais tipos de âncoras estão aparecendo. Ainda não houve relatório v2 real neste auditor.

## Falha nova comprovada pelo próprio CI Android PR #34 (P1 de diagnóstico)

CI https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43078793764, job `Parser, segurança e APK`, **2 JUnit FAIL em 78**, na primeira tentativa consultada:
- `CaptureContextEvidenceTest.adWithPriceHasNoOfferContext`;
- `CaptureContextEvidenceTest.counterOverlapDoesNotEqualClassificationAndResetWorks`.

Causa de código identificada sem processar vídeo real: `ScreenContextClassifier.diagnosticEvidenceMask` usa tanto `\\b99\\b` na modalidade quanto `t.contains("99")` na âncora. Um preço sintético terminando em centavos `,99` cria um falso marcador de plataforma **99**, que ainda pode ativar `EVIDENCE_PARTIAL_OFFER` por `price && modality`. Isso **não prova** alerta falso do Vexo, pois o PR34 não mudou o classificador de alerta ou as guardas: os novos *contadores diagnósticos* é que ficariam enganosos.

**Aceite pedido ao Dev Android:** restringir **apenas os sinais de diagnóstico** de plataforma (sem mexer no gate/FinancialGuard). JUnit negativo para preço em propaganda, valor que contenha `99` dentro de outro número e preço iniciado em `R$99`; JUnit positivo para rótulos de plataforma `99 Moto`, `99 Negocia`, e texto com marcador 99 legítimo. Revisar como diferenciar marcador isolado de texto de preço; não assumir que `\\b99\\b` exclui decimais. Exigir CI verde, sem modificar o número de confirmações nem registrar OCR bruto.

## Comandos

```bash
python tools/ocr_quality_audit/live_diagnostic_audit.py /caminho/local/report-v2.json
python tools/ocr_quality_audit/compare_live_diagnostics.py /caminho/local/report1.json /caminho/local/report2.json
python -m unittest discover -s tools/ocr_quality_audit/tests -p 'test_capture_diagnostic_v2.py' -v
```

Nenhum JSON real, MP4, frame, ZIP, número de oferta, identidade, texto OCR ou chave de projeção deve ser enviado ao repositório. A validação do v2 e o CI de captura Android continuam separados da prova de compatibilidade com a 99, e o motorista segue no comando.
