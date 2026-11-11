# Testes automáticos do Vexo sem instalação de APK

Esta documentação pertence **somente** à auditoria independente de relatórios e não muda código Android ou workflows.

## Execute agora — Python 3.10+ (sem Gradle, sem dispositivo e sem instalar APK)

Na raiz do repositório:

```sh
python tools/ocr_quality_audit/check.py
# Opcional: execute localmente com um relatório exportado, nunca faça upload do JSON privado no CI
python tools/ocr_quality_audit/check.py --report /caminho/privado/relatorio.json
```

A primeira invocação roda todos os testes sintéticos em `tools/ocr_quality_audit/tests/` e sai com código 0/1 conforme aprovação/reprovação. A opção `--report` analisa localmente um lote real, falha em inconsistências internas de contadores (retorno 3), e **não** falha só porque há erros reais de OCR — esses erros devem aparecer nas métricas, não ser ocultados. O comando não envia arquivos pela rede nem imprime o conteúdo bruto do relatório.

## Matriz de capacidades

| Teste / verificação | Python independente? | APK no celular? | Evidência que produz |
|---|---|---|---|
| JSON parse e schema do relatório | Sim | Não | rejeita versão/estrutura inesperada |
| Consistência entre `summary`, `perField`, `samples` | Sim | Não | alerta contagem divergiu |
| `false_positive` com `expected: null`, `actual` preenchido | Sim | Não | conta erro no denominador, sem inventar delta |
| `wrong` e `missing` em distância, tarifa e R$/km | Sim | Não | marca prioridade de revisão com evidência declarada |
| Diferenças de versões e comparação de denominadores | Sim | Não | delta em pontos percentuais + ressalva de pareamento |
| Testes unitários dos métodos Java do parser | Não (requer JVM/Gradle) | **Não**, podem rodar no GitHub Actions | valida regras Java, não a leitura real de telas |
| Compilação do aplicativo | Não (requer Android SDK/Gradle) | Não, pode rodar no GitHub Actions | APK compilado, não garante OCR em tela real |
| ML Kit reconhecendo texto de prints reais | Não | Requer execução Android em dispositivo/emulador configurado | reconhecimento real, desempenho específico do cenário |
| Captura automática da tela de outros apps | Não | Requer validação Android e permissões reais | confiabilidade e conformidade de captura; não é provada por JSON |

## Pedido de integração ao CI (equipe Android/integração)

A **equipe proprietária dos workflows** pode colocar um job Python independente no GitHub Actions, sem instalar Android SDK e sem gerar APK:

```yaml
  auditoria_python:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Testar auditor Vexo (sem Android)
        run: python tools/ocr_quality_audit/check.py
```

Este é um **exemplo para revisão** — não foi aplicado ao workflow e não deve ser interpretado como CI já configurado. Não adicionar relatórios reais nem prints como fixtures ou artefatos de CI. Quando for preciso validar um export, execute `--report` localmente num ambiente controlado e compartilhe apenas indicadores não sensíveis.

## O que os testes ainda não provam

- O programa recebe **rótulos produzidos por humanos ou pelo próprio gerador** e não relê pixels. Contadores matematicamente coerentes não garantem que cada rótulo esteja correto.
- Uma ausência `missing` não equivale a zero e não gera prejuízo monetário calculado.
- Um `false_positive` conta no denominador **somente quando o gerador emite explicitamente um campo inesperado**. Campos legitimamente ausentes, omitidos da lista, não recebem crédito artificial.
- Dez imagens / 111 campos não dão representatividade suficiente para declarar prontidão em produção.
- Dados de versões diferentes precisam do mesmo conjunto de imagens e rótulos para comparação confiável.
