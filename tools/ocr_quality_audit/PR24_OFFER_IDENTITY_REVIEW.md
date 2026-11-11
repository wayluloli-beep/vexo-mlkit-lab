# PR #24 — auditoria temporal do identificador de oferta (reprodução sintética)

**Escopo:** revisão independente de `LiveCaptureService.evaluate()` da branch `fix/mediaproj-stop-resize-guards`, baseada no PR #23. Não é captura de tela real nem correção Android.

## Falha reproduzível no modelo do código atual

O Android exige 2 leituras consecutivas do mesmo fingerprint e evita nova notificação desse fingerprint por `NOTIFY_INTERVAL_MS = 25000`. Fingerprint concatena modalidade, preço, km e tempos, sem uma identidade de oferta verificável. `evaluate()` reseta `lastFingerprint` e `consecutive` ao encontrar mapa/UNCERTAIN, mas mantém `lastNotified` e `lastNotificationAt`. Dois casos opostos:

1. **Oferta A permanece visível por mais de 25 segundos:** após o cooldown, o mesmo fingerprint pode emitir um **segundo alerta** para a mesma oferta (duplicação).
2. **Oferta A → mapa → oferta B com os mesmos números, dentro de 25 segundos:** após duas leituras iguais de B, o `lastNotified` de A pode **suprimir o primeiro alerta da B**, porque compara valores, não identidade da nova oferta.

O `alert_policy_audit.py` modela as condições observáveis desse algoritmo com tokens totalmente artificiais. Os grupos verdadeiros são identidades atribuídas pelo fixture humano; NÃO são gerados pelo OCR. `tests/test_alert_policy_audit.py` acrescenta **7 testes executados localmente, 7 PASS**, cobrindo ambas as falhas, controle com números diferentes, duas ofertas idênticas sem transição evidente, leitura única, UNCERTAIN e relógio regressivo. Os contadores não exportam grupos nem valores.

**Cuidado:** isso demonstra um defeito **lógico na política modelada**, não que o defeito já tenha acontecido em uma corrida real, nem comprova detecção perfeita de identidade por MediaProjection.

## Critérios sugeridos para correção Android

- Se a mesma oferta ativa segue visível por minutos, **no máximo um alerta por ciclo de vida da oferta**, sem permitir uma nova notificação só porque passaram 25 segundos.
- Uma transição de tela inequivocamente confirmada (por exemplo, mapa puro por múltiplos frames antes de outro card) permite iniciar um novo ciclo de oferta **mesmo com números idênticos**; a janela de cooldown não pode suprimir o novo ciclo só por valor.
- Uma única leitura UNCERTAIN/mapa de um OCR ruidoso **não é prova de troca de card**. Exigir histerese de estado com evidências; separar OFF/UNKNOWN/ACTIVE para não multiplicar alertas.
- Se dois cards apresentam números idênticos sem nenhuma prova de transição ou identidade adicional, **não é possível provar que são ofertas distintas apenas pelos campos**. Registrar ambiguidade; nunca afirmar 100% de deduplicação sem sinais reais.
- Não guardar OCR bruto, perfis, rotas, endereços, capturas ou tokens de projeção como identificadores, nem aceitar/recusar corrida automaticamente. O motorista é quem decide.
- Testar no emulador com app sintético: card durando 60 s; A→mapa claro→B idêntica; A→1 frame ilegível→A; A→B igual sem intervalo (ambíguo); Stop durante inferência; 2 sessões distintas. Instrumentar só contadores agregados `group` de fixture, alerta, frame/epoch e p95.

**Responsabilidade:** correção de `LiveCaptureService` é do Agente 1 na branch Android; o auditor não modifica Android/Gradle/workflows/main. Os testes aqui executam sem APK ou dados da 99.
