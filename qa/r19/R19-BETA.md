# Vexo R19 — evolução modular do beta manual

Esta camada parte da edição R18 do beta Android (Kotlin + WebView). Mantém o uso sem cadastro de conta e o histórico local. Não inclui simulador, corridas fictícias ou captura automática. Separada da validação de atualização da R18.

| Itens | Entrega da R19 | Próxima prova |
| --- | --- | --- |
| 201–204, 207 | Mesma navegação manual e política local com avaliação de snapshots previamente verificados. GPS, OBD2 e Fiscal continuam indisponíveis neste binário, mesmo que uma configuração externa tente ativá-los. | Provedor de configuração, módulos e fallback de GPS num binário que os contenha. |
| 211–212 | Plano Alugado mostra equivalente semanal do aluguel e custos pagos à parte sem reaproveitar IPVA ou depreciação. | Validar a tela no Android e confirmar entendimento com motoristas. |
| 221 | Uber, 99, inDrive e outros recebimentos separados no mesmo turno. | Validar os campos e o teclado no Android. |
| 231–232 | Preto OLED e ações de turno para a mão escolhida, opcionais e locais. | Testar toque, contraste, foco, teclado e fontes maiores num aparelho. |
| 241–242 | Dinheiro e Pix classificam os ganhos já informados. O Pote calcula uma sugestão separada do líquido quando há taxa e distância. | Validar reabertura e conferência no Android. |
| 261–262 | Uso local sem conta continua. Contrato de migração descreve como preservar os dados existentes. | Implementar e testar migração com backend de conta autorizado. |
| 271–272 | Um toque oculta os resumos e as sugestões monetárias da Home. A opção de 30 segundos vale para inatividade, não detecta suporte. Campos que o motorista está digitando continuam visíveis. | Validar TalkBack e renderização na WebView. |
| 281–282 | Protocolo de abertura a frio e verificação do código Web, lint Android e testes unitários. | Medir a meta de 1,2 s em aparelho. Nenhuma proteção de merge foi alterada. |
| 291–292 | Cálculo rápido usando valores informados, disponível sem configurar um plano. Não escreve histórico. | Cronometrar com testadores. Cartão compartilhável depende de progresso semanal verdadeiro. |

O relógio contínuo ao volante (#251) fica para o fluxo de pausas e retomada, sem estimar direção a partir do tempo total. Não ativa sincronização, telemetria, GPS, Fiscal, Bluetooth ou compartilhamento externo. Os demais itens permanecem no backlog, deduplicados quando reaproveitam histórico, metas, onboarding e QA existentes.

## Testar sobre a R18

A partir da raiz, em uma cópia descartável:

```bash
bash qa/r19/materialize.sh /caminho/vazio/de/trabalho
node qa/r19/ci-manual.cjs web /caminho/vazio/de/trabalho/src/aurora
```

Use `android` no lugar de `web` e acrescente o caminho para o executável Gradle 8.11.1 para incluir lint e testes Android, em ambiente com Java 17 e SDK 35. O resultado local Web não equivale a uma prova no emulador.
