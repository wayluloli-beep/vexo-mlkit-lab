# Agente 3 — Segurança MediaProjection (Vexo)

**Escopo exclusivo:** `tools/media_projection_security/` e workflow específico de segurança. Nenhuma edição em app, Gradle, `tools/ocr_quality_audit` ou branches dos Agentes 1/2. Sem dados privados ou imagens.

## Como executar sem APK

```bash
python -m unittest discover -s tools/media_projection_security/tests -p "test_*.py" -v
python tools/media_projection_security/check_contract.py --root .
# Quando houver código MediaProjection, exigir implementação:
python tools/media_projection_security/check_contract.py --root . --require-capture --json
```

O checker inspeciona **somente arquivos de texto Java e AndroidManifest**, não carrega imagens, transcrições, screenshot, JSON de corridas nem tokens. Na branch `main` sem captura, emite `SKIP` para contrato de app, mas os testes de fixtures positivas/negativas continuam rodando. Na branch Android com captura presente, `FAIL` interrompe o CI se faltar requisito estático.

## Snapshot de arquitetura verificado (11/11/2026)

Base: `feature/media-projection-lab` no commit `d793d0115e6d140165da284ad347e273ec225f70`.

| Item | Evidência | Estado |
|---|---|---|
| Consentimento por clique | `app/src/main/java/com/vexo/mlkitlab/LiveCaptureActivity.java` usa `createScreenCaptureIntent()` | Código de entrada presente; sem teste real |
| Serviço captura | `LiveCaptureActivity.java` invoca `LiveCaptureService.class`, mas classe não consta da árvore | **P0 bloqueado** |
| Declarações | `app/src/main/AndroidManifest.xml` não declara nova Activity, serviço, tipo FGS ou permissões | **P0 bloqueado** |
| Limite de frames | `CaptureThrottle.java` faz gate sincronizado | Implementado isoladamente; sem integração à captura |
| Token único, callback, limpeza, OCR em tela | Serviço ainda ausente no snapshot | Não demonstrado |
| Compatibilidade 99 | Nenhum teste autorizado de MediaProjection nessa app | Não demonstrado |

### Cinco ameaças e mitigações
1. **Início sem foreground e sem consentimento:** exigir duas permissões FGS, tipo `mediaProjection`, consentimento do sistema **a cada nova sessão**, promover serviço a foreground antes do `getMediaProjection`. Não guardar o `Intent`/token.
2. **Sessão inválida:** somente uma chamada por sessão a `getMediaProjection` e `createVirtualDisplay`; `registerCallback` antes do display; em `onStop` invalidar `sessionEpoch`, cancelar entrega de callbacks antigos e liberar recursos. Não reiniciar no boot nem após kill.
3. **Fuga de recursos e throttling:** `ImageReader` com `maxImages >= 2`, `acquireLatestImage()`, fechamento garantido de `Image` em `finally`, sem fila de OCR, máximo 1 inferência simultânea. Liberar `VirtualDisplay`, `Surface`, `ImageReader`, `TextRecognizer`, thread/handler e notificação. Medir temperatura, p95 de inferência, heap e bateria no emulador/dispositivo de teste.
4. **Troca de janela/rotação/lock:** `onCapturedContentResize` chama `VirtualDisplay.resize` e `setSurface`, nunca segunda `createVirtualDisplay`. `onCapturedContentVisibilityChanged(false)` suspende inferência quando janela capturada deixa de estar visível. `onStop` encerra ao bloquear/usar chip de sistema; tratar fechamento pelo sistema sem restaurar token. A troca de app após escolher **tela inteira** não garante privacidade; preferir janela de app autorizada pelo usuário e advertir claramente.
5. **Conteúdo protegido ou privado:** respeitar `FLAG_SECURE`, zerar buffers transitórios, não registrar conteúdo bruto em `Log`, Analytics, Crashes, GitHub ou arquivos. Ausência/black frame deve resultar em **nenhum dado**, não em preço zero. Não acessar eventos de tela via Accessibility nem interagir com Uber/99 para aceitar/recusar.

### Matriz de teste e limites

| Camada | Casos | Evidência que pode provar |
|---|---|---|
| Python offline (nesta branch) | Manifest/permissões; Activity/service existentes; exported; FGS; callback; uma callsite; Image finally; release; boot; persistência; acessibilidade | Regressão de contratos **estáticos**, usando fixtures artificiais |
| Android emulador API 34/35/36 (requisitar Agente 1) | autorização/negação; segundo token; STOP durante OCR; rotação; app-share; lock/chip; mudança de visibilidade; tela `FLAG_SECURE`; kill | Comportamento real de APIs Android, com app sintético próprio |
| Métricas de perfis fictícios | frames vistos/descartados, inferências simultâneas, p50/p95, memória, energia, callbacks tardios | Desempenho; NÃO significa precisão em ofertas da 99 |
| Validação 99 legítima e consentida | Somente após CI, revisão humana e acordo de escopo | Compatibilidade real, ainda desconhecida |

### Restrições da auditoria estática

Este script **não é um parser Java completo**: um `PASS` sinaliza presença textual das salvaguardas, **não garante** ordem correta, idempotência, ausência de vazamentos, resistência a corridas de threads, consentimento real ou segurança jurídica. A verificação de um único callsite não prova unicidade por sessão em runtime. Uma `FAIL` precisa ser investigada no código real; padrões novos podem exigir atualização do scanner. Sem vínculo automático de fixtures Python ao comportamento do app até o Agente 1 disponibilizar a implementação.

## Requisitos oficiais e fontes

- MediaProjection: https://developer.android.com/media/grow/media-projection
- Android 14 (API 34): https://developer.android.com/about/versions/14/behavior-changes-14
- Android 15 / proibição BOOT_COMPLETED (target 35+): https://developer.android.com/about/versions/15/behavior-changes-15
- Android 15 QPR1 chip + auto-stop ao bloquear: https://developer.android.com/about/versions/15/behavior-changes-all
- Android 16 (API 36) deve passar pela mesma suíte: https://developer.android.com/about/versions/16/behavior-changes-16
- `ImageReader.acquireLatestImage`: https://developer.android.com/reference/android/media/ImageReader
- `MediaProjection.Callback`: https://developer.android.com/reference/android/media/projection/MediaProjection.Callback
- Proteção `FLAG_SECURE`: https://developer.android.com/reference/android/view/WindowManager.LayoutParams#FLAG_SECURE

**Coordenação:** Issue #21 (missão) e Issue #8 (central). PR draft obrigatório, sem auto-merge.
