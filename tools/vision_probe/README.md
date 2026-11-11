# Experimento de detecção visual do Vexo

O protótipo compara pixels em memória antes do OCR. Começa pela metade inferior como pista, depois recebe a região do card localizada por uma leitura inteira. Um quadro que muda pede uma leitura inteira do quadro mais recente. A comparação não confirma identidade, preço, distância ou tempo. Se o mapa também estiver dentro da área observada, pode disparar OCR.

Durante a confirmação, um segundo quadro pode ir para OCR mesmo com pixels iguais. A leitura periódica de segurança limita a espera quando a mudança escapa da área observada. O chamador só registra um quadro depois que o OCR inicia, usando a vaga já controlada pelo `CaptureThrottle`. O teste usa 700 ms para a verificação periódica, a cadência do código de base. Reinício, perda de visibilidade e mudança de geometria exigem invalidar a região.

## Executar no computador

Com JDK 17 ou posterior, na raiz do repositório:

```sh
output=$(mktemp -d)
javac --release 17 -d "$output" tools/vision_probe/FrameChangeProbe.java tools/vision_probe/VisionProbeDemo.java
java -cp "$output" VisionProbeDemo
```

O teste usa buffer RGBA sintético de 1080 × 2400, com padding em cada linha, 80 aquecimentos e 300 amostras por região. Mede a comparação local, separada da captura Android, do OCR e do tempo até o aviso. Antes de ativar no app, medir a latência no telefone e comparar ofertas encontradas, campos críticos e acionamentos pelo mapa com gabarito manual. O experimento fica fora do APK.

## Primeira medição local

14 cenários sintéticos passaram na JVM. Resultados de uma execução no computador:

| Região | p50 | p95 |
|---|---:|---:|
| Metade inferior (1080 × 1200) | 1,467 ms | 1,665 ms |
| Região conhecida do card (960 × 520) | 0,555 ms | 0,646 ms |

A meta de 100 ms no telefone vai da aparição da oferta até a decisão de pedir OCR. O teste local mede apenas a comparação. No aparelho, medir também a espera pelo quadro, o tempo até o OCR começar (inclusive se houver outra leitura em andamento) e o tempo até o aviso após a confirmação.
