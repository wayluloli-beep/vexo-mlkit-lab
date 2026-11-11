# Revisão independente — v0.3.5 e segundo lote de imagens

**Status:** revisão de relatórios e de código Android feita pelo auditor, sem acesso ou upload de prints privados. Não confirma acurácia em produção e não altera o aplicativo.

## Resultado medido e sugestão de releitura

| Medida | v0.3.3 | v0.3.5 |
|---|---:|---:|
| Campos corretos | 106/111 | 107/111 |
| Taxa por campo no mesmo lote de 10 imagens | 95,5% | 96,4% |
| Erros declarados | 5 | 4 |
| Casos financeiros/distância afetados | 4 imagens | 3 imagens |

A diferença **medida** foi de um acerto (+0,9 ponto percentual, por arredondamento) devido ao parser de R$/km. O diagnóstico de ROI trouxe dois candidatos correspondentes ao gabarito dos mesmos prints, mas **não alterou os campos finais**:
- 99_003: tripKm 1,8 → sugestão visual 11,8 (ainda resta erro em surge nessa mesma oferta);
- 99_007: surge ausente → sugestão visual 1,1 (ainda não promovida);
- 99_003 e 99_008: surge com glifo ⚡ possivelmente confundido com 4, sem sugestão válida.

Se ambos os candidatos fossem aceitos **com evidência adequada**, o placar hipotético seria 109/111 = 98,2% nesse lote; isso **não é acurácia observada** e concordância de 2 execuções do mesmo OCR não é verificação independente.

## Experimento mínimo para os dois erros de glifo ⚡ / multiplicador

**Hipótese, não causa comprovada:** o ícone do raio pode ter sido fundido visualmente ao número como um `4`. Não existe autorização para transformação textual `42,8x→2,8x`.

1. Na branch Android, capturar **somente em memória** para `surge`: ROI ancorada no *mesmo card* entre preço principal e perfil de corridas; caixa de linhas, elementos e símbolos reconhecidos pelo ML Kit. Não salvar log de OCR bruto, coordenadas de localizações privadas nem prints.
2. Comparar a leitura do bitmap original com duas variantes do **mesmo recorte**: (a) faixa inteira incluindo ícone com margem suficiente; (b) faixa de texto cujo limite esquerdo seja definido por evidência espacial do glifo (caixas de símbolos e/ou vale de projeção de pixels), **não** por remover um caractere de string ou chutar coordenada fixa. Se a separação do glifo não for demonstrável pelos pixels, não gerar candidato.
3. Controles obrigatórios: multiplicador real 4,8x; multiplicador 2,8x sem ícone; ausência de multiplicador; glifo ⚡ com o texto do valor mais próximo; rótulo de preço e perfil de **duas ofertas** na mesma tela; mapa com valor dinâmico mas sem oferta. Em caso de âncoras misturadas, recusar ROI.
4. Guardar para auditoria só contagens sintéticas por caso: candidatos gerados, divergências, abstenções, latência e **novos falsos positivos**. Sem promover o candidato a valor financeiro enquanto não houver confirmação independente.
5. Primeiro executar com pixels sintéticos no CI. Para chamar de **recuperação real**, comparar localmente os mesmos prints originais, com rótulos humanos, sem publicá-los.

**Aceite decisivo:** recuperar corretamente `2,8x` e `2,2x` em pixels isolados pelo contorno visual, sem transformar `4,8x` em `8x`, sem criar `surge` em mapa ou oferta sem tarifa, e sem retroagir sobre os 107 campos já corretos. Falha em qualquer controle mantém o campo em revisão.

## Lote 02 — medir contexto separado da acurácia

Segundo a análise de hashes comunicada no canal de coordenação:
- 15 imagens no lote 02, das quais 11 são repetidas do lote 01;
- 4 **novas** imagens, em grande parte telas de histórico, mapa e oferta arquivada, sem gabarito financeiro completo;
- a `99_011` já existia no lote 01, mas não fazia parte das dez imagens avaliadas na v0.3.3; pode testar uma modalidade nova, porém não é amostra nova independente do segundo pacote.

O classificador `ScreenContextClassifier` deve gerar métricas próprias:
- `OFFER_CANDIDATE`, `COMPLETED_TRIP`, `MAP_WITHOUT_OFFER`, `ARCHIVED_OFFER_SCREENSHOT`, `UNCERTAIN`;
- anotar manualmente, em privado, `true_live_offer` versus `not_live_offer` por imagem;
- calcular matriz de confusão, falsos bloqueios de ofertas verdadeiras e falsas ativações de não-ofertas **antes** de usar os quatro novos prints em qualquer placar financeiro;
- `UNCERTAIN` não pode virar oferta confirmada automaticamente; revisar o fluxo de confirmação humana e persistência;
- deduplicar imagens por SHA256 privado antes de contar amostras. Mesmo 4 prints inéditos não sustentam precisão de produção.

**Risco de contexto no PR #16:** uma oferta real com texto sobreposto `você está online` pode ser classificada como mapa se o OCR perder o botão `Aceitar` e os minutos. Favor testar controles de overlay, fontes e OCR parcialmente ilegível antes de bloquear o salvamento de ofertas válidas.

## Bloqueio de CI identificado pelo auditor

No PR #16, run `43009735900`:
- `Parser, segurança e APK` = **failure**;
- `41 tests completed, 1 failed`;
- falha: `OfferTypeLot02Test.entregaMotoIsNotMisclassifiedAsPassengerMoto` em `OfferTypeLot02Test.java:11`, asserção do tipo `"Entrega Moto"`;
- `ML Kit real no emulador Android 35` = **cancelled**.

O resultado do PR #16 ainda **não autoriza APK pronto para instalação**. A equipe Android precisa inspecionar o valor real devolvido pela versão compilada do `OfferParser` e corrigir o motivo do teste antes de tentar nova execução. Não é apropriado eliminar o teste para obter CI verde.

## Limites e responsabilidades

- Auditoria independente: documentos e contadores em `tools/ocr_quality_audit/`, sem alterar Android, Gradle, workflows ou branches de outros agentes.
- Android: implementação espacial e repetição de CI em PR draft separado, sem merge automático.
- Proprietário: recebe apenas uma versão experimental quando a integração estiver de fato pronta, testes passarem e a instalação não ameaçar histórico. Os prints reais devem ficar fora do GitHub.
