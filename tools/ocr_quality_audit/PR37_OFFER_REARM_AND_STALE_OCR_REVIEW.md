# Auditoria PR #37 — identificação por episódio e frames descartados

**Escopo:** revisão independente do `OfferEpisodeGate.java` e `LiveCaptureService.java` de `feature/overlay-metrics-and-offer-recall`, HEAD `2cd5d055`, sem editar Android. Todos os identificadores abaixo são FICTIONS com tokens opacos; não são valores de corrida, screenshots, prints, vídeos ou OCR real. Não representam uma medição de precisão na 99.

## Achado P1 — nova política pode avisar DUAS vezes sobre o MESMO card

O gate original já alertado não rearmava sem duas telas definitivamente não-oferta. O PR #37 agora permite novo aviso com **3 leituras financeiras completas iguais** de um fingerprint **diferente** quando passaram **7.500 ms desde o último alerta**, cada leitura separada por no máximo 5.500 ms.

Esse mecanismo traz ganho potencial: uma nova oferta real sem mapa/intervalo pode ser vista. Mas **3 leituras numéricas iguais não comprovam identidade de nova corrida**, especialmente quando o mesmo card continua e o OCR corrige ou altera de forma sistemática preço, distância, modalidade ou duração.

**Contraprova Java executada localmente**, usando cópia da lógica do `OfferEpisodeGate` do PR #37 (não o Android/ML Kit): sequência fictícia `A@0, A@1000` gera alerta inicial; **o mesmo card visual** é lido com fingerprint B em `8500, 9200, 9900 ms`; a política atual retorna um **segundo alerta** para esse único episódio. É comportamento reproduzido do gate no harness, não evidência de problema em tela real. O controle `A,A` estável por 35s gerou apenas 1 alerta; o cenário `A,A,MAP,MAP,A,A` gerou corretamente 2 alertas para dois episódios visuais. **8 probes Java locais passaram** cobrindo esses casos, transição de mapa, janela mínima, uma/dúas leituras incertas e resgate.

- Modelo de inspeção Python `pr37_offer_rearm_audit.py` e **13 novos testes escritos** em `tests/test_pr37_offer_rearm_audit.py`. Eles distinguem **verdade visual de fixture** vs fingerprint de OCR, medem duplicação e falso negativo por episódio, e não se limitam a contagem de frames. Esses 13 testes novos ainda **não tiveram execução integrada CI Python GitHub comprovada**.

**Pedido Android:** adicionar JUnit `A,A,B_ocr,B_ocr,B_ocr` com um mesmo card contínuo após 7,5s, em paralelo a `A,A,MAP,MAP,B,B` e dois cards reais rápidos sem transição. Decisão de produto explícita: se não existe prova de troca de tela/identidade visual, apresentar na janela `valores possivelmente alterados — confira`, sem emitir segunda notificação como nova oferta; ou documentar e medir taxa de falso segundo alerta. Não prometer detectar todas as ofertas sem transição se essa segurança for escolhida. Nunca autoaceitar/rejeitar; motorista decide.

## Bloqueio E2E do emulador PR #35/#36 explicado pela trava temporal

- `LiveCaptureService.consumeFrame` anota `frameAcquiredAt` antes de `startedAt` do OCR. O callback contabiliza `ocrCompleted()` **antes** de `CaptureFrameFreshness.isFresh(frameAcquiredAt, elapsedRealtime(), MAX_FRAME_AGE_MS)`; quando a idade passa de **3.000 ms**, marca `staleOcrFrame()` e **não chama `evaluate()`**.
- PR #35 run 43082257185: 2 OCR com p50 **5.685 ms**, p95 **12.359 ms**, 0 contextos, 0 avisos. PR #36 run 43085204871: 2 OCR, p50 **4.976 ms**, p95 **9.441 ms**, 0 contextos, 0 avisos, compilação OK, E2E **FAIL**. Como **cada uma das duas amostras** ultrapassa 3.000 ms (p50 de posto mais próximo com n=2 equivale ao menor valor), e frame adquirido precede a medição de OCR, **ambos os callbacks são necessariamente tratados como obsoletos se a mesma sessão está ativa**. O filtro antiatraso explica 2 OCRs concluídos mas 0 contexto, sem culpar o classificador ou a 99. O E2E precisa expor `discardedStaleOcrFrames` para confirmar que esse é o estágio exato no dispositivo.
- **Não sugerir desligar proteção**: oferta de 10 segundos pode expirar enquanto OCR processa. Otimizar cold start/escala sem perder dígitos, analisar cronograma de OCR e testar metas de latência do telefone, separadas do emulador. No teste fictício pode pré-aquecer ML Kit sem fabricar aprovação ou reduzir guardas.
- PR #37 run 43087090925 constava **CANCELLED**, não aprovado. Precisa de CI no novo SHA antes de propor APK de janelinha como confiável.

## Auditor de diagnóstico v3

O PR #37 muda exportação voluntária para `vexo-live-capture-diagnostic-v3`, adicionando `discardedStaleOcrFrames`, `offerGateHeldFrames`, `candidatesWithout99Logo` ao v2. `live_diagnostic_audit.py` passou a admitir **apenas** conjuntos exatos dos schemas v1/v2/v3, preservando os oito contadores nested do v2 e recusando novos campos privados. Verifica que stale ≤ OCR concluído, candidatos sem logo/retidos ≤ candidatos de oferta, e leituras com evidência ≤ concluídas menos descartadas. `compare_live_diagnostics.py` compara v3 contra v3 apenas condicionalmente (nunca inventa ID de sessão). **12 testes v3 escritos** em `tests/test_capture_diagnostic_v3.py`; falta execução no CI Python/execução integral.

**Controle de privacidade:** nenhum APK, vídeo, ZIP, print, texto OCR, número financeiro real, rota, endereço, identificador de passageiro, hash real de card ou token foi enviado pelo auditor. Nenhuma mudança em Android, Gradle, workflows ou main; branch exclusiva `feature/ocr-quality-audit` (PR draft #7).
