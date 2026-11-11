# Revisão PR #25 — dois tipos de ausência NÃO são equivalentes

**Escopo:** auditoria independente do `OfferEpisodeGate` do PR #25 e do callsite `LiveCaptureService.evaluate()/clearCandidateIfCurrent()`. Sem alteração Android, sem testes com a 99 e sem dados privados. Reproduzido por cópia local da classe Java do snapshot `cb36bcbc4266bd87f0c26dba486da289ae382188` e pela modelagem Python sintética.

## Achado P1-A: dois frames UNCERTAIN reabrem indevidamente uma oferta existente

O serviço chama `clearCandidateIfCurrent(session)` **sempre que o texto não parece oferta, o classificador retorna algo diferente de OFFER_CANDIDATE ou o FinancialGuard se abstém**. O método chama `episodes.nonOffer()`. Essa chamada não diferencia:
- **mapa/histórico/post definitivamente sem oferta ativa**;
- **UNCERTAIN** (ex.: overlay, OCR parcial, um número oculto ou falha do ML Kit).

`OfferEpisodeGate.nonOffer()` encerra o episódio após **duas** invocações. Portanto este roteiro fictício:
`A(legível), A(legível), UNCERTAIN, UNCERTAIN, A(legível), A(legível)`
gera **2 alertas para A**, embora o mesmo card nunca tenha saído. Na cópia compilada em Java (OpenJDK 21), o probe mostrou `alerts=2, expected=1`. Não é crash/erro observado no aparelho; é um caminho lógico do código atual.

## Achado P1-B: OCR de dois valores plausíveis diferentes pode inventar novo episódio

Quando `OfferEpisodeGate.observe(next)` recebe outro fingerprint, zera `alerted=false` sem evidência de retirada do card atual. Se o OCR ler um número diferente de maneira consistente em dois frames, `A,A,B,B,A,A` pode gerar **3 alertas sobre a MESMA oferta**. O probe Java isolado encontrou `alerts=3, expected=1`. Por outro lado, uma oferta B genuína sem intervalo visível pode ter o mesmo comportamento. A política precisa declarar a escolha entre **evitar falsos alertas** e **perder troca não observável**: só os campos numéricos não resolvem identidade.

## Mudança conservadora proposta ao Android (sem invadir branch)

1. Propagar **três sinais separados** do classificador ao gate: `OFFER_CANDIDATE`, `DEFINITELY_NOT_LIVE_OFFER` (evidência de contexto forte), `UNCERTAIN` (OCR incompleto, FinancialGuard bloqueou, overlay). Dois `UNCERTAIN` **não** podem equivaler a duas evidências de que o card desapareceu.
2. Contar somente **duas observações definitivas e consecutivas** de tela não-oferta para encerrar episódio. `UNCERTAIN` suspende candidato/aviso financeiro, mas preserva o estado de deduplicação do episódio em memória; não aceita nem rejeita corridas.
3. Depois de um alerta, um fingerprint diferente na mesma sequência sem transição comprovada deve ser tratado como **identidade ambígua / revisão**, não abrir automaticamente novo episódio só com dois preços/km plausíveis. Se o app optar por notificar, documentar e medir taxa de falsos alertas.
4. Contraprovas de Android JUnit/Emulador: `A,A,UNCERTAIN,UNCERTAIN,A,A → 1 alerta`; `A,A,MAP,MAP,B,B` com números iguais → **2**; `A,A,B_errado,B_errado,A,A` na mesma tela → **1**; `A,A,1x UNCERTAIN,A,A → 1`; tela oculta ou consentimento parado → **0 novos alertas**.
5. Um frame isolado de mapa classificado equivocadamente como definitivamente não-oferta não prova ausência; prudência com histerese e testes de OCR parcial. Quando duas ofertas são visualmente indistinguíveis sem transição, reconhecer limite em vez de afirmar 100% de detecção.

## Evidência desta auditoria

- `episode_context_audit.py`: reproduz comportamento **atual** e uma política **alternativa conservadora** com identidades fictícias opacas, sem OCR/preço/rota.
- `tests/test_episode_context_audit.py`: 9 cenários sintéticos **executados localmente e 9/9 PASS** sobre modelo equivalente; inclui ambiguidade não observável e custo da abstenção. Isso NÃO é um patch de código Android nem CI Python integrado.
- Compilação isolada da classe Java copiada do PR #25: 5 probes demonstraram 2 cenários de risco (resultados acima), 3 controles com resultado esperado.
- PR #25, SHA `cb36bcbc`, GitHub Actions run `43058418419`: **2/2 jobs completed/success** (JUnit+build e ML Kit em emulador com pixels sintéticos). O CI não cobre os dois casos acima, nem comprova sessão MediaProjection concedida capturando a demo.
- **Próxima ação do Dev:** adicionar JUnit contra os dois casos, separar `uncertain()` de `nonOffer()`, reexecutar CI e demonstrar transições reais em app próprio sintético via consentimento do Android. Não liberar APK antes da revisão P0 de segurança.

Nenhum arquivo Android, workflow, main, print real ou dado de passageiro foi alterado.
