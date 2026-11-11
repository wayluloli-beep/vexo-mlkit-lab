# VEXO OCR 0.3 — histórico e backup (laboratório)

## Para testar só pelo Android
1. Instale o novo aplicativo **Vexo OCR 0.3** ao lado do anterior. **Não desinstale a versão 0.2**.
2. Abra na 0.3 os dois prints que você já usou: R$ 43,09 e R$ 7,70.
3. Confira todos os campos e toque em **Confirmar e guardar correções**.
4. Toque em **Exportar backup JSON**, escolha um local privado no celular e confirme que o arquivo foi criado.
5. Teste a importação do mesmo JSON com **Importar backup JSON**: devem aparecer 0 ofertas novas e as existentes como duplicadas. Não deve apagar nem duplicar nada.

## Por que a 0.3 não pega automaticamente os dados da 0.2?
O Android isola o armazenamento interno de cada pacote. Além disso, as versões anteriores foram assinadas com chaves de depuração temporárias por cada executor do GitHub Actions. Por isso, não se pode assumir que a 0.3 instalará como atualização direta da 0.2. Foi adotado outro applicationId e outra área de dados. **Não há migração automática** do histórico da 0.2; ele continua na versão antiga. Refazer os dois testes na 0.3 permite criar o primeiro backup exportável.

## Limites e comportamento
- O processamento OCR usa o Google ML Kit no aparelho. O app não envia prints para o GitHub ou a uma API.
- O backup contém **somente campos estruturados e correções confirmadas**, com identificadores UUID, data e versão do formato. Não inclui a imagem nem o texto OCR bruto.
- É um **arquivo JSON sem criptografia**. Guarde em pasta privada e não publique no GitHub.
- Inclui um hash SHA-256 do conteúdo para detectar corrupção acidental. O hash **não é assinatura digital** e não prova autoria.
- Em importações, o usuário confirma a operação; registros existentes são preservados e duplicatas são ignoradas. O sistema rejeita versão desconhecida, valores inválidos e dados alterados.
- O histórico de laboratório tem limite de 2.000 registros para evitar um armazenamento local ilimitado no SharedPreferences. Se atingir esse limite, não exclui registros silenciosamente.
- Ainda não existe modelo próprio retreinado, banco de dados Room, atualização com assinatura estável nem validação extensiva de interface em muitos Androids.
- Este APK é de desenvolvimento, não de distribuição comercial.

## O que testar
- Exportar e importar sem perder registros.
- Importar de novo e conferir que não duplicou.
- Cancelar o seletor de documentos sem mudar o histórico.
- Tentar importar um JSON que não é backup; o app deve recusar.
- Reiniciar o app e conferir a contagem de registros.
