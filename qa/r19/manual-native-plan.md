# Isolamento do Android manual R19

- Reconstruir primeiro a R18 verificada e a camada Web da R19. Sobrepor somente arquivos Android do candidato privado e materializar uma lista explícita de código compilado. Manter fontes e testes de OCR intactos no histórico do laboratório.
- Preservar classe de entrada, ID de pacote, origem da WebView, armazenamento do veículo e da meta. O nome histórico da ponte JavaScript permanece temporariamente por compatibilidade, mas seus únicos métodos são combustível, meta e versão.
- Cobrir a ausência de captura e sincronização, rotas locais, formatos das mídias e limites de entrada. Não adicionar permissão de notificação ou biblioteca OCR para resolver lint.
- Montar e verificar um APK privado. Comparar exame de pacote e relatório lint. Testes de código não substituem instalação, atualização, retorno do turno e inspeção visual.
