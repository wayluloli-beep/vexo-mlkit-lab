# Revisão 09 — Janela flutuante PR #35/#36/#37 e gate Java real

**Data:** 2026-11-11. **Auditor:** Agente 3, independente. **PRs lidos:** #35 `247eb5ca`, #36 `1822032d`, #37 **`0d1b42b57f1d1234985b4f5322194f2610ab75f8`**. Branch auditada e dados de exemplos são totalmente sintéticos; NENHUMA gravação privada 99, OCR bruto, valor real, rota ou imagem foi copiada.

## Evidência CI executada

[Ações de segurança 43087535105](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43087535105): **139/139 testes sintéticos de segurança Python PASS**, 1 teste antigo skipped sem Android na branch. Na mesma execução, `overlay_optin_review.py` leu a fonte original de três PRs em worktrees **read-only**:

| Versão / SHA | Auditoria de 8 contratos | Bloqueios estáticos |
| --- | --- | --- |
| PR #35 `247eb5ca` | **6 PASS, 2 FAIL** | ocultação antiga podia remover overlay após reinício; opt-out não removia imediatamente |
| PR #36 `1822032d` | **7 PASS, 1 FAIL** | corrigiu hide com generation, ainda falta opt-out imediato |
| PR #37 `0d1b42b5` | **8 PASS, 0 FAIL** | nenhum dos 8 contratos ausente na inspeção de fonte |

**Contratos PR37:** overlay OFF por padrão, ativação voluntária via Settings.canDrawOverlays + toggle próprio, TYPE_APPLICATION_OVERLAY, FLAG_NOT_TOUCHABLE/NOT_FOCUSABLE/SECURE, `alpha=0.76`, apenas uma janela gerenciada na instância, sem invocar cliques/Acessibilidade, STOP invalida epoch e remove, hide enfileirado guarda `overlayGeneration` sob `sessionLock`, opt-out pede hide sem encerrar captura. **PASS estático não demonstra que toques na 99, FLAG_SECURE, cobertura do OCR ou remoção em todos aparelhos funcionam**.

**Android 12+ e toque:** doc oficial <https://developer.android.com/about/versions/12/behavior-changes-all#untrusted-touch-events>: uma janela TYPE_APPLICATION_OVERLAY é *não confiável*, e toques transmitidos atrás dela são permitidos na exceção de opacidade suficientemente baixa, máximo **0.8 por padrão**. PR37 usa 0.76, portanto atende o limite fonte para **uma janela**; outra sobreposição simultânea pode elevar a opacidade combinada e bloquear os toques. Testar parada, permissão, opt-out, botão da 99 que fique sob card, fabricante/Android 15 em veículo **PARADO**, sem desativar proteção Android em ADB.

## Prova usando o Java REAL do Vexo, não um modelo Python

O CI compilou `app/src/main/java/com/vexo/mlkitlab/OfferEpisodeGate.java` diretamente do PR37 com `javac` ao lado do `OfferGateSecurityHarness.java` do Agente 3; executou com `java`, sem Android SDK/ML Kit ou dados privados. **14 cenários passaram**: primeira leitura não alerta, duas idênticas confirmam, vários frames do mesmo card não duplicam, uma leitura UNCERTAIN entre duas completas tolerada, duas UNCERTAIN desarmam, prazo 5,5s, mapa precisa de duas confirmações, mudanças rápidas não geram alerta, terceiro valor igual do fingerprint novo valida a política atual.

**REVIEW_REQUIRED (fato do código, não erro de execução):** a sequência sintética `A@1000`, `A@2000` (alerta A), `B@10100`, `B@11100`, `B@12100` **gera alerta B** embora não exista transição MAP/MAP nem evento explícito de expiração. É o novo rearmamento deliberado da PR37: **3 observações de outro fingerprint após 7,5s**. Isso pode ser uma segunda solicitação legítima, mas também três leituras erradas repetindo o mesmo número enquanto o card A persiste. Nenhum dos 14 cenários prova qual delas ocorreu em gravação real.

**Recomendação P1:** manter a opção de detectar corrida nova rapidamente, mas testar estes contraexemplos com OCR sintético: A permanece visualmente por >=15 s e o OCR oscila `A,A,B,B,B` depois de 7,5s → **no máximo 1 alerta nesse episódio real**; solicitação nova B sem mapa por poucas dezenas de segundos → alvo do novo recurso com zero confusão; EXPIRADA durante A ou B → nenhum alerta depois; overlay obscurece botão de Aceitar → nunca retirar guardas para forçar alerta. Sem mecanismo externo que confirme transição visual, exigir distinção de identidade no produto ou rotular novos alertas como **não confirmado** e bloquear sequência numérica obviamente instável. **Não afirmar** que três leituras iguais do OCR provam viagem diferente.

## E2E Android ainda pendente

