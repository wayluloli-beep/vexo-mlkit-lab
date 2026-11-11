# Auditoria preliminar do relatório Vexo OCR 0.3.3

> **Origem:** JSON `vexo-ocr-batch-report-v1` compartilhado pelo responsável do Vexo em 11/11/2026. Este documento resume os **valores declarados**; não houve acesso às imagens nem verificação independente dos rótulos esperados. O arquivo JSON original não foi versionado no GitHub.

## Resumo numérico

| Indicador | Dado declarado |
|---|---:|
| Imagens | 10 (identificadores `99_001` a `99_010`) |
| Campos conferidos | 111 |
| Campos corretos | 106 |
| Campos discrepantes | 5 |
| Erros de processamento | 0 |
| Acerto por campo | 106 / 111 = **95,495...% (~95,5%)** |
| Imagens com ao menos um erro em campo de risco | **4/10** |

Conferência cruzada: os contadores das dez amostras somam **111 conferidos e 106 corretos**; os contadores por campo somam os mesmos valores. Esta é uma verificação aritmética das declarações do arquivo, não uma reavaliação do OCR nas imagens.

| Campo | Corretos/Conferidos | Acerto |
|---|---:|---:|
| `surge` (tarifa dinâmica) | 1/4 | **25%** |
| `perKm` (R$/km exibido) | 3/4 | **75%** |
| `tripKm` (km da viagem) | 9/10 | **90%** |
| `offerPrice` | 10/10 | 100% |

Os outros campos informados (`platform`, `offerType`, `payment`, `pickupMin`, `pickupKm`, `tripMin`, `rating`, `rides`, `negotiations`) tiveram 100% entre os itens **efetivamente checados**, com denominadores diferentes. Valores não testados não contam como acertos.

## Quantas ofertas foram afetadas?

Os cinco erros declarados estavam distribuídos por **4 das 10 imagens**: `99_003`, `99_007`, `99_008` e `99_010`.

- Ofertas com qualquer erro reportado: **4/10 (40%)**.
- Ofertas com erro em campo diretamente financeiro (`surge` ou `perKm`): **4/10 (40%)**.
- Ofertas com erro de distância (`tripKm`): **1/10 (10%)**.
- União dos erros financeiros diretos e de distância: **4/10 (40%)**, não 5/10. O caso `99_003` apresentou **dois erros** e deve ser contado uma vez nessa medida.

**Importante:** essas taxas descrevem apenas as dez imagens e os campos conferidos na exportação fornecida, **não** a frequência esperada de erro em novas corridas. As ofertas não são uma amostra independente representativa do trânsito de produção.

## Cinco discrepâncias, todas em campos sensíveis à decisão

| Caso | Campo | Esperado | Extraído | Interpretação |
|---|---|---:|---:|---|
| `99_003` | `tripKm` | 11,8 km | 1,8 km | Erro de 10 km; subestimação de ~84,75% |
| `99_003` | `surge` | 2,8× | ausente | Multiplicador indisponível |
| `99_007` | `surge` | 1,1× | ausente | Multiplicador indisponível |
| `99_008` | `surge` | 2,2× | ausente | Multiplicador indisponível |
| `99_010` | `perKm` | R$ 1,28/km | ausente | Indicador indisponível |

**Não converter “ausente” em zero** nem atribuir valor monetário a perdas que não ocorreram ou não foram medidas. Os quatro erros de `surge`/`perKm` (três + um) merecem *revisão financeira prioritária* por potencial de induzir decisão incorreta. O erro de `tripKm` é um risco **indireto** de cálculo financeiro. O valor principal da oferta (`offerPrice`) teve 10/10 acertos nesta amostra.

### Exemplo condicional de impacto de `99_003`

Se um indicador hipotético dividisse **R$ 40,70** pela distância total `pickupKm + tripKm`, o valor usando a extração errada seria **R$ 40,70 / (3 + 1,8) ≈ R$ 8,48/km**; usando a referência, seria **R$ 40,70 / (3 + 11,8) = R$ 2,75/km**. Essa conta **não prova** que o app tenha calculado ou mostrado algum desses indicadores; demonstra a sensibilidade de fórmulas financeiras à distância incorreta.

## Pistas de origem (não são diagnóstico conclusivo)

O próprio `ocrEvidence` **declara** `expectedNumberSeenInRawOCR=false` para `tripKm`/`surge` em `99_003` e `surge` em `99_007`/`99_008`. Isso sugere investigar reconhecimento OCR, disposição dos caracteres e normalização; **não comprova** falha do ML Kit, pois o critério de busca do número também pode falhar.

Em `99_010`, o `ocrEvidence` declara `expectedNumberSeenInRawOCR=true` para `perKm`, com candidato `1,28/km`, enquanto o resultado extraído ficou vazio. Isso direciona a investigação para a regra de localização, vínculo campo-valor, normalização e interpretação do parser; também **não confirma** a origem sem inspecionar texto bruto e logs.

## Sinalizador de segurança

- `99_003` declarou `financialSafety.basicFieldsUsable=false`: há alerta explícito do app, coerente com a distância suspeita.
- `99_007`, `99_008` e `99_010` declararam `basicFieldsUsable=true` **apesar de** erros em dinâmica ou R$/km. Isso não implica necessariamente defeito do sinalizador, que é restrito a “campos básicos”, mas significa que ele **não deve ser interpretado como segurança financeira completa**.

## Comparação com a versão 0.3.2

O resultado agregado anteriormente informado para a **0.3.2** era igualmente **106/111 = 95,5%**, com cinco discrepâncias. **Diferença agregada observável: 0 ponto percentual.** Não há elementos suficientes aqui para comparar cada par de imagens, atestar identidade de amostra ou declarar melhoria/regressão. O rótulo do gerador permanece `Android Google ML Kit + OfferParser 0.3` na exportação 0.3.3; isso, por si só, não demonstra que o código não mudou.

## Próximas verificações

1. Conferir OCR bruto e localização dos valores de dinâmica na imagem; registrar recorte e caracteres com confidencialidade.
2. Para `99_010`, criar teste de parser cobrindo explicitamente o token `1,28/km`.
3. Para `99_003`, testar `11,8km` vs `1,8km`, detecção de dígito inicial perdido, plausibilidade e sinalização conservadora.
4. Repetir **as mesmas imagens rotuladas** em 0.3.2 e 0.3.3; depois ampliar o teste para material não usado no desenvolvimento.
5. Acompanhar **ofertas com pelo menos um campo crítico incorreto**, além da média por campo, e definir critérios de aprovação específicos para `surge`, `tripKm` e `perKm`.

**Conclusão:** a taxa agregada de 95,5% não autoriza homologação em produção. Os dados direcionam testes adicionais, mas não determinam confiabilidade em uso real.
