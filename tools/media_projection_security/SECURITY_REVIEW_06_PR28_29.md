# Revisão 06 — exportação voluntária e métricas OCR (PR #28 / #29)

Data: 2026-11-11. Agente 3 — auditoria independente. **Somente fonte e logs; sem editar as branches Android/OCR.**

## Evidências verificadas

| Proposta | SHA inspecionado | Segurança do diagnóstico / latência |
|---|---|---|
| [PR #28](https://github.com/wayluloli-beep/vexo-mlkit-lab/pull/28), botão de copiar diagnóstico | `b212aee9ffa32638af1f526ad894901e4093694f` | 4 PASS, 1 WARN P2, 2 SKIP (não possui métricas de latência) |
| [PR #29](https://github.com/wayluloli-beep/vexo-mlkit-lab/pull/29), latência p50/p95 | `82915328bd4845f670ce7c73dd37e5c31afec2c6` | 6 PASS, 1 WARN P2, 0 SKIP |

CI do auditor independente: https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43068598144, **80/80 testes sintéticos Python PASS**, execução `Auditoria MediaProjection (Python offline)` **SUCCESS**. O scanner lê PRs #28 e #29 por `git worktree` *somente leitura*, mostra SHA, contratos e WARN no resumo do CI. Uma ferramenta de análise estática não prova ausência completa de vazamentos em tempo de execução.

## Exportação do diagnóstico

O clique explícito em `Copiar diagnóstico da captura para análise` chama `LiveCaptureState.safeDiagnosticReport()`, que serializa um **conjunto fixo de 19 campos agregados no PR28**, ampliado para 25 no PR29. O scanner rejeita chaves não permitidas, chaves dinâmicas, mudanças nos valores seguros dos campos e referências a `lastCandidate`, `snapshot()`, `getText()` ou pixels no método de exportação. Confirma que o clipboard é preenchido somente na ação do botão, não na inicialização nem após atualização automática.

Limitações:
- Os contadores são **metadados de uso**, mesmo sem preço, rota, nome ou endereço; a área de transferência do sistema não é um cofre privado. O usuário deve revisar o JSON antes de colar fora do Vexo.
- **P2 recomendado para PR #28 / #29:** antes de `clipboard.setPrimaryClip(clip)`, chamar `clip.getDescription().setExtras(extras)` com `PersistableBundle` contendo `ClipDescription.EXTRA_IS_SENSITIVE=true` (API 33+; equivalente literal na compilação pré-33). Evita que a prévia de área de transferência Android 13+ mostre o JSON. **Não criptografa, não impede acesso ao conteúdo e não substitui consentimento.** Não há marcador no código inspecionado, por isso o scanner registra **WARN**, não bloqueio de segurança.
- Fonte oficial: https://developer.android.com/privacy-and-security/risks/secure-clipboard-handling e https://developer.android.com/reference/android/content/ClipDescription#EXTRA_IS_SENSITIVE

## Métricas OCR PR29

`CaptureLatencyStats` mantém janela de no máximo **128 durações em RAM**, rejeita durações negativas ou acima de 600.000 ms e reinicializa no começo de uma nova sessão. O registro a partir do callback ML Kit está protegido por `active`, `!stopping` e `epoch.get()==session`. Os p50/p95 vêm da **janela de amostras**, enquanto média e máximo vêm da **sessão**: distinguir isso no relatório para não comparar grandezas diferentes. Contagens e tempos do emulador não equivalem a desempenho no celular do usuário.

## Resultado mais recente de emulador / bloqueio P0

CI [PR #29](https://github.com/wayluloli-beep/vexo-mlkit-lab/actions/runs/43066818185): job `Parser, segurança e APK` SUCCESS; job de emulador Android 35 FAILURE (**1/15 testes**, `LiveProjectionConsentE2eTest`). Mensagem da asserção:

```text
frames=29, OCR=2, avisos=0, janela=não informada,
contextOffer=1, contextUncertain=1,
contextRejected=0, financialGuardBlocked=0,
waitingStableReads=1
```

Isto é evidência de pixels recebidos por MediaProjection, ML Kit concluindo 2 tarefas e **apenas UMA leitura classificada como candidata a oferta**. O alerta exige duas leituras válidas estáveis, portanto ainda não há prova de reconhecimento completo. `janela=não informada` não é evidência de que a janela esteja oculta, mas requer investigar o callback de visibilidade. Não relaxar guardas de contexto e finanças para produzir sucesso artificial.

**PEDIDO Android / Agente 2:** coletar apenas métricas agregadas/tempos por etapa no app de demonstração fictícia, testar 3 leituras realmente válidas e consistentes, verificar visibilidade/escopo selecionado pelo sistema e separar falha OCR, classificador e confirmação de episódio. Testar interrupção do Android com Task pendente e release de reader no resize. Não gravar imagens ou OCR bruto no CI, não usar a 99 real no laboratório, não liberar APK de captura como aprovado.

**Status:** PR #28/29 passam contratos de privacidade de fonte; WARN cosmético/recomendação de preview do clipboard. Homologação da captura e alerta no emulador continua P0 ABERTA. PRs draft e branch do auditor isolada; sem merge e sem automação de decisão do motorista.
