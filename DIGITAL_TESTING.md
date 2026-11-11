# Vexo — Laboratório Digital, sem instalar APK a cada alteração

Este projeto de testes roda no **GitHub Actions**. Nenhuma conta da 99 é conectada; nenhuma corrida é aceita, recusada ou cancelada; o celular do usuário não é usado.

## Três camadas de teste

1. **Testes rápidos Java (JUnit):** executam o interpretador `OfferParser`, a trava `FinancialGuard` e cenários de regressão escritos com texto de ofertas. São determinísticos e ajudam a impedir que uma correção quebre outra.
2. **Android virtual (Google ML Kit real):** o GitHub cria um emulador Android 35, gera um card de corrida **sintético em memória**, executa `TextRecognition.getClient(...).process(...)` e verifica os valores reconhecidos. Não é mock do ML Kit.
3. **Auditoria Python independente:** será executada automaticamente quando o PR do segundo agente integrar a pasta `tools/ocr_quality_audit/tests`. A pasta não é criada nem alterada aqui.

### Como acompanhar

Abra a aba **Actions** do repositório, escolha **Vexo — Laboratório Digital (sem celular)**, confira os jobs `Parser, segurança e APK` e `ML Kit real no emulador Android 35`. Se algum teste falhar, verifique os logs e os arquivos XML/HTML de teste como artifacts da execução.

A automação dispara em **Pull Requests** e na branch principal após atualizações. Existe também um agendamento diário preparado, porém **o GitHub só o executa a partir da branch padrão quando esta alteração for aprovada e integrada**.

### O que é validado

- Compilação do aplicativo e regressões numéricas conhecidas
- Leitura OCR de texto renderizado em uma imagem fictícia em um Android virtual
- Casos em que valores incompletos devem ser marcados como suspeitos, nunca adivinhados
- A auditoria de relatórios quando o segundo agente for integrado

### O que ainda NÃO está validado

- Precisão de 99, 95,5% ou 100% em **prints novos reais da 99**
- Variações de aparência, pop-ups, fontes, DPI e modelos de celulares reais
- Leitura automática da tela de outro aplicativo (`MediaProjection` não foi implementado)
- Uso sem impacto na conta 99 / conformidade de políticas
- Disponibilidade de dados pessoais de passageiros: **não subir prints reais nem relatórios privados para Actions/PRs**

O resultado de um teste sintético aprovado não autoriza o Vexo a tomar decisões de corrida. Campos financeiros duvidosos permanecem sujeitos a conferência do motorista.

## Revisão e integração

Trabalho isolado na branch `feature/digital-test-lab`. A `main` não será alterada automaticamente. Depois do teste, revisar o PR, conferir funcionamento do job de emulador e as restrições de custo do GitHub Actions, e só então considerar integrar mediante autorização do proprietário.

Pontos a observar: emulador Android consome mais tempo de CI do que JUnit; testes de OCR em imagens sintéticas podem ser instáveis. Uma falha **não deve ser ocultada**; analisar a evidência antes de classificar como falso positivo.
