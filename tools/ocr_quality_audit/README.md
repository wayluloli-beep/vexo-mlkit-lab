# Vexo OCR — auditor independente de qualidade

Ferramenta **offline, somente leitura e sem dependências externas**. Não altera o Android, o ML Kit, o `OfferParser`, as configurações de build ou os testes do aplicativo. Analisa aritmética, cobertura e indicadores de relatórios de homologação exportados pelo Vexo. Foi desenvolvida para trabalhar em paralelo ao diagnóstico Android.

## Uso

Na raiz do repositório, com Python 3.10 ou posterior:

```bash
python tools/ocr_quality_audit/audit.py caminho/relatorio-0.3.2.json
python tools/ocr_quality_audit/audit.py caminho/relatorio-0.3.3.json --compare caminho/relatorio-0.3.2.json
python tools/ocr_quality_audit/audit.py caminho/relatorio-0.3.3.json --compare caminho/relatorio-0.3.2.json --format json --output auditoria.json
python -m unittest discover -s tools/ocr_quality_audit/tests -v
```

**Não inclua no GitHub os relatórios reais, capturas de tela, endereços ou histórico de motoristas.** Rode a ferramenta localmente e revise o relatório gerado antes de compartilhar. A ferramenta não coleta nem envia dados pela rede.

## Formato aceito

Aceita `vexo-ocr-batch-report-v1`, com `appVersion`, `testImages`, `summary` (`checked`, `correct`, `discrepant`, `processingErrors`, `accuracyPct`) e `perField` (por campo, `checked` e `correct`). O relatório original pode conter campos extras; eles não são interpretados automaticamente.

**Formato usado na exportação 0.3.3:** quando há `samples`, cada item deve conter `id`, `fields` com entradas `expected`, `actual` e `status` (`ok`, `wrong` ou `missing`), além de contadores `correct` e `tested`. O auditor reconcilia os status por amostra, por campo e com `summary`. Também lê, quando fornecidos, `financialSafety.basicFieldsUsable` e `ocrEvidence.<campo>.expectedNumberSeenInRawOCR`. Essa evidência é apenas um indício declarado pela exportação, não uma verificação independente do texto OCR nem uma prova da origem do erro. **Quando os dois formatos existem, `samples` tem prioridade** para evitar contar o mesmo erro duas vezes.

**Campo ausente ≠ valor zero:** `actual: ""` com `status: "missing"` gera um alerta de revisão financeira, mas a magnitude da diferença não é calculada (a ausência não corresponde a 0 real). Uma anotação `basicFieldsUsable: true` descreve apenas a segurança dos campos básicos segundo o próprio app, e **não garante** que tarifa dinâmica ou R$/km estejam disponíveis.

O suporte **opcional** a erros individuais espera uma lista `discrepancies`, com objetos como `{"field": "offerPrice", "caseId": "teste-local-1", "expected": "43,09", "actual": "4,09"}`. A alternativa `observed` é aceita no lugar de `actual`. Este trecho é **somente um exemplo sintético** de formato, não um resultado de teste real. Esse formato mais antigo continua aceito quando `samples` não existe; **o programa não tenta adivinhar** estruturas desconhecidas.

## Indicadores e como interpretá-los

- **Acerto geral** = `correct / checked × 100`. Campos com `checked = 0` recebem `n/a`, jamais 100%.
- **Por campo** = `perField[field].correct / perField[field].checked`. Campos financeiros não são diluídos na média global: erros em tarifa, preço, dinâmica/multiplicador e R$/km são separados de erros de distância e de metadados.
- **Consistência** = conferir `checked − correct = discrepant`, percentuais declarados e soma de `perField`. Divergências são sinalizadas como avisos e não são corrigidas silenciosamente.
- **Risco financeiro agregado** = campos associados a decisão financeira com `checked − correct > 0`. **Sem valores reais versus esperados, não há como determinar o tamanho nem confirmar criticidade do erro.**
- **`critical_review`** = uma divergência individual declarada (`wrong` ou `missing`) em campo diretamente financeiro. Significa **prioridade de revisão** porque pode alterar decisão do motorista; **não significa perda financeira comprovada**. Distâncias divergentes são `distance_review` porque podem distorcer os cálculos derivados.
- **Erros de processamento** são informados em separado: não presumimos como entram no denominador de acertos do gerador.
- **Diferenças entre versões** são expressas em **pontos percentuais**; só com a mesma base de screenshots, mesmos rótulos de referência e critérios é possível avaliar a evolução de maneira justa. Um `datasetHash`, `datasetId` ou `caseSetId` coincidente é apenas uma indicação declarada, **não prova a identidade do dataset**.

### Limitações críticas

1. **Auditoria de relatório não é auditoria de OCR ponta a ponta.** A ferramenta recalcula números declarados; não acessa prints nem verifica se os rótulos humanos estão corretos. Erros de leitura do ML Kit e de interpretação do parser permanecem indistinguíveis sem evidência adicional.
2. Os **10 prints e 111 campos** das versões 0.3.2 e 0.3.3 são uma amostra pequena e correlacionada (múltiplos campos por print), não uma validação de 95,5% para produção. Não há intervalo de confiança confiável de desempenho real sem amostragem representativa e teste independente.
3. Comparações de versões com imagens, plataformas, tipos de oferta ou campos diferentes podem mostrar alterações de porcentagem por **mudança de amostra**, não por evolução/regressão do programa.
4. A classificação de risco depende do nome do campo. Nomes novos ou genéricos podem não ser classificados como financeiros. Revise `riskBearingFieldsWithErrors` e os campos não classificados.
5. Valores de dinheiro, km e multiplicadores em formato brasileiro são analisados sem arredondar valores originais. Há formatos de texto ambíguos que não são convertidos; nesses casos o erro pode ser assinalado, mas sua magnitude não é estimada.
6. **Não use estas métricas para aceitar/rejeitar automaticamente corridas.** A decisão deve ficar com o motorista e exige conferência quando há inconsistência.

## Critérios mínimos sugeridos antes de homologar para produção

Construir um conjunto de teste independente e representativo, com imagens de 99 (e de cada outra plataforma que se pretenda suportar), diversidade de aparelhos, temas, fontes, resoluções, tarifas dinâmicas, intervalos de distância e casos difíceis. Registrar rótulos verificados manualmente, gerar IDs anônimos estáveis para os casos, comparar as mesmas imagens entre versões e acompanhar taxa de **erro crítico financeiro por oferta**, além das taxas por campo. Definir limites de aceitação com a equipe do produto; este utilitário **não os inventa**.
