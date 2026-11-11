# Auditoria temporal privada — duas gravações, eventos visuais, sem mídia no GitHub

**Agente 2 / OCR, Fase MediaProjection.** Esta suíte é *Python puro*, alimentada por intervalos **aproximados e anônimos** inspirados nas anotações da Issue #21 de 11/11/2026. Os MP4, clipes, áudio, oito frames da mesma oferta, ZIP e gabaritos reais permanecem locais/privados. Este repositório NÃO contém qualquer arquivo de mídia real, texto OCR de passageiro, endereço, preço real, rota ou identificador de corrida.

Código: \`tools/ocr_quality_audit/video_temporal_qa.py\`. Testes: \`tools/ocr_quality_audit/tests/test_video_temporal_qa.py\`.

## Como executar offline

\`\`\`bash
python -m unittest discover -s tools/ocr_quality_audit/tests -p 'test_video_temporal_qa.py' -v
\`\`\`

Foram executados **18/18 testes locais PASS** no módulo isolado, com \`py_compile\` aprovado. **Não** atribuir este resultado ao CI Python completo do GitHub nem a ML Kit/MediaProjection no telefone. Nenhum merge, nenhuma alteração Android/Gradle/workflow/main.

## Regra de contagem e segurança

- A unidade de análise é o **episódio visual de oferta**, não o frame e nem a corrida independente. Oito frames capturados dentro do mesmo card produzem **um** episódio avaliado; replays com valores iguais, separados por intervalo visual de mapa, podem representar dois episódios visuais, mas NÃO necessariamente duas corridas distintas. A anotação de \`episode\` é um token opaco sintético e independente do OCR.
- \`CARD\` é um card de oferta presente na tela. \`LIST\` é oportunidade na tela de Solicitações; somente \`LIST_REVIEW\` é um alerta de revisão, não uma corrida aceita nem valor financeiro confirmado. Nunca promovê-lo silenciosamente a \`CARD_ALERT\`.
- \`MAP\`, \`NON_OFFER\` (inclui histórico/ganhos), \`EXPIRED\` e \`AD\` são cenários negativos. Um valor monetário em anúncio NÃO comprova oferta. Qualquer aviso depois de STOP é falso. A oferta expirada também não gera alerta.
- Em intervalos não rotulados, o auditor marca \`unscoredAlerts\`, não inventa falsos positivos. Alertas num card exigem \`financial_guard_passed=True\` ou são classificados \`unsafeAlerts\` e não contam como detecção segura.
- Detectar em até **3 segundos** do início do episódio visual de 10 segundos é uma **meta de teste sugerida**, não latência medida. \`firstCardAlertP95Seconds\` usa posto mais próximo, mas com 1–2 eventos não é estatística robusta. Alertas atrasados são contados separadamente de falsos alertas; nunca alertar após expiração.
- O algoritmo expõe apenas **contagens agregadas e latências**, não IDs de episódio, valor de corrida, OCR bruto ou timestamps de ações do passageiro.

## Dois cenários sintéticos inspirados nas anotações dos MP4 privados

| Cenário | Intervalos arredondados da anotação | O que avaliar |
|---|---|---|
| A, gravação longa de ~5 min | Mapa ~0–188s, card ~188–198s, depois somente contexto não-oferta | No máximo 1 alerta seguro durante os ~10s do card; zero nos ~5 min de não-oferta; não contar os 8 frames do mesmo card como 8 ofertas |
| B, gravação ~103s | Card ~0–7s, mapa ~7–33s, card com MESMOS números ~33–43s, lista ~51–61s, expirado ~61–64s, anúncio ~64–103s | Separar dois episódios VISUAIS (não afirmar duas corridas), lista como revisão, não alertar após expiração e rejeitar anúncio com preço |

**Importante:** no cenário B, o intervalo ~43–51s não tem rótulo definitivo. Um alerta nesse intervalo é não pontuado, e não falso positivo por suposição. Os tempos são aproximações de anotação visual, não resultados de ML Kit. Um controle de volume flutuante pode ocultar parte do card no A; preservar incerteza e abstenção financeira, não inventar números ou reabrir episódio por OCR parcial.

## Porta de homologação para Agente Android e Segurança

1. **P0 Android separado:** concluir teste E2E do PR #30 com consentimento nativo MediaProjection, \`ImageReader\`, ML Kit e STOP. O run 43067924315 falhou ANTES do consentimento por botão não encontrado; não atribuir isso ao OCR.
2. Depois, testar o replay **somente local e voluntário** do clipe de 40s sem áudio no aparelho/emulador, com a tela do reprodutor selecionada no diálogo Android ou tela inteira, nunca atribuindo compatibilidade com a 99 a uma captura do player. Preservar arquivo privado, sem subir mídia/log de OCR.
3. Gerar somente eventos agregados \`epoch/frame/callback/contextKind/financialGuardBlocked/alertPublished\` e relógio relativo de teste. Comparar por episódio visual, não por frame. Medir atraso ao primeiro alerta dentro da janela ~10s sem afrouxar \`ScreenContextClassifier\` ou \`FinancialGuard\`.
4. Depois de haver consentimento e captura real no emulador, auditar STOP com OCR em andamento, falso alerta no anúncio e expiração de solicitação, limpeza de recursos/resize e política do motorista no comando. **Sem APK liberado nem merge** até aprovação independente.

**Limite de evidência:** os 18 testes verificam a pontuação e invariantes em cenários de metadados fictícios; não provam que o OCR detecta a oferta nos vídeos, nem que o Android identifica corretamente o contexto. Nenhuma meta de precisão real foi medida aqui.
