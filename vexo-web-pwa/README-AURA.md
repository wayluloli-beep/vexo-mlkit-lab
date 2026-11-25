# Aura Sync — contrato de consulta v2

A Aura não é um chatbot que calcula a partir de texto. A interpretação local (ou Gemini, quando necessário) produz um objeto com intenção, período, plataforma e métricas. A consulta lê um único snapshot consistente de `Vexo.invoke('auraDados')`. O motor financeiro usa as mesmas regras do painel Finance; o teste de integração verifica a correspondência literal dessas regras.

- Perguntas reconhecidas, inclusive sequências e múltiplos indicadores, não usam a API.
- O Gemini recebe apenas a pergunta e o contexto de consulta estruturado, não recebe o histórico financeiro nem as linhas de corridas.
- O dispositivo valida o contrato antes de consultar os dados. Não confunde caixa com lucro, duração de corrida com jornada online, plataforma desconhecida com Uber/99 ou simulação com operação real.
- O endpoint v2 mantém a versão legada. O proxy pode alternar entre os dois modelos Flash-Lite quando há falha temporária, sem aumentar o limite configurado de tentativas. O serviço ainda depende da disponibilidade externa e do plano Render. A cota em memória não é controle de faturamento nem autenticação de produção.
- Os testes sintéticos verificam lógica, dados reais do motor, persistência e navegação em Chromium mobile. A voz é simulada no navegador; o Android físico e reconhecimento de voz ainda precisam de validação.
- Os APKs anteriores usaram chaves de assinatura temporárias. Não desinstale a versão anterior para testar outra; os dados locais não migram automaticamente entre pacotes.
