# Vexo — plano de aumento de precisão OCR (evidência antes de hipótese)

**Estado:** especificação de auditoria, **não** uma correção do app nem medição de nova acurácia.
**Fonte:** relatório textual 0.3.3 fornecido pelo responsável (10 imagens, 111 campos, 106 acertos). Fotos e texto OCR integral não disponíveis à auditoria. Os testes sintéticos do GitHub Actions **não certificam** o comportamento nos prints originais.

## Prioridade por falha real

| Caso | Campo | Referência | Extrato | Hipótese e experimento |
|---|---|---|---|---|
| 99_010 | perKm | 1,28/km | vazio; evidência aponta OCR com `1,28/km` | PR #6 (0.3.4) já aceita valor sem `R$`. Confirmar replay pareado no print original; proteger contra falso positivo em indicadores não exibidos |
| 99_003 | tripKm | 11,8 km | 1,8 km | Evidência sugere perda de um dígito antes de `1,8km`. Testar recorte da **região de viagem** e OCR adicional sem adivinhar o dígito; preservar bloqueio de cálculo se continuar ambíguo |
| 99_003 | surge | 2,8x | vazio; OCR indicativo `42,8x` | Separar selo de dinâmica e ruído da arte; testar recorte contextual, escala e contraste; não transformar `42,8x` em `2,8x` apenas por plausibilidade |
| 99_007 | surge | 1,1x | vazio; candidatos incluem `4x` | Investigar legibilidade e localização do multiplicador; evitar ler fragmento isolado como dinâmica |
| 99_008 | surge | 2,2x | vazio; OCR indicativo `42,2x` | Mesmo experimento de 003, com teste negativo para não aceitar multiplicadores inexistentes |

**Nota:** `ocrEvidence.expectedNumberSeenInRawOCR` é uma declaração do gerador, não prova independente de falha do ML Kit. Requer inspeção de imagens e caixas OCR.

## Método A/B para passar de testes a precisão comprovada

1. Preservar a linha de base 0.3.3, com hash de cada imagem original e rótulos humanos verificados. Não usar screenshots reais em PR, comentários, logs públicos, fixtures ou GitHub Actions.
2. Rodar a mesma bateria no mesmo ambiente/versão Android, com mesmo conjunto de imagens, na versão candidata (0.3.4 ou superior). Se não houver acesso seguro aos arquivos originais, registrar o experimento como **bloqueado**, não como ganho comprovado.
3. Medir `correct/checked` e `perField` com a mesma definição de campo e conjunto de imagens, distinguindo `wrong`, `missing` e `false_positive`. Medir também **ofertas com ao menos um erro financeiro/distância** (cada oferta contada uma vez).
4. Investigar cada correção com experimento controlado: primeiro o mesmo texto com parser, depois pixels sintetizados com ML Kit (múltiplos temas, fontes, densidades, ruídos e recortes), depois a imagem real sob uso consentido.
5. Regressão negativa obrigatória: campos anteriormente corretos devem continuar corretos; dinâmica ausente não pode se tornar um multiplicador inventado; distância de navegação não pode substituir a distância da viagem. Sem inferência automática `42,8x→2,8x` ou `1,8km→11,8km`.
6. Impedir recomendações financeiras quando faltar campo essencial, quando houver inconsistência ou baixa confiança. `basicFieldsUsable` não é garantia de `surge` nem de `perKm`.
7. Só depois testar em conjunto independente mais amplo, estratificado por variações de UI (99 Moto/Negocia/Prioritário, tema claro/escuro, modelos/resoluções, tarifas e distâncias). **10 imagens não bastam para homologação.**

## Indicadores de aceite *para os 10 casos de regressão* (não critérios de produção)

- `99_010.perKm` deve ser `1,28`, sem novos falsos positivos.
- `99_003.tripKm` deve ser `11,8`, sem inventar dígitos se OCR continuar ambíguo.
- `99_003/007/008.surge` deve corresponder respectivamente a `2,8`, `1,1`, `2,2` **ou** permanecer explicitamente pendente de revisão (não pode gerar valor confiável a partir de ruído).
- Nenhuma regressão nos **106 campos anteriormente corretos**, com mesmo contrato de comparação.
- Registrar `perField`, `falsePositiveCount`, `offersWithDecisionRelevantError`, logs privativos de diagnóstico e diferenças por imagem. Nenhum resultado sintético pode ser usado como substituto da bateria real.
- Distinguir claramente **exatidão de extração** (acerto literal) de **segurança financeira** (abstenção/bloqueio): abster-se em caso ambíguo é mais seguro, mas não é um acerto literal.

## Responsabilidades e bloqueios

- **Android/OCR:** escolher e testar modificações no ML Kit, recortes/boxes, OfferParser e FinancialGuard, em branch própria e PR draft. PR #12 já cobre três cards sintéticos de estresse visual; ampliar a cobertura depois de revisar esses resultados, evitando duplicidade.
- **Auditoria:** medir integridade dos exports e taxa por campo/oferta via `tools/ocr_quality_audit/check.py`, revisar diferenças e sinais de falsos positivos. Nenhuma edição no app, Gradle ou workflows.
- **Bloqueio para alegar aumento real de precisão:** acesso privado e consentido aos **mesmos dez prints originais**, ground truth verificada e export pareado da candidata; não pedir reinstalação contínua.
- **Bloqueio de produção:** conjunto independente de maior amplitude, critérios de aceite acordados e taxa de erro por oferta com estratos e incertezas; não homologar com 10 casos.

**Importante:** é melhor declarar `não consegui ler` do que apresentar um valor incorreto como seguro. Jamais automatizar aceitar ou cancelar corridas.
