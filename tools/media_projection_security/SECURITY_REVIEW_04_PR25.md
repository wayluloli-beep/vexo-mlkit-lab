# Revisão 04 — PR #25: notificações por episódio e STOP

Data: 2026-11-11. Auditoria independente do Agente 3 em leitura somente de código.

- PR: https://github.com/wayluloli-beep/vexo-mlkit-lab/pull/25
- Branch: `fix/live-offer-episode-dedup`
- SHA auditado: `cb36bcbc4266bd87f0c26dba486da289ae382188`
- Serviço (blob): `dc7c4f379a1aa0a2adbda71df7d29c303ddadb35`
- CI auditor: https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43060550705
- CI Android: https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43058418419

## Segurança e limpeza de notificações

- **56/56** casos sintéticos do auditor Python PASS.
- **23/23** verificações estáticas do PR #25 PASS: 13 contrato/Manifest, 2 onStop/resize, 1 orçamento ImageReader, 3 ordenação, 4 publicação/limpeza de candidato protegida por lock.
- A chamada `LiveCaptureState.clearCandidate()` e o `NotificationManager.notify(..., notification(false))` estão sob `synchronized(sessionLock)`, depois de `sessionAlive(session)`. Já `onStop` invalida `active` e incrementa `epoch` sob o mesmo lock. A revisão não encontrou novo caminho de notificação **após** a invalidação; isto é um contrato de fonte, não prova de concorrência no Android.
- `LiveCaptureState.clearCandidate()` limpa o candidato e altera o texto de status sem encerrar a sessão.
- `OfferEpisodeGate` é uma máquina de estado em RAM com `synchronized`, sem relógio, com um alerta por episódio confirmado, permitindo alertar valores iguais depois de transição de contexto explícita.

## Atenção P1 / pedido ao Agente 2 (qualidade, não vulnerabilidade explorada)

`LiveCaptureService.evaluate()` envia qualquer texto que **não** for `OFFER_CANDIDATE` a `clearCandidateIfCurrent()`, incluindo `UNCERTAIN`, falha isolada do parser e `FinancialGuard` que se abstém. O helper chama `episodes.nonOffer()`. **Dois frames OCR sucessivos incertos** podem assim encerrar um episódio genuíno e os dois próximos frames válidos dispararem **alerta duplicado da mesma oferta**. É uma consequência plausível da política de código; não há reprodução em tela real nem medição de incidência.

**Teste solicitado:** sequência artificial `offer(A), offer(A), UNCERTAIN, UNCERTAIN, offer(A), offer(A)` deve manter um único alerta; e `offer(A), offer(A), MAP claro, MAP claro, offer(B)` pode abrir episódio novo inclusive com valores idênticos. Não transformar ausência de leitura confiável em certeza de ausência de oferta. Dois frames sem texto não são automaticamente dois frames de mapa. Também testar sobreposição de bolha/PiP que obstrui dados, sem inventar valores financeiros.

Este ponto é do domínio de qualidade de OCR/identidade do Agente 2; o Agente 3 não alterou parser/Android/branches alheias. Solicitar correção na própria branch Android, teste sintético e revisão OCR.

## Próximo bloqueio para liberar APK

Falta prova **MediaProjection real** no emulador/dispositivo autorizado: consentimento do sistema, FGS e `ImageReader` capturando pixels fictícios da `DemoOfferActivity`; STOP enquanto ML Kit trabalha; callback tardio, troca de apps, tela protegida e resize/falha injetada. O teste de OCR direto da View não substitui essa prova.

Sem APK aprovado, sem merge, sem imagens/tokens/endereços enviados ao GitHub.
