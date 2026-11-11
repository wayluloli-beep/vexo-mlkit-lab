# Revisão P0 — PR #17, lote 99 novo e integridade dos rótulos

**Escopo:** revisão independente de código e dos resultados declarados na Issue #8, sem acesso às imagens privadas, sem alterar Android nem fazer merge.

## Evidência nova — amostras não comparáveis

- O lote anterior de dez imagens teve 107/111 acertos (96,4%) na 0.3.5.
- O novo lote reportado teve **84/91 acertos (92,31%) em oito imagens, porém somente seis ofertas distintas**; duas imagens são variantes com overlay de rede social. Não interpretar diferença entre 96,4% e 92,31% como regressão estatística pareada: mudaram as imagens e as condições. Repetições não são observações independentes.
- Duas capturas reais adicionais eram posts incorporando ofertas, não ofertas ativas; precisam de teste de classificação de contexto fora do denominador financeiro.
- O usuário/Android informou um ZIP privado com 20 imagens distintas por hash, porém 16 ofertas avaliáveis e 4 posts; dentro das 16 há 14 variações de oferta, portanto novamente não se deve chamar 16 ofertas independentes sem agrupar as variantes por identificação humana.

## Risco de ROI em tripKm — o PR #17 é uma proteção parcial

Em dois screenshots com sobreposição, a imagem tinha só uma linha de trajeto reconhecida, relativa ao embarque. O ROI retornou essa distância como **viagem**, mesmo com duas leituras ampliadas concordantes. Isso prova que a concordância de variantes do mesmo OCR **não equivale** a validação semântica.

Na branch do PR #17, findRegions só oferece ROI de tripKm se reconhecer **duas linhas de trajeto min/km com caixas separadas verticalmente**. Correção conservadora razoável: quando há uma única linha reconhecida, abster-se; o FinancialGuard já bloqueou cálculo no lote observado.

**Bloqueio residual:** duas linhas min/km não garantem origem no mesmo card ou que a segunda seja a viagem. Uma pode vir de mapa/overlay, outra ser embarque, ou podem ser duas ofertas empilhadas. Critério mínimo para promover sugestão: delimitação de **mesmo card**, âncoras de embarque e viagem, caixa alinhada à rota, duas linhas atribuídas sem conflito; sem esses sinais, REVIEW_REQUIRED. No CI, acrescentar contraprovas de mapa com min/km, segunda oferta sobreposta e mesma imagem com uma linha cortada. Não adaptar a regra com valores de distância que pareçam plausíveis.

**Status de CI conferido:** run 43012952789 do PR #17, jobs Gradle/Java+APK e ML Kit no emulador Android 35 **completed/success**. É regressão sintética, não confirmação de que os dois falsos candidatos reais desapareceram. Reexecutar as mesmas imagens apenas localmente e revalidar.

## Auditoria P0 — Entrega Moto e tipo de oferta

A função equivalente(field, expected, actual) em BatchOcrActivity usa, para offerType, uma comparação permissiva de **presença de fragmentos**, inclusive:

    return (!e.contains("moto") || a.contains("moto")) && ...

Portanto um rótulo esperado **Entrega Moto** pode ser contado como OK quando o parser devolve **Moto**. Isso é um risco de superestimar o campo offerType, independentemente do número de imagens. A correção de parser no PR #16 que produz Entrega Moto é boa, mas **não conserta o comparador permissivo** em versões anteriores, nem detecta futuros subtipos omitidos.

Pedir ao agente Android: comparação canônica EXATA por modalidade (normalizar caixa/espaço/acentos e aliases expressamente documentados), sem substring. Cenários positivos e negativos: Entrega Moto ≠ Moto; Moto Negocia ≠ Moto; Negocia ≠ Padrão; Moto sem Entrega = Moto. Teste também a variante de erro OCR "Entrega Moto" cortada. Se o ground truth tem modalidade que o avaliador não entende, registrar pendência/revisão, não considerar acerto.

**Mitigação já aplicada pelo auditor:** em audit.py, quando offerType tem status ok mas os textos expected/actual são diferentes, o auditor produz warning de subtipo potencialmente ignorado e NÃO altera silenciosamente o denominador do relatório Android. Testes sintéticos de 2 cenários adicionados em tests/test_offer_type.py. É alerta, não substituto para reprocessar a exportação original.

## Campos rating/rides do caso 99_novo_006

OfferParser usa regex global que exige nota e quantidade de corridas **adjacentes ao termo corridas**:

    ([0-5][.,]\d{2})\s*[-·•.]?\s*(\d{1,5})\s*corridas

Quando o OCR separa os números por linhas, deixa de ver o separador, ou oculta o perfil, a regex não encontra. Isso é hipótese plausível para os dois ausentes (não temos texto OCR bruto da imagem para fechar causa).

**Mudança recomendada (Android, sem expandir regex global):** usar Text.Line / Text.Element com caixas, encontrar a região de perfil do passageiro **dentro do mesmo card** e exigir âncora textual "corridas". Associar candidato de rides ao termo por proximidade visual; associar rating a elemento em região vizinha do perfil e faixa 0–5, com ancoragem de ícone/contexto. Evitar pegar 4,94 do preço, minutos ou avaliação de uma postagem. Se não detectar o bloco ou âncora, retornar missing com revisão humana. Testar blocos em linhas separadas, outros números em mapa, rating sem rides e rides sem rating. Avaliar se há aumento de falsos positivos antes de habilitar recuperação.

## Separação de métricas por imagem/oferta/contexto

O utilitário Python novo cohort_audit.py exige **offerGroupId rotulado por pessoa** para consolidar imagens variantes da mesma oferta; não infere grupo por preço, rota ou OCR. Métricas de campo usam somente imagens rotuladas live_offer; posts/mapas aparecem na contagem de falso reconhecimento de contexto, não viram erros/acertos de campos. A saída é somente agregada, sem IDs, valores, prints ou OCR bruto. Cinco testes sintéticos locais passaram (modelo de oito imagens/seis ofertas, contextos negativos, ausência de grupo, falsos positivos e IDs duplicados).

**Limites:** a ferramenta NÃO reclassifica automaticamente as 20 imagens reais, NÃO valida rótulos nem altera a porcentagem publicada pelo APK; o agente Android/usuário precisa criar os metadados privados com identidade das ofertas e conferir o gabarito. Não publicar esses arquivos no GitHub. Comparação de precisão real continua condicionada à revisão de gabarito e replay da mesma base.
