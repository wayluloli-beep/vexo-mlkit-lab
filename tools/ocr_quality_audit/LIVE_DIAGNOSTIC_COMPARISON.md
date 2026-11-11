# Vexo 0.4 — relatórios consecutivos de captura (sem conteúdo da tela)

## Correção do auditor em novembro de 2026

\`live_diagnostic_audit.py\` agora aceita **exatamente duas formas** do schema \`vexo-live-capture-diagnostic-v1\`:

- Formato inicial do PR #28: contadores agregados, status e explicações curtas.
- Formato dos PR #29–#32: os mesmos campos **mais seis métricas de latência** (\`ocrLatencySamples\`, \`ocrLatencyLastMs\`, \`ocrLatencyMeanMs\`, \`ocrLatencyP50Ms\`, \`ocrLatencyP95Ms\`, \`ocrLatencyMaxMs\`).

Não aceita extensões arbitrárias, campos de texto OCR, nome, endereço, rota, preço ou token; tipos inválidos ou conjuntos incompletos de métricas são rejeitados. As explicações e notas de privacidade são **validadas, mas nunca ecoadas** pelo auditor. É um verificador local; os arquivos de diagnóstico compartilhados voluntariamente pelo proprietário NÃO foram gravados neste repo.

\`compare_live_diagnostics.py\` aceita dois desses relatórios e calcula diferenças de contadores. **Não comprova que são a mesma sessão**: schema v1 não tem \`sessionId\`, \`epoch\` nem timestamp de snapshot. Um contador menor pode indicar sessão reiniciada; relatórios de versões diferentes não devem ser comparados diretamente. Não inferir latência de aparição da oferta a partir de \`ocrLatencyP95Ms\`: esse valor mede somente a duração individual da inferência, não detecção, classificação, confirmação ou aviso.

## Uso local (somente diagnóstico copiado e consentido)

\`\`\`bash
python tools/ocr_quality_audit/live_diagnostic_audit.py /caminho/diagnostico1.json
python tools/ocr_quality_audit/compare_live_diagnostics.py /caminho/diagnostico1.json /caminho/diagnostico2.json
python -m unittest discover -s tools/ocr_quality_audit/tests -p 'test_diagnostic_version_comparison.py' -v
\`\`\`

Ambas as ferramentas retornam **somente contadores, diferenças e códigos de inconsistência**; nenhuma imagem, texto bruto, valores financeiros ou identificação da oferta. Arquivos limitados a 8 KiB, JSON com chaves repetidas rejeitado. O \`compare\` devolve \`sessionContinuityProven=false\` mesmo quando contadores aumentam. Não usar essas ferramentas para afirmar precisão ou compatibilidade com 99.

## Checagem nova: percentil p95 e amostras pequenas

A classe Android \`CaptureLatencyStats.snapshot()\` implementa quantil de **posto mais próximo**: \`ceil(n * .95) - 1\` no vetor ordenado da janela de até 128 amostras. Com **1 a 19 amostras**, o p95 calculado é necessariamente igual ao **máximo** dessa janela, mesmo que nenhuma medida seja erro.

**Investigação pendente (metadados relatados na Issue #21):** a primeira e segunda leituras copiadas pelo usuário indicaram p95 diferente, mas a segunda não foi anexada integralmente nesta auditoria. Se são de fato a MESMA sessão e o número de amostras só cresceu de um total abaixo de 20, o p95 não pode cair abaixo do máximo anterior. O auditor marca \`P95_DROPPED_BELOW_PREVIOUS_MAX_WITH_SMALL_SAMPLE_WINDOW\` para revisão. Possíveis explicações alternativas: nova sessão/reset, versão de APK diferente, campos transcritos incorretamente ou código da estatística divergente. **Não declarar bug no celular nem melhora de desempenho até conferir os JSON integrais consentidos e o mesmo build.**

## Critérios separados

- **OCR concluiu** não é **OCR correto**.
- \`screenContextUncertain\` não significa necessariamente erro de reconhecimento: o vídeo pode incluir mapa, tela de controles, sobreposição e transição.
- \`offersAlerted=1\` é evidência de um episódio de alerta nessa sessão, não taxa de precisão nem prova de que os números eram exatos.
- Para testar STOP: o usuário deve apertar PARAR fora de uma corrida, verificar se o indicador do Android cessou e copiar **novo** diagnóstico \`CAPTURE_STOPPED\`; não inferir STOP de um relatório anterior \`CAPTURE_ACTIVE\`.
- Para medir tempo de detecção: instrumentar marco da primeira visibilidade de oferta fictícia com um relógio de sessão, sem armazenar imagem ou OCR. Percentis de menos de 20 amostras são instáveis e não medem melhora permanente.

**Status:** esta entrega contém testes de unidade com fixtures totalmente artificiais, ainda requer execução em Python CI separado. Nenhum APK, print real, token, dado pessoal ou branch Android foi alterado; não fazer merge antes da revisão de segurança.
