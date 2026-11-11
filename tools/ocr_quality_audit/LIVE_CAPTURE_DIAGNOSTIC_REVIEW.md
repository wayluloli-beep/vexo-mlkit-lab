# Vexo 0.4 — auditor independente do diagnóstico da captura

Ferramenta **offline** que recebe somente o relatório voluntário gerado pelo botão "Copiar diagnóstico da captura" (schema \`vexo-live-capture-diagnostic-v1\` do PR #28). **Não** recebe telas, texto OCR, preço, nome, endereço, rota, token MediaProjection ou identificador de oferta. Nunca imprime de volta as strings descritivas do JSON; retorna apenas contadores, códigos de inconsistência e hipótese de etapa.

## Executar

\`\`\`bash
python tools/ocr_quality_audit/live_diagnostic_audit.py /caminho/local/diagnostico.json
python -m unittest discover -s tools/ocr_quality_audit/tests -p 'test_live_diagnostic_audit.py' -v
\`\`\`

Códigos de saída: 0 se o relatório está estruturalmente consistente; 1 se há contradições nas contagens/estágio; 2 se JSON/schema/tipos/campos são inválidos. Nunca converter uma contradição de contadores em "OCR deu erro" sem evidência. Limita o arquivo a 8 KiB; rejeita campos extras como \`rawOcr\`, campos de identidade ou conteúdo de imagem, números negativos, bool como contador e marcadores de privacidade inconsistentes.

## Funil de interpretação

1. \`framesReceived\`: \`ImageReader\` entregou pixels; não significa que a oferta da 99 era visível.
2. \`ocrAttempts\`: \`recognizer.process\` começou; não significa que finalizou.
3. \`ocrCompleted\`: callback de sucesso do ML Kit concluiu; **não comprova leitura correta**.
4. \`offerContextCandidates\`, \`screenContextUncertain\`, \`screenContextRejected\`: classificação de texto (contexto), não contagem de ofertas únicas.
5. \`financiallyUnconfirmedFrames\`: a \`FinancialGuard\` recusou usar dados da oferta; é uma **trava de segurança**, não deve ser removida para fabricar alertas.
6. \`awaitingTwoStableReadings\`: episódios em espera de confirmação; é contador de eventos, **não** quantidade de ofertas distintas.
7. \`offersAlerted\`: contador de candidatos publicados em RAM, **não é taxa de acerto** nem prova de notificação recebida pelo motorista.

Caminhos típicos, todos **hipóteses**, não prova de causa:

| Evidência | Interpretação conservadora |
|---|---|
| 0 frames | captura ainda não entregou pixels |
| frames > 0, 0 OCR | pipeline/limite de inferência não iniciou |
| OCR > 0, 0 candidatos | nenhum contexto de oferta classificado no que foi efetivamente lido |
| candidatos > 0, todos barrados | FinancialGuard recusou todos os candidatos |
| candidatos válidos, esperando confirmação | a estabilidade/identidade do episódio pode não estar comprovada |
| candidato válido, 0 avisos e sem espera | causa não determinável só pelos contadores |

**O run PR #27 mostrou 19 frames, 2 OCR concluídos, 0 avisos.** Esses números sozinhos **não permitem atribuir a falha a classificador, guarda ou estabilidade**. O PR #28 adiciona os contadores que permitem estreitar a hipótese. Mesmo com os contadores, não dá para provar identidade visual do card sem teste E2E instrumentado. Não publicar OCR bruto para "resolver" a lacuna. Testar apenas a DemoOfferActivity fictícia no emulador e manter autorização do sistema.

### Estado / limitação

Os 11 testes sintéticos do verificador foram **executados localmente e passaram**; não foi executada a suíte Python completa no GitHub até que exista integração explícita. Não tocamos no código Android, em Gradle, workflows, main ou na branch dos outros agentes. Repo com PR #7 continua draft. O CI do PR #28 e #29 deve ser conferido separadamente. Nada aqui certifica precisão da 99, corridas reais ou um APK seguro.


## Evidência E2E nova: PR #28 e PR #29 (11/11/2026)

Não reproduzir OCR textual, imagens ou screenshots. Logs públicos do **próprio laboratório fictício**:

- **PR #28**, run [43065445709](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43065445709) **FAIL** no job de emulador: \`frames=24\`, \`OCR iniciado=1\`, \`OCR concluído=1\`, \`falhas OCR=0\`, \`janela=visível\`. Teste exigia 2 OCR. **Nem houve segunda leitura concluída**; portanto não é possível culpar classificador ou FinancialGuard por essa execução.
- **PR #29**, run [43066818185](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43066818185) **FAIL** no job de emulador, com Gradle/JUnit/build no outro job **SUCCESS**. Resultado com separação de etapas: \`frames=29\`, \`OCR concluído=2\`, \`avisos=0\`, \`janela=não informada\`, \`contextOffer=1\`, \`contextUncertain=1\`, \`contextRejected=0\`, \`financialGuardBlocked=0\`, \`waitingStableReads=1\`. Então **um callback** chegou como candidato e **outro** ficou incerto; **não houve duas leituras válidas iguais**. Guarda financeira não foi a causa de rejeição do candidato contabilizado nessa rodada. A origem do UNCERTAIN (texto ausente, outra tela, overlay, OCR parcial) **continua desconhecida**.

**Código de teste novo do auditor:** \`frame_starvation_audit.py\` e \`tests/test_frame_starvation_audit.py\` com **7 testes locais PASS**. Cenário fictício: 24 frames chegam enquanto um OCR de 5 s mantém o gate ocupado; se a tela depois fica estática e não gera mais frames, o app termina com **1 OCR iniciado**, pois o serviço adquire \`ImageReader\` somente sob callbacks de frame. Um novo frame após OCR concluir permite a segunda leitura. O exemplo é explicação de possibilidade arquitetural, **não medição** que 5 s ocorreu no emulador. Somado aos **12 testes locais** do verificador de JSON, são **19/19 PASS nesta entrega**, não suíte completa do projeto nem CI Python GitHub.

### Pedido concreto ao Android

1. Teste E2E de sessão MediaProjection, em demo própria fictícia, deve usar **evidências separadas**: frames > 0, OCR iniciados/concluídos, contexto reconhecido, guarda bloqueada e **dois callbacks \`OFFER_CANDIDATE\` estáveis** para mesmo fixture antes de exigir alerta. Nunca dar PASS só por \`OCR concluídos=2\`.
2. Instrumentar **somente contagens e tempos** para saber se houve frame NOVO **após a conclusão do primeiro OCR**. No ensaio sintético, pode-se provocar redesenho periódico discreto de um elemento não-financeiro da própria DemoOfferActivity para gerar outro frame, **sem modificar números/preço, sem usar View.draw como substituto da captura**. Exigir o mesmo \`getMediaProjection/createVirtualDisplay/ImageReader\` com consentimento do sistema.
3. Se dois OCRs ainda produzirem apenas um candidato, analisar *classificador/posicionamento/overlay da demo fictícia* com testes privados e contagens, não afrouxar \`FinancialGuard\` nem fabricar campos ausentes. Nenhuma captura real deve entrar em CI.
4. Manter STOP assíncrono e provas de callback tardio/resize mesmo no run em que não houver alerta. O print da 99 e a compatibilidade no celular NÃO foram homologados.

**Nota:** fluxo de frame/latência faz parte de um modelo independente e não altera o Android. As strings em campos de diagnóstico não são devolvidas pelo auditor; schema v1 estrito rejeita campos extras e qualquer valor marcado como conteúdo OCR.
