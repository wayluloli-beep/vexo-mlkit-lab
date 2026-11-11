# Vexo 0.4 — ensaio de MediaProjection sem usar a 99

> Critério: é protótipo experimental. A compilação e os testes de imagens sintéticas **não** garantem que uma sessão MediaProjection funcione, que a interface da 99 seja capturável ou que o OCR acerte todas as corridas.

## O primeiro teste útil e seguro no próprio telefone

1. Instale o `Vexo Captura 0.4 (teste)` **ao lado** do leitor `Vexo OCR 0.3.5` (applicationId distinto). Não desinstale o leitor.
2. Abra **MediaProjection • ler tela com autorização (experimental)**.
3. Toque **Autorizar e iniciar leitura de tela**. O diálogo é do Android: é o motorista quem escolhe o escopo (se aparecer, selecionar somente o aplicativo Vexo ou a tela inteira, evitando exposição involuntária). Sem autorização, nada começa.
4. Abra **Abrir oferta fictícia para conferir captura**. Deixe essa tela visível por pelo menos duas leituras (o código limita a uma tentativa por 1,4 s).
5. Volte ao controle e toque **Atualizar resultado**. Valores visuais fictícios: `99 Moto`, `R$40,70`, multiplicador `2,8x`, embarque `9 min/3 km`, viagem `24 min/11,8 km`. O texto **Aceitar** da demonstração é uma imagem visual, sem comando.
6. Toque **Parar captura agora** e confirme que o status do sistema e a notificação/indicador de projeção encerraram; repetir a sessão requer NOVA autorização.
7. Opcional: durante uma sessão de teste com dados fictícios, girar o aparelho e bloquear/desbloquear para observar interrupção, fechamento de recursos e ausência de candidato tardio.

## Coisas que NÃO são aceitas como prova de conclusão

- CI de `assembleDebug` e teste de parser com Bitmap gerado são importantes, mas não provam a autorização nativa e fluxo de frames.
- O teste `DemoOfferOcrIntegrationTest` tira uma imagem em RAM da **View do próprio Vexo**, sem MediaProjection. É uma contraprova da legibilidade do layout, NÃO uma validação de captura entre aplicativos.
- Um único print real lido 100% não equivale a precisão 100% em produção.
- Não publicar prints de corridas reais, endereços, dados de passageiros, transcrições OCR, tokens ou permissões em GitHub.
- Não usar Accessibility para automatizar a 99; motorista continua tomando todas as decisões.

## Dados de aceitação (agregados, sem conteúdo sensível)

- Consentimento: concedido/negado, tipo de janela escolhido voluntariamente.
- Serviço: iniciou foreground, notificação PARAR/controle visível e `onStop` limpo.
- Captura demo: frames recebidos, campos da oferta fictícia reconhecidos, latência p50/p95, número máximo de inferências simultâneas (meta = 1).
- Ciclo de vida: STOP durante OCR, callback tardio descartado, resize sem reader pendurado, sessão nova com token novo.
- Segurança: scanner de contrato + memória + temporal P0 sem bloqueio, CI Java e Android emulador aprovados; captura real 99 requer teste separado legítimo e consentido.

**Referência:** Issue #21, PRs #22 (auditoria), #23 (MVP) e #24 (guardas+demo).
