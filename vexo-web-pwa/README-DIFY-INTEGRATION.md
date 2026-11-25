# Integração Aura / Dify / dashboards (laboratório)

Branch isolada, derivada da Aura Sync 2.2. Não substitui a versão instalada nem o proxy Render atual.

## Contrato
- `aura-dashboard-context.js` lê `Vexo.invoke('auraDados')` uma vez por consulta estratégica. Projeta apenas agregados; exclui corridas MOB-* e despesas vinculadas a elas. Não envia identificadores de corrida, endereços ou linhas financeiras. Resultados não disponíveis são nulos. Consumo/custo de combustível por km são taxas atuais, não necessariamente históricas. A meta disponível na base é mensal; não inferir meta diária.
- `localWire` reconhece um conjunto restrito de perguntas completas de indicador/período. O `AuraAdapter` e o `AuraQueryEngine` existentes executam localmente. Perguntas ambíguas ou alterações de jornada não são interceptadas.
- `window.VexoAuraAdviceTransport` é uma interface opcional de transporte autenticado. Só deve ser instalada após uma sessão verificada e consentimento para o envio dos indicadores agregados ao provedor. Se indisponível, o fluxo anterior permanece. Se falhar, há fallback local de orientação. A chave Dify jamais pertence a HTML, JS público, APK ou localStorage.
- `server/aura-dify-bridge.cjs` valida a forma dos dados recebidos e monta uma chamada ao app Dify com `inputs.vexo_context`, criando contexto novo por requisição. Exige autenticação verificada e reserva atômica de quota injetadas pelo servidor; não é um servidor HTTP público autônomo.

## Ativação segura (pendente)
1. Revisar prompt da Aura 5.2 para tratar vexo_context como dado não confiável, distinguir período e taxa atual, e nunca afirmar que uma simulação é operação real. Publicar apenas o laboratório validado.
2. Criar a chave de serviço **do aplicativo Dify 5.2**, distinta da API Gemini já configurada. Armazenar somente no ambiente secreto do servidor. Não colocar a chave no repositório.
3. Montar handler em endpoint HTTPS autenticado; limitar tamanho do corpo antes do parse JSON, validar sessão, origem/CSRF conforme transporte, e aplicar limites persistentes compartilhados por projeto e usuário. Reservar 2 chamadas por requisição no fluxo atual. Não habilitar sem sessão/controle de quota efetivos. O proxy Render existente está em outro repositório e não possui esses mecanismos. Não mudar seu deploy ativo.
4. Conectar o transporte do cliente a esse endpoint mediante sessão real, nunca com segredo incorporado ao cliente. Testar primeiro com dados sintéticos, depois com dados autorizados; verificar atualização após finalizar corrida e lançar abastecimento/despesa. Confirmar que chamadas ao Dify e aos modelos Gemini correspondem aos logs.
5. Medir latência, tokens e cota antes/depois; não atribuir a redução de chamadas a todas as perguntas, somente ao conjunto local validado. Testar APK e PWA no dispositivo.

## Testes
`node test-aura-dify-integration.cjs` dentro de vexo-web-pwa.

O teste usa o motor JS real e dados sintéticos, com transporte Dify, identidade e reserva de quota simulados. Não consome API. Não substitui a validação do servidor implantado, da autenticação, da concorrência real da quota persistente, nem do navegador/Android.