O build/junit do PR #36 foi SUCCESS, mas [E2E Android 35 do mesmo SHA](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43085204871) **FAIL**. No PR #35 o emulador mostrou 21 frames, 2 OCR, **0 candidato/0 aviso**, p95 12.359ms em duas amostras, que excede o filtro de idade de 3s. **Não diminuir proteção TTL** apenas para obter verde; precisa investigar por que OCR é muito lento no emulador, efeito do overlay e candidatos pós-STOP, com diagnóstico de contadores sem OCR bruto. O [PR #37 CI 43087339008](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43087339008) **ainda estava em andamento na consulta do auditor**; nenhum APK #37 homologado.

## Necessário antes de usar no carro

- Permissão independente de sobreposição + consentimento nativo MediaProjection, cada um revogável.
- Verificação manual com **carro parado**: tocar na 99 sob card, nenhuma ação automática, opt-out remove imediatamente, Android STOP remove e bloqueia callbacks atrasados após reinício; verificar FLAG_SECURE e que a janelinha não reduziu leitura da oferta ao ser capturada na tela inteira.
- Confirmar falsa segunda oferta no gate novo e validade da linha de tempo; medir tempo até alerta, não só p50 OCR.
- JSON v3 somente agregados: `offerGateHeldFrames` e `candidatesWithout99Logo` (sem texto OCR/imagem/endereços). Adicionar contrato de privacidade da v3 em CI específico.
- Nenhum merge. APK experimental é diferente de produção/homologação 99.

Os scripts desta revisão modificam exclusivamente `tools/media_projection_security/` e o workflow de segurança da própria branch, nunca o Android de outro agente.


## Adendo — CI final de PR37, privacidade v3 e notificação antiga (mesmo SHA)

**HEAD inspecionado:** PR #37 \`0d1b42b57f1d1234985b4f5322194f2610ab75f8\`. **Auditoria independente** [run 43088760620](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43088760620) registrou **156 testes sintéticos Python PASS**, 1 teste legado SKIP por falta de Android na própria branch. Harness da classe Java real: **14/14 PASS**. Overlay: **8/8 contratos de fonte PASS**. JSON de diagnóstico **v3: 7/7 contratos PASS**, verificando 29 campos superiores com valores permitidos e 8 chaves aninhadas com contadores, sem OCR bruto, coleta em RAM zerada por sessão, cópia somente por gesto. PASS heurístico, não auditoria formal de dados.

**P1 novo — notificação stale após janela perder visibilidade:** \`onCapturedContentVisibilityChanged(false)\` protege epoch/lock e limpa \`LiveCaptureState.clearCandidate()\`/oculta overlay, mas **NÃO chama \`NotificationManager.notify(NOTIFICATION_ID,notification(false))\`**. O título da notificação previamente publicada \`Vexo: confira uma possível oferta\` pode permanecer mesmo com captura oculta/sem card, até outra atualização/STOP. Scanner \`notification_visibility_review.py\` com 7 testes negativos/positivos no CI: **2 PASS / 1 FAIL** no PR37; o FAIL é \`VISIBILITY_LOSS_RESETS_ONGOING_OFFER_NOTIFICATION\`. É risco reproduzível por inspeção de código, não relato medido no aparelho. Correção sugerida: limpar estado e chamar atualização de notificação neutra no mesmo lock e após conferir sessionAlive(epoch), com teste Android oferta confirmada → visibilidade false → título neutro, mais STOP/restart sem notificação tardia.

**P0 do CI Android PR37 CONFIRMADO:** [run 43087339008](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43087339008), SHA idêntico, job compilação/JUnit **SUCCESS**, job \`ML Kit real no emulador Android 35\` **FAIL** (1/15). Erro de \`LiveProjectionConsentE2eTest\`: **31 frames, 3 OCR concluídos, 0 alertas, contextOffer=0, contextUncertain=0, contextRejected=0, financialGuardBlocked=0, waitingStableReads=0**, janela visível; OCR p50 **4.999ms**, p95 **7.501ms** (3 amostras). Limite de frescor atual \`MAX_FRAME_AGE_MS=3000\` desde aquisição; com 3 latências OCR e p50 acima de 3s, pelo menos duas inferências concluíram depois desse prazo. A origem mais provável dos contadores de contexto em zero é descarte antes de \`evaluate()\`; confirmar com \`discardedStaleOcrFrames\` agregado. **Não concluir que TODOS os três frames foram descartados** sem o contador; não relaxar TTL para fabricar aprovação. Teste E2E com demo visível após o warmup e frame novo capturado, separando inferências stale, retornos de ML Kit e tempo até candidato/alerta.

**P1 rearmamento** do Java confirmado no harness: segundo alerta B sem MAP após 7,5s + 3 leituras estáveis, mesmo que um único card visual A continue em tela e OCR sistematicamente erre três vezes; falta prova de troca de episódio. Solicitar contraexemplo JUnit de A persistente e rearmamento conservador, em colaboração com Agente 2.

**Decisão de gate de segurança:** **BLOCK para homologação de APK #37 e uso em movimento**. A compilação, 8/8 de overlay e 7/7 de privacidade de fonte **não substituem** E2E vermelho, alerta persistente, riscos de segundo alerta e testes reais de toque/opt-out Android 15. Sem merge, sem retirar proteção financeira/STOP e sem copiar vídeos privados.
