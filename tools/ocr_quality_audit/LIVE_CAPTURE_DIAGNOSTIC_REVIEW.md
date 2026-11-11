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
