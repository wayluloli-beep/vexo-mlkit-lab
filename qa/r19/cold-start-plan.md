# Vexo R19 — medição de abertura a frio no Android

**Situação:** comparação de código com a R18, sem medição em APK instalado até aqui. Este ambiente não tem `adb` no `PATH` nem `/dev/kvm`. O tempo real da R18 e da R19 no Android de destino continua **não medido**. Testes de VM/HTML e o tempo do arquivo de vídeo não substituem essa medição.

## O que a R18 já faz

- `AuroraActivity.onCreate` inicializa a WebView e abre `aurora/index.html`. Quando `vexo.entry.sequence.x4` é `app` e `vexo.entry.disclosure.v1` contém a versão vigente, o script faz `location.replace('./central.html')` **antes** de exibir a abertura ou atribuir o MP4. Portanto, tirar o vídeo do retorno não é um ganho novo sobre a R18. Ainda há inicialização da WebView, carregamento do documento intermediário, leitura de armazenamento e carregamento da Central.
- No primeiro uso, sem dados anteriores e sem preferência de movimento reduzido, a R18 marca `interview` antes do vídeo. O fluxo vai às boas-vindas quando o vídeo termina, é pulado, falha ou alcança o temporizador de 18 s. Um reinício depois de gravar `interview` não deve repetir a abertura. Termos desatualizados ou não aceitos não são um caso de retorno normal à Central.
- O MP4 da R18 tem **10,026667 s**, 1080 × 1920, H.264, 24 fps e 2.147.258 bytes pelo `ffprobe` no arquivo de origem. É a duração do arquivo, não o tempo de decodificação, reprodução observada ou chegada às boas-vindas.
- Na área pronta, a R18 mostra `Painel do motorista` e a ação de turno. Esse texto e o botão `Iniciar turno` já existem no HTML, antes de os scripts `defer` registrarem as ações e restaurarem o estado. Nem o primeiro frame, nem `onPageFinished`, nem `am start -W` certificam por si só que a Central responde. `Meu veículo` é carregado sob demanda pelo iframe; o `onStart` da edição manual não inicia o agendador de captura nem aquece o modelo OCR.

## Preparar a comparação

Use o **aparelho Android de destino** e os APKs R18/R19 do mesmo tipo de distribuição. Registre SHA-256, versão, pacote/Activity resolvidos, modelo, API, versão do provedor WebView, frequência/modo da tela, configurações de animação, rede, estado térmico e modo de energia. Use a mesma tela inicial, perfil de teste e condições nos dois lados. Deixe a bateria sem economia de energia e o aparelho esfriar se houver aquecimento. Não compare debug com release, aparelho com emulador, ou instalação limpa com atualização. Um emulador é útil para verificar rotas, mas o seu tempo não representa o do aparelho.

Resolva o componente a partir do APK instalado, sem presumir o sufixo do pacote. Por exemplo, o Gradle da R18 acrescenta `.aurora` no debug, enquanto o caminho de QA dedicado da R18 usa `com.trackingracing`.

```bash
ADB=adb
SERIAL='SERIAL_DO_APARELHO'
PKG='PACOTE_DO_APK_INSTALADO'
"$ADB" -s "$SERIAL" shell getprop ro.product.model
"$ADB" -s "$SERIAL" shell getprop ro.build.version.sdk
"$ADB" -s "$SERIAL" shell dumpsys webviewupdate
"$ADB" -s "$SERIAL" shell cmd package resolve-activity --brief \
  -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p "$PKG"
```

Use exclusivamente um perfil de teste e faça as reinstalações em aparelho/usuário dedicado. Preserve as preferências, a meta e os dados locais entre execuções de retorno. Não limpe dados nessa série. Se a atualização pedir a nova versão dos termos, anote o comportamento separadamente e aceite pelo fluxo normal antes de iniciar a série de retorno elegível.

## A — primeira abertura, instalação realmente nova

1. Faça três instalações limpas de cada versão no aparelho de teste. Em cada uma, não restaure backup, não abra o app antes e mantenha movimento reduzido desligado para a reprodução normal. Filme a tela externamente a 120 fps, idealmente 240 fps, com o toque perceptível no vídeo. Faça uma abertura separada para cada teste de pular, minimizar/forçar parada durante a mídia e preferência de movimento reduzido. Não misture esses números com a reprodução normal.
2. Use como `t0` o primeiro frame do toque no ícone. Marque `t_poster` quando aparecer o pôster, `t_video` quando aparecer movimento real, `t_ultimo` no último frame animado e `t_welcome` no primeiro frame das boas-vindas com `Entrar no Vexo` visível. Não confunda pôster com vídeo. Registre por passagem a causa observável da saída, como fim normal, toque para pular, fallback ou causa indeterminada. Se o vídeo for omitido, os campos de mídia ficam `N/A` e não `0`.
3. Guarde `t_poster − t0` e `t_video − t0` como latências, `t_ultimo − t_video` como tempo observado de reprodução e `t_welcome − t0` como tempo para as boas-vindas. Verifique em separado que `Entrar no Vexo` responde no estado adequado, sem somar a leitura ou o aceite dos termos. Ao testar interrupção, a reabertura deve ir para o estado correto de boas-vindas/termos e não repetir a mídia se `interview` já havia sido gravado.

