# VEXO — Leitor de prints 0.2

Este laboratório Android usa Google ML Kit Text Recognition **no aparelho** para ler texto de prints de ofertas. A camada `OfferParser` aplica regras determinísticas ao texto para extrair valor principal, km exibido, dois trechos (busca/viagem), avaliação, corridas e contrapropostas.

## Uso
1. Escolha um print privado da galeria.
2. Revise os campos que aparecerem e compare com a imagem original.
3. Edite os erros e toque em **Confirmar e guardar correções**.
4. Os campos confirmados e as alterações ficam em `SharedPreferences` local, com no máximo 50 registros recentes. Prints e texto OCR bruto não são persistidos pelo aplicativo.

## Importante
- ML Kit faz reconhecimento de texto por um modelo pré-treinado pelo Google.
- O parser é **baseado em regras**, não é um segundo modelo treinado.
- Correções **não retreinam** o ML Kit. Nesta versão elas são guardadas para análise e evolução futura.
- Informações duvidosas ficam vazias em vez de serem inventadas.
- Não há captura automática, upload de imagens ou integração com o Vexo principal.
- A base de testes de duas ofertas usa strings OCR, sem publicar imagens com endereços no repositório.
- A versão 0.2 está sujeita a testes em mais aparelhos e prints. A confirmação manual permanece obrigatória.

## Build
O workflow de GitHub Actions prepara o projeto extraindo a base v0.1 e mantendo os arquivos v0.2 do repositório (`unzip -n`). Em seguida executa `testDebugUnitTest` e `assembleDebug` e salva o artefato `Vexo-MLKit-APK`.
