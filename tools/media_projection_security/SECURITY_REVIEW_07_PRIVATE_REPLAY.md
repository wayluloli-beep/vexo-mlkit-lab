# Revisão 07 — duas gravações privadas, ofertas vencidas, anúncios e OCR atrasado

Data: 2026-11-11. Agente 3 / auditoria independente de segurança. A coordenação registrou dois vídeos da 99 **privados** na Issue #21. **NENHUM MP4, imagem, áudio, transcrição, endereço, nome, coordenada, print ou valor de corrida foi baixado, copiado ou anexado a esta branch.** Este relatório descreve APENAS categorias e política de tempo, com `synthetic-A/B`.

## Risco do novo caso e o que está testado

- Vídeo A (apenas linha do tempo abstrata): longo período de mapa sem oferta, 1 card breve (~10 s), overlay temporário de volume, depois mapa/painel. Esperado: no máximo 1 alerta na janela válida, zero no mapa, painel e após saída.
- Vídeo B (apenas eventos abstratos): card presente no início, mapa, reaparecimento visual com **os mesmos números** (isso são dois episódios VISUAIS, **não** prova de duas corridas independentes), lista de solicitação, expiração explícita, anúncio com valor monetário. Esperado: contextualizar por episódio, não multiplicar ofertas por 8 prints; não emitir alerta depois da expiração nem sobre anúncio.
- Testar estática de prints **não** valida captura MediaProjection nem tempo de leitura. A meta <=3s para alertar um card de ~10s ainda é uma **meta não medida**, e `max_frame_age_ms=3000` aqui é um **limiar conservador proposto para modelo sintético**, não exigência Android implementada.

## Entrega concreta na branch exclusiva da segurança

`tools/media_projection_security/temporal_offer_safety.py` é um modelo independente (Python, em RAM) de segurança de avisos, com timestamps **de captura** e **de conclusão** em milissegundos fictícios, sem imagem. Módulo `tests/test_temporal_offer_safety.py` testa:

1. Contexto MAP por vários minutos → 0 alertas.
2. Um card confirmado por duas leituras válidas → 1 alerta, sem duplicar em vários frames.
3. OCR `UNCERTAIN` e overlay não provam fim do episódio, não geram novo aviso.
4. Dois episódios VISUAIS com números idênticos separados por dois MAP confirmados podem gerar dois avisos, sem afirmar identidade real das corridas.
5. Card em lista só é candidato se `financial_safe` E `actionable`, com duas leituras estáveis.
6. Sinal `EXPIRED` bloqueia aviso atrasado e exige transição visual inequívoca antes de rearme.
7. `ADVERTISEMENT` com preço NÃO é oferta.
8. Frame cuja inferência termina após prazo máximo de frescor é descartado; callback capturado antes do evento terminal também é rejeitado.
9. STOP bloqueia callback pendente; guardas financeiras não são relaxadas.
10. Falta de estado explícito de lista/expiração ou controle de idade do frame no **código Android** é relatada como `FAIL` de integração, em vez de fingir que modelo sintético está no APK.

CI `media-projection-security.yml` executa fixtures automaticamente e busca HEADs PR #29/#30 em checkout **somente leitura** para detectar a presença de três contratos de fonte. O workflow não baixa vídeo real e não modifica Android/OCR/main.

## Lacuna real no código Android inspecionado

Na branch Android #29, `ScreenContextClassifier.Kind` contém `OFFER_CANDIDATE, COMPLETED_TRIP, MAP_WITHOUT_OFFER, ARCHIVED_OFFER_SCREENSHOT, SOCIAL_POST_WITH_SCREENSHOT, UNCERTAIN`, mas **não** distingue `OFFER_LIST_CANDIDATE` nem `EXPIRED` como estados próprios. `LiveCaptureService.evaluate()` processa o texto reconhecido sem checar a idade da imagem no momento do aviso (capture timestamp vs completion timestamp). O `OfferEpisodeGate` tem dedup por episódio visual e `UNCERTAIN` conservador, mas não tem TTL explícito para o alerta.