## B — retorno a frio, da parada do processo à Central utilizável

1. Em cada versão, conclua a entrada do jeito normal, aceite os termos vigentes e tenha o mesmo perfil de teste com uma meta fixa e sem turno ativo. Confirme que o perfil abre a Central e mantenha os mesmos dados durante a série. Faça duas execuções de preparo, marcadas fora da amostra, e 20 execuções medidas por versão. Se viável, alterne os blocos R18/R19 mantendo os estados equivalentes. Registre a primeira abertura após instalar/atualizar separadamente se for relevante, porque a compilação e os caches podem estar diferentes.
2. Volte ao launcher e execute `"$ADB" -s "$SERIAL" shell am force-stop "$PKG"`. Verifique em cada tentativa que `"$ADB" -s "$SERIAL" shell pidof "$PKG"` não retorna PID antes de abrir. Não troque uma parada real por Voltar/Home. Uma parada de processo preserva arquivos, dados da WebView e caches do sistema. Não equivale à primeira instalação ou ao primeiro uso após reiniciar o aparelho.
3. Filme do toque no ícone até a primeira ação respondida. Na mesma gravação, marque `t0` no primeiro frame do toque no ícone e `t_central` no primeiro frame estável em que título e ação primária aparecem sem vídeo/diálogo. Verifique a ação com `Configurações` em toque real assim que o botão estiver visível. Se não responder, anote o toque e tente novamente após 250 ms, até a resposta ou o timeout de 15 s. Marque `t_tap_ok` no toque aceito e `t_resposta` no primeiro frame do cabeçalho `Configurações` com a aba ativa. Volte a `Início` ao fim. Navegar para Configurações não deve criar turno ou editar preferências. Confirme em um ensaio funcional separado da série que `Iniciar turno` também funciona, usando um perfil descartável.
4. Registre `t_central − t0` como **Central visível** e `t_resposta − t0` como **Central visível com ação comprovada**. A segunda é uma medida de ponta a ponta que inclui a reação de quem toca e a renderização do resultado. Registre também `t_tap_ok − t0` como um limite superior de prontidão de entrada e `t_resposta − t_tap_ok` para revelar a parcela de resposta da ação. Não substitua esses números por uma leitura de DOM ou pela primeira Activity desenhada. Use o mesmo operador ou método nas duas versões. Marque qualquer parada, tentativa sem resposta, vídeo indevido, boas-vindas indevidas ou timeout. Não descarte falhas como se fossem amostras lentas.
5. Se também for necessário o tempo literal de **solicitar parada até ver uma ação respondida**, sincronize o terminal com a gravação colocando terminal e aparelho no mesmo vídeo, marcando a solicitação da parada e usando um intervalo de relançamento fixo após a confirmação de ausência de PID. Relate esse total e o intervalo de preparação separadamente. A métrica comparável de abertura a frio começa no relançamento depois de confirmada a parada, não no tempo de espera do operador.

Como diagnóstico complementar em um lote separado, salve a saída de `"$ADB" -s "$SERIAL" shell am start -W -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$COMPONENT"` após cada parada confirmada. Use `COMPONENT` com o pacote/Activity retornado pela resolução. Se disponível, use Perfetto com atividade/WM, escalonador e trilhas gráficas para localizar o custo entre o lançamento, a criação da WebView e a primeira composição. Não cite resolução ou marcadores que o trace não tenha. Evite `uiautomator dump` repetido, screenrecord e profiler na coleta principal para não acrescentar carga à inicialização. FPS nominal de câmera não substitui os timestamps reais do vídeo se a gravação tiver taxa variável.

## Evidência e decisão

- Guarde o vídeo original com timestamps, tabela por repetição e metadados de aparelho/APK. Registre versão, cenário, repetição, PID antes, tempos de cada marco, cliques sem resposta e motivo de falha/timeout. `am start -W` e trace ficam anexos diagnósticos e não substituem a leitura de UI.
- Na série A, informe os valores individuais e faixa. Na B, informe mediana, p90 por posto `ceil(0,90 × n)`, número de sucessos/20 e número de falhas por motivo para cada versão. Calcule o delta absoluto e percentual da R19 contra a R18 para as duas métricas principais. Quando o p90 de todas as tentativas cair na região de timeout, informe como censurado em 15 s em vez de publicar o p90 apenas dos sucessos como se fosse o resultado de toda a série.
- A R19 deve manter a abertura inicial separada, nunca exibir o vídeo no retorno elegível, respeitar a entrada e os termos e permitir ação real na Central sem falhas novas. Só declare ganho de velocidade objetivo se as distribuições no aparelho sustentarem a diferença além da granularidade da captura e da variação das amostras. Sem o dispositivo, o máximo verificável aqui é o comportamento previsto pelo código, não um tempo de abertura.
