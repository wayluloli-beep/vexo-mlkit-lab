# Vexo — MediaProjection Fase 1: auditoria OCR de frames sucessivos

**Referência:** Issue #21. Escopo da auditoria, PR #7. É um contrato de testes e segurança, não uma implementação Android nem comprovação de compatibilidade com a 99.

## O problema novo

No laboratório antigo, um print gera uma avaliação. Na captura automática, a mesma oferta pode aparecer em dezenas de frames, mudar no meio de uma leitura ou ficar atrás de um mapa. Acurácia por campo não é suficiente. Sem controle temporal, o aplicativo pode gerar notificações duplicadas, combinar números de ofertas diferentes ou usar o resultado de uma sessão que o motorista já encerrou.

**Nunca deduplicar só por preço, km ou tempo:** ofertas diferentes podem coincidir nesses valores. Um hash de OCR bruto também pode vazar conteúdo sensível e mudar com ruído. No teste sintético, usar somente identificadores opacos de ofertas atribuídos pelo fixture. Nos lotes reais, grupos são rotulados manualmente em ambiente privado.

## Requisitos auditáveis

1. Uma sessão MediaProjection válida só começa mediante autorização do Android. Uma sessão tem um ID efêmero e um contador monotônico de frames.
2. Frame capturado fica em memória; limitar o ML Kit a **uma inferência por vez**, descartando frames intermediários se a captura for mais rápida que o OCR. Fechar cada Image em finally, inclusive erro/cancelamento.
3. Todo callback ML Kit carrega sessionEpoch e frameSequence. Quando a sessão para, incrementa-se o epoch e qualquer callback tardio deve ser ignorado, sem alterar resultados da tela, ganhos ou histórico.
4. Classificar o contexto como OFFER_CANDIDATE, NON_OFFER ou UNCERTAIN. Nada de registrar histórico financeiro automaticamente quando não houver confirmação humana.
5. Ao detectar incerteza sobre distância, dinâmica, modalidade ou origem da caixa, mostrar REVIEW_REQUIRED. Duas leituras do mesmo recorte não constituem verdade independente.
6. Nunca automatizar aceite, recusa ou cancelamento; não pedir acessibilidade para interagir com a 99; não exportar imagens, OCR bruto, perfis, rotas nem endereços.

## Matriz sintética de testes

| Cenário | Evidência de aceite |
|---|---|
| Mesmo card em 30 frames, com erros OCR esporádicos | Uma identidade de oferta; sem 30 notificações/linhas de histórico |
| Ofertas distintas com preço e km iguais | Não fundir duas ofertas porque números coincidiram |
| Oferta A → mapa → oferta B | Mapa não cria oferta, campos de A e B não se misturam |
| Post antigo com print de oferta | Não criar oferta ativa |
| Apenas pickupKm legível, tripKm encoberto | Não sugerir pickupKm como tripKm; manter bloqueio |
| Ícone de raio OCR como dígito 4 | Não converter 42,8x para 2,8x por regra textual |
| Stop enquanto ML Kit está em processamento | Callback tardio descartado; buffers/serviço liberados |
| Rotação ou seleção de janela de aplicativo | Atualizar resolução e invalidar coordenadas ROI antigas |
| Tela protegida ou sem pixels | Não tentar contornar FLAG_SECURE; abster |
| Nova sessão usando token antigo | Recusar reutilização; solicitar autorização válida |
| ML Kit artificialmente lento | Uma inferência simultânea no máximo; descartar backlog |

## Contrato de eventos do test harness (somente dados fictícios)

O Android pode emitir dados **sintéticos, sem conteúdo da tela**, com:
- sessionEpoch, frameSequence, frameTimestampMs;
- tipo de contexto, fixtureOfferGroupId opaco (somente nos testes gerados);
- contagem de campos reconhecidos/incertos, financialGuardBlocked;
- indicador de nova notificação/registro, indicador de callback tardio;
- tempo de inferência e número de releituras ROI.

A auditoria separa métricas por **frame**, por **oferta única fictícia** e por **sessão**: falsos candidatos, duplicatas, abstenções, callback após parada, falso bloqueio de oferta e cálculo financeiro com campo inseguro. Na fase inicial não exportar frames reais nem OCR bruto.

**Aceite digital mínimo:** executar CI com telas sintéticas/atividade própria, teste de Stop durante inferência, teste de janela/resize e 30 frames repetidos. Evidência exigida: zero callbacks tardios aplicados, zero históricos automáticos, zero confusão de pickup/trip, zero falsa oferta em mapa/post. Android virtual não comprova captura da 99.

## Revisão cruzada dos PRs #19 e #20

- PR #19 protege parcialmente a oferta sob overlay: devolver UNCERTAIN em vez de bloquear automaticamente é prudente. Testar também publicação de rede social com print embutido e o uso isolado da palavra Posts fora de uma publicação.
- PR #20 cria regiões de rating e rides apenas se houver linha corridas entre preço e primeiro trecho; isso **não demonstra que pertencem ao mesmo card**. Também cria duas regiões idênticas se ambos faltarem e executa duas variantes de OCR por campo: até quatro passagens sobre os mesmos pixels. **Melhoria prioritária a avaliar na branch Android:** uma releitura compartilhada da região de perfil para tentar extrair os dois campos, sem promover candidatos incertos. Em streaming, custo por frame faz diferença.
- Condicionar ROI às fronteiras do card e criar negativos com duas ofertas simultâneas, linha corridas num post e perfil com números de mapa adjacentes.

## Conformidade Android / limites

A documentação oficial exige consentimento a cada sessão. No Android 14+, o token é de uso único para criação de VirtualDisplay, com foreground service do tipo mediaProjection e callback onStop para liberar recursos. A API suporta seleção de aplicativo e ajustes de tamanho/rotação. Android 15 QPR1 exibe chip de sessão e interrompe captura no bloqueio da tela.

Fontes oficiais:
- https://developer.android.com/media/grow/media-projection
- https://developer.android.com/about/versions/14/behavior-changes-14

**Próxima tarefa:** Android disponibilizar harness sintético temporal com contadores agregados; agente auditor mede falsas ofertas, repetição, abstenção e estado de sessão sem qualquer screenshot privado no GitHub. Nada de merge nem promessa de captura silenciosa sem consentimento.
