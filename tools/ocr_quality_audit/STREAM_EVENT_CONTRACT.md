# Contrato do fluxo sintético de eventos OCR — Vexo MediaProjection

**Versão:** `vexo-stream-events-v1` (auditoria Python da branch `feature/ocr-quality-audit`). Só para fixtures e testes locais/sintéticos. Este contrato **não** permite coletar OCR bruto, prints, perfis, endereços ou trajetos da 99.

## Entrada do auditor

O agente Android ou o Agente 3 pode gerar um JSON com a estrutura abaixo, apenas com identificadores *opacos fictícios* atribuídos pelo fixture de teste:

~~~json
{
  "schema": "vexo-stream-events-v1",
  "events": [
    {"kind": "start", "epoch": 1},
    {"kind": "frame", "epoch": 1, "seq": 1},
    {"kind": "inference_start", "epoch": 1, "seq": 1},
    {"kind": "inference_end", "epoch": 1, "seq": 1},
    {"kind": "callback", "epoch": 1, "seq": 1, "context": "OFFER_CANDIDATE",
     "group": "fixture-A", "notified": true, "ui_applied": true,
     "guard_blocked": false, "unsafe_financial": false, "inference_ms": 120,
     "roi_passes": 0, "history_written": false},
    {"kind": "stop", "epoch": 1}
  ]
}
~~~

Os únicos `kind` válidos são `start`, `frame`, `inference_start`, `inference_end`, `callback`, `stop`. Em callback, `context` é `OFFER_CANDIDATE`, `NON_OFFER` ou `UNCERTAIN`. Os demais campos admitidos são `epoch`, `seq`, `group`, `guard_blocked`, `notified`, `history_written`, `unsafe_financial`, `ui_applied`, `inference_ms` e `roi_passes`. Qualquer campo extra, como `rawText` ou `address`, **provoca rejeição**, assim como tipos inválidos. `group` admite somente um token fictício ASCII de até 64 caracteres, **nunca um valor extraído do OCR**. Limite de 20 mil eventos/2 MB.

- `epoch`: incrementado em cada nova sessão autorizada; não é token Android de MediaProjection.
- `seq`: contador de frame monotônico dentro da sessão; callbacks referenciam um frame observado.
- `ui_applied`: somente `true` se um resultado OCR realmente atualizou o estado visível; precisa ser instrumentado pelo agente Android. O `false` padrão **não prova** que uma interface real descartou callbacks.
- `inference_start/end`: opcionais para manter retrocompatibilidade, mas **obrigatórios para demonstrar uma inferência em andamento por vez**. Sem esses eventos não afirmar que a concorrência foi validada.
- `group`: identidade *de fixture* atribuída antes da leitura, para medir repetição; não representa uma identidade de oferta real inferível por preços/km ou hash do OCR.
- `guard_blocked` e `unsafe_financial`: registrar o resultado da guarda e a presença de campo financeiramente inseguro; na ausência, defaults conservadores apenas para fixtures.
- `history_written`: na Fase 1 não deve haver salvamento automático, nem mesmo para uma oferta candidata.

## Executar no próprio repositório

`python tools/ocr_quality_audit/stream_check.py /caminho/local/fixture.json`

O programa devolve **apenas contagens agregadas e posições dos eventos com violações**:
- código 0: JSON válido, sem violações detectadas;
- código 1: JSON válido, porém violação temporal/financeira encontrada;
- código 2: schema inválido, conteúdo extra ou entrada ilegível.

Testes locais sem APK:

`python -m unittest discover -s tools/ocr_quality_audit/tests -p 'test_stream*.py' -v`

A auditoria detecta duplicação de aviso, alerta de mapa/post/UNCERTAIN, callback aplicado após Stop, callback antigo sobrescrevendo UI nova, callback sem frame, resultado duplicado e inferências simultâneas. Não pode comprovar consentimento nativo, compatibilidade com a 99, temperatura/bateria ou liberação real de buffers. Essas responsabilidades exigem instrumentação Android e auditoria do Agente 3.

## Regras de integração

Não colocar fixtures da 99 real em CI. Gerar somente telas fictícias no próprio app/emulador. Em `Stop`, invalidar epoch antes de liberar MediaProjection e descartar resultados de ML Kit que acabarem depois. Resultado ambíguo não pode gerar análise financeira confirmada nem aceitação/recusa automática. No Android 14+, pedir consentimento por sessão, respeitar `onStop` e `FLAG_SECURE` conforme https://developer.android.com/media/grow/media-projection.
