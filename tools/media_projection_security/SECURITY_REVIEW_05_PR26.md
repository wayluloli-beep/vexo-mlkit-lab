# Revisão 05 — PR #26: captura real no emulador ainda bloqueada

Data: 2026-11-11. Auditoria independente Agente 3, leitura somente de código, workflow e logs.

- PR: https://github.com/wayluloli-beep/vexo-mlkit-lab/pull/26
- Branch: `feature/mediaproj-runtime-proof`
- HEAD auditado: `c94d0d8d76c624c069bac081a1c9d3028d759c76`
- CI Android de verdade: https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43059851985
- CI do auditor: https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43062414960

## Resultados separados (não misturar)

1. **Compilação / JUnit:** SUCCESS no job `Parser, segurança e APK` do PR #26.
2. **Emulador API 35:** FAILURE, **1 de 15 testes**. O teste instrumentado `LiveProjectionConsentE2eTest.nativeConsentThenFakeOfferProducesRealFramesAndStops` chegou a `CAPTURA ATIVA`, estado que o serviço agora atribui somente depois de criar `VirtualDisplay`; mas falhou no assert combinado `awaitCounts(2,2,1,30000)` com mensagem `Não recebeu 2 frames, 2 leituras OCR e 1 alerta da tela fictícia durante MediaProjection`. O erro **não** identifica qual dos três contadores ficou abaixo do mínimo.
3. **Revisão estática Android PR #26:** 23 PASS (contrato/permissões, onStop/resize, orçamento pixels, ordem API, proteção de publicação/limpeza).
4. **Revisão do TESTE E2E:** 3 PASS e 4 FAIL heurísticos. O código tenta consentimento UiAutomator real, chama DemoOfferActivity fictícia e não grava screenshots privados, mas a qualidade da prova precisa melhorar.
5. **Auditor Python:** 65/65 casos sintéticos próprios PASS; isso valida a ferramenta de inspeção, **não** a captura no emulador.

## Quatro deficiências concretas da prova E2E

- `E2E_SCOPE_EXPLICIT` FAIL: `approveThroughSystemDialog()` escolhe tela inteira **somente se** encontra um dropdown textual `A single app`. Se essa string não existir, clica Start sem verificar se a demo será compartilhada. Exigir seleção de tela inteira explicitamente em emulador ou app-share da própria demo, sem bypass.
- `E2E_COUNTERS_VISIBLE_ON_FAILURE` FAIL: o assert composto não inclui `LiveCaptureState.counts()` quando falha; apenas mensagem genérica. Mostrar `frames, OCR, avisos` como contadores agregados e fictícios no relatório de falha, sem texto OCR ou imagem.
- `E2E_STAGEWISE_ASSERTIONS` FAIL: verificar isoladamente (a) frames capturados >=2, (b) OCR completados >=2, (c) alertas >=1. Uma única combinação falha sem localizar a etapa.
- `E2E_STOP_NOT_SKIPPED_BY_OCR_FAILURE` FAIL: asserts de STOP estão **depois** do assert que já falhou, portanto não foram validados nessa execução. O `finally` manda um STOP mas não verifica transição, limpeza ou callback atrasado. Usar teste independente de STOP, inclusive enquanto ML Kit ainda estiver processando.

## Diagnóstico recomendado ao Agente 1

- `frames < 2`: investigar escopo do diálogo, visibilidade, callback do ImageReader, Surface e VirtualDisplay. Não assumir que `CAPTURA ATIVA` significa frame adquirido.
- `frames >= 2` e `OCR < 2`: investigar extração Bitmap, `CaptureThrottle`, tarefa ML Kit/erro de reconhecimento; sem gravar pixels.
- `OCR >= 2` e `avisos < 1`: investigar se demo sintética é lida como contexto `OFFER_CANDIDATE`, `OfferParser`, `FinancialGuard` e política de dois frames; não remover guardas de segurança só para ficar verde.
- Após correção, exigir STOP idempotente e teste que mantém resultado atrasado inativo, mais resize/falhas injetadas.

**Estado:** PR #26 mantém sessão MediaProjection iniciada de forma plausível no Android 35, mas não comprova pipeline de leitura da demo. **APK com captura não aprovado; sem merge.**

Todos os arquivos do Agente 3 ficam em `tools/media_projection_security/` + workflow da auditoria. Sem alteração Android/OCR, sem token, captura de tela privada, endereço ou transcrição enviados ao GitHub.
