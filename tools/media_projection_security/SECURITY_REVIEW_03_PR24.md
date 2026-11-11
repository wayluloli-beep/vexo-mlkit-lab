# Revisão 03 — PR #24 de correção (MediaProjection)

Data: 2026-11-11. Auditoria independente Agente 3, em modo **somente leitura**.

- PR corrigido: https://github.com/wayluloli-beep/vexo-mlkit-lab/pull/24
- Branch auditada: `fix/mediaproj-stop-resize-guards`
- HEAD exato auditado: `9f43bf82f0d739190edda92287b9ae1cb8573645`
- Blob do serviço: `de817e7d5cd777cbc3da7409f3a9d838c319d5f7`
- CI do auditor: https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43059369937

## Achados estáticos comparativos

| Verificação | PR #23 antigo | PR #24 corrigido |
|---|---|---|
| Contrato Manifest, permissões, reader, cleanup | 13 PASS | 13 PASS |
| Invalidação imediata de sessão antes do cleanup | FAIL | PASS |
| Fechamento do ImageReader provisório em exceção de resize | FAIL | PASS |
| Limite antes de ambas as alocações ImageReader | FAIL | PASS |
| Ordem startForeground, getProjection, callback e display | 3 PASS | 3 PASS |

PR #24 total: **19 PASS / 0 FAIL**, com **51/51 casos sintéticos de regressão do próprio auditor PASS**. Nenhum resultado representa execução real da API MediaProjection.

### Como a proteção é implementada

- `onStop` chama `invalidateStoppedSession(session)` de modo síncrono, antes de enfileirar cleanup. O helper marca `stopping=true`, `active=false`, invalida `epoch` sob `sessionLock`; a publicação da oferta também usa `sessionLock`.
- `resize` mantém `ImageReader replacement` sob ownership local até o `VirtualDisplay.setSurface` retornar. Em exceção, fecha o provisório antes de invalidar a sessão.
- `CaptureDimensions.fit` limita dimensões a 4096 por lado e no máximo 6 milhões de pixels, com multiplicação `long`, e os dois leitores são alocados usando exatamente dimensões derivadas desse `fit`. Isso **limita**, mas não mede, o consumo (buffer de até 3 imagens, bitmaps intermediários e sobreposição temporária no resize).
- `getMediaProjection` e `createVirtualDisplay` têm um callsite cada; verificar unicidade por **sessão** e token em runtime.

### Correção do próprio auditor

A primeira tentativa detectou 18 PASS / 1 FAIL no PR #24: o verificador considerou `onCapturedContentVisibilityChanged`, um callback Java aninhado já fechado, como método do `ImageReader.newInstance` subsequente. Corrigido `memory_review.py` com busca da **delimitação real por chaves do método que contém a alocação** e exclusão dos corpos de callbacks encerrados. Acrescentadas duas regressões: guarda externa antes do callback continua válida; guarda colocada *somente dentro* de callback não protege alocação posterior.

### Itens ainda obrigatórios para aprovar APK experimental

1. **Sessão autorizada no Android real/emulador**: consentimento de usuário do sistema, iniciar FGS `mediaProjection`, capturar pixels de uma `DemoOfferActivity` sintética via `ImageReader`, OCR local, mostrar candidato fictício. O teste `DemoOfferOcrIntegrationTest` renderiza a própria `View` diretamente, **não** prova MediaProjection.
2. **STOP concorrente**: impedir atualização de UI e notificação após `onStop` com tarefa ML Kit pendente e callback atrasado; validar cleanup idempotente, e reinício exigindo consentimento novo.
3. **Resize com falhas injetadas**: erro em `VirtualDisplay.resize` e `setSurface` deve fechar todo `ImageReader` e não criar segundo display. Recurso deve chegar a zero.
4. **Memória, latência e temperatura reais**: coletar somente contadores agregados/sintéticos, sem imagem ou transcrição. Monitorar orçamento durante dois leitores simultâneos no resize.
5. **Separação de identidade de ofertas**: Agente 2 registrou que um card persistente pode alertar novamente após 25s, e duas ofertas com números iguais podem se confundir. Reparar e validar em branch Android separada antes de confiar em alertas, sem usar dados de passageiros.
6. Verificar app-share em API 34, 35 e 36, com consentimento renovado, tela protegida respeitada e parada por sistema.

**Status da segurança do PR #24:** sem os três P0/P1 estruturais antigos no código revisado. **Não há sinal verde para APK com captura real**, pois e2e MediaProjection, interrupção em runtime e desempenho seguem sem prova nesta auditoria.

A auditoria não edita Android/OCR/main, não produz APK, não executa merge e não usa dados reais da 99.