**Risco tecnicamente plausível, não reproduzido no Android real:** uma imagem capturada enquanto uma solicitação ainda estava aberta pode terminar OCR só depois do aviso de expiração e gerar alerta tardio; uma palavra de expiração isolada pode ser classificada como `UNCERTAIN` e não encerrar estado. `ADVERTISEMENT` com valor isolado cai em `UNCERTAIN` nos padrões atuais, não em oferta confirmada; ainda falta regressão negativa instrumentada.

## Segurança de vídeo privado e permissões — proposta para integração

- **Não** colocar nenhum MP4, crop, frame ou transcrição com origem real no GitHub/CI/issue; usar fixtures inteiramente fictícias no repositório.
- **Replay local opcional**: o usuário escolhe arquivo por seletor de documentos do Android (SAF, `ACTION_OPEN_DOCUMENT`/`ACTION_GET_CONTENT`), com URI autorizado pelo usuário; se precisar decodificar frames, fazê-lo localmente e descartá-los em RAM após ML Kit. Não solicitar acesso indiscriminado à galeria quando picker basta; não guardar URI em histórico sem consentimento.
- **MediaProjection verdadeira**: diálogo nativo autoriza compartilhar a tela inteira ou especificamente a **janela do reprodutor** da gravação. A 99 não precisa estar aberta para reproduzir o MP4 e não deve ser apresentada como app compartilhado nessa prova. Sem contornar `FLAG_SECURE`, sem AccessibilityService, sem permissão reutilizada.
- **Áudio:** não solicitar `RECORD_AUDIO` nem capturar áudio de reprodução. O usuário só precisa de frames visuais fictícios/consentidos para o OCR. Clip de replay pode ser sem áudio.
- **No STOP ou revogação:** invalidar sessão e descartar frame, bitmap e callback pendente antes de notificar; não adicionar screenshots a logs, clipboard, analytics ou crash reports.
- **Exportação voluntária:** somente contadores e duração do episódio, sem dados de corrida. O `ClipDescription.EXTRA_IS_SENSITIVE` serve apenas para ocultar prévia do clipboard Android 13+, não cria segurança para conteúdo.
- **Expiração/anúncio:** qualquer detecção explícita deve invalidar candidato e bloquear publicação de resultado cujo frame tenha timestamp anterior ao estado terminal. Uma nova oportunidade não pode herdar o fingerprint de uma expirada nem aparecer sem revalidação.
- **Métrica por EVENTO:** 8 prints de uma oferta são 1 exemplo temporal, não 8 acertos independentes. Medir `time-to-first-alert`, alertas fora da janela, falsos positivos no mapa/anúncio, número de episódios visuais, p50/p95 OCR, contadores de frames recebidos/inferidos/pulados.

## Pedidos objetivos à equipe

**Agente 1 Android:** manter P0 de CI E2E verdadeiro e consentimento. Depois, implementar em PR próprio proteção contra OCR de frame vencido e sinais de `EXPIRED`/anúncio/lista (sem texto real nos testes), com 2+ MAP confirmados para rearmar outro episódio; testar STOP e notificação de callback tardio. **Não criar implementação nova de vídeo antes de fechar o teste de captura.**

**Agente 2 OCR:** validar com fixtures artificiais a separação entre `solicitação em lista`, `expirada`, `banner comercial monetário`, `mapa` e `card`; não classificar vídeo como dados independentes e não atribuir rótulo de 2 corridas a números reaparecendo.

**Agente 3:** revisar política proposta contra código e CI Android após integração, sem tocar branches de terceiros. Não liberar APK como aprovado até pipeline real + STOP/expiração seguros.

**Limitações:** o modelo Python e suas regressões são contrato de comportamento; **não são teste de OCR ML Kit, vídeo real, MediaProjection ou Android**. O scanner de presença de fonte é conservador/heurístico, seus PASSs não garantem implementação correta.
