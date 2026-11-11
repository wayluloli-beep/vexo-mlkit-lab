# Revisão independente 02 — callbacks de parada e resize

Escopo: **Agente 3**, inspeção somente leitura de
`app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java`
na branch `feature/media-projection-lab`, hash do arquivo
`12c0b67315f2e723cb745af3cc342286a9f44580`, observado em
11/11/2026. Os riscos são baseados no **código-fonte**, não em
teste de captura real ou falha explorada.

## Evolução positiva

- Serviço `LiveCaptureService` agora existe, é declarado `exported=false`
  no Manifest, com `foregroundServiceType=mediaProjection` e permissões FGS.
- Fluxo cria o MediaProjection com consentimento nativo, faz uma chamada
  `getMediaProjection`, registra `onStop`, cria um VirtualDisplay e usa
  `ImageReader.acquireLatestImage`. Cada `Image` adquirida é fechada em
  `finally`. Captura recente limitada por `CaptureThrottle`.
- Há `START_NOT_STICKY`, notificação persistente e ação de parada;
  sem automatizar decisões do motorista, sem código aparente para upload
  de screenshots.
- A implementação ainda precisa **compilação CI comprovada e testes Android**
  de fluxo, incluindo autorização e teardown em API 34/35/36.

## Risco prioritário 1 — onStop assíncrono mantém sessão válida durante uma janela

Trecho atual:

```java
@Override public void onStop() {
    main.post(() -> shutdown());
}
```

`shutdown()` só define `active=false` e incrementa `epoch` quando
a main thread executar o Runnable. Até lá, um `Task.addOnCompleteListener`
já enfileirado poderá passar a checagem `active && epoch.get()==session`
e chamar `LiveCaptureState.candidate` ou atualizar a notificação **depois
que a sessão foi encerrada pelo sistema**, porque o callback de Stop ainda não
invalidou a sessão de forma síncrona.

**Recomendação:** executar a invalidação atômica de epoch e sinal de parada
no próprio callback `onStop`, **antes de enfileirar cleanup na main thread**.
O cleanup idempotente fecha buffers/recursos; resultados tardios nunca atualizam
UI/notificação/histórico. Ter cuidado com concorrência quando o Service reiniciar.
Em emulador, simular Stop e callback pendente com barreira controlável, além de
bloqueio de tela/chip Android 15 QPR1.

## Risco prioritário 2 — ImageReader provisório vaza se resize falha

Trecho resumido atual:

```java
try {
    ImageReader replacement = ImageReader.newInstance(...);
    virtualDisplay.resize(...);
    virtualDisplay.setSurface(replacement.getSurface());
    imageReader = replacement;
} catch (Exception ex) {
    main.post(() -> shutdown());
}
```

Se `setOnImageAvailableListener`, `virtualDisplay.resize` ou
`setSurface` lançar exceção **antes de `imageReader=replacement`**, a
referência ao leitor recém-alocado fica somente na variável local do `try`.
O `shutdown()` fecha `imageReader` antigo, mas não `replacement`.

**Recomendação:** declarar variável de substituição fora do `try`,
usar `boolean ownershipTransferred` ou `finally` condicional e sempre
fechar o reader provisório em falha de qualquer etapa. Só fechar reader
antigo após transferência bem-sucedida; não criar segundo VirtualDisplay.
No emulador, injetar falhas separadas em `resize` e `setSurface` e
contar leitores criados/fechados (zero vazamentos).

## Outras verificações sugeridas (ainda não validadas)

- **Memória e aquecimento:** `Bitmap.createBitmap(paddedW,h)` aloca
  bitmap RGBA de tamanho integral antes de reduzir para largura 1080.
  Requer orçamento máximo em pixels/bytes *antes* de criar `ImageReader`,
  inclusive durante resize, e teste de OOM/temperatura em aparelhos pequenos.
  Bitmap intermediário pode não ser reciclado se uma alocação posterior falhar.
- **Gate OCR:** callback Task atrasado, depois da parada e de nova autorização,
  precisa liberar somente o gate antigo, sem bloquear/liberar inferências da sessão nova.
  `CaptureThrottle` atual é instância por sessão; confirmar em teste de corrida.
- **Visibilidade e telas protegidas:** `onCapturedContentVisibilityChanged(false)`
  suspende OCR, mas não pode reter resultado antigo. Testar `FLAG_SECURE`
  usando app de testes próprio, não burlar proteção de 99/Uber.

## Evidência automatizada

O script `lifecycle_review.py` executa duas heurísticas conservadoras:
`STOP_INVALIDATES_EPOCH_BEFORE_DISPATCH` e
`RESIZE_REPLACEMENT_RELEASE_ON_EXCEPTION`. O CI testa **9 casos sintéticos**:
stop adiado, invalidação antes/depois do post, reader perdido, cleanup do
provisório, resize ausente, chaves aninhadas, modo sem serviço, modo obrigatório.
Ao inspecionar a branch do Agente 1, o workflow reporta PASS/FAIL com SHA
exato do checkout, **sem modificar arquivos da branch alheia**.

Heurísticas de texto podem gerar falsos positivos/negativos: todo achado deve
ser confirmado por revisão de código e instrumentação. Não há afirmação de
exploit, de eficácia real da 99, de redução mensurada de bateria, nem
de aptidão de um APK para produção.

## Fontes Android oficiais

- https://developer.android.com/media/grow/media-projection
- https://developer.android.com/reference/android/media/projection/MediaProjection.Callback
- https://developer.android.com/reference/android/media/ImageReader
- https://developer.android.com/about/versions/15/behavior-changes-all
