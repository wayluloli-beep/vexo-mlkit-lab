# Central Vexo · Visual congelado para discussão (v1)

**Status:** referência visual aprovada provisoriamente em conversa de 21/11/2026. **Não implementar no aplicativo ainda.** É um registro de design, não aprovação funcional nem APK gerado.

## Aparência de referência
- Central escura, estilo 99, com detalhes amarelo quente e identidade X VEXO.
- Widgets de vidro fosco jateado semitransparente, blur/translucidez, borda suave e contraste suficiente em carros ao sol.
- Fonte visual inspirada no Google Gemini (Google Sans Flex / Google Sans, com fallback apropriado; verificar licença/disponibilidade em app antes de incorporar fontes).
- Tipografia média mais destacada, sem desperdício de espaço. Dados sempre legíveis.
- Tamanhos permitidos por widget: pequeno, médio e grande com conteúdo semanticamente distinto, não escalonamento da mesma apresentação.
- Pequeno: indicador principal e legenda curta.
- Médio: valor dominante bem grande, valor auxiliar importante, faixa/indicação e linha útil de contexto.
- Grande: análise, comparação, histórico/gráfico e ações aplicáveis.
- Central modular com grade alinhada; perfil Profissional e Uso pessoal; edição e rearranjo posterior.

## Gadgets demonstrados com dados explicitamente simulados
- Meta diária: P = R$ 280 e 70%; M = valor R$280 + faltam R$120 + progresso + 12 corridas; G = meta R$400, corridas, ganhos/hora, despesas.
- Consumo: P = 11,1 km/L; M = 11,1 km/L + autonomia 394 km + R$0,53/km + abastecimento 35,5L; G = histórico, gráfico, consumo, autonomia, custo/km, valor e volume abastecido.
- Jornada: P = 6h20; M = 6h20 + pausa 35min + atividade 5h45 + início 07h40; G = distribuição atividade/pausa e resumo detalhado.
- A versão demonstrativa em conversa era uma prévia interativa; este documento **não é** o código-fonte integral dela.

## Decisão de interação ainda ABERTA
- Pergunta: tocar no widget abre expansão em sobreposição (*bottom sheet*) ou leva ao módulo completo?
- Sugestão a discutir: toque abre painel de detalhes ocupando parte da tela; ação 'Ver tudo' navega ao módulo correspondente.
- Nenhuma solução de toque definida pelo usuário até o momento.

## Cuidados
Não alterar Aura Sync, OCR, assinatura, módulos automotivos ou rota inicial até autorização explícita. Valores fictícios devem estar marcados como demonstração. Para condução, evitar fluxos que exijam manipulação visual prolongada.
