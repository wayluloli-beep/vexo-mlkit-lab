# Vexo OCR • Homologação automática 0.3.1

## O que este protótipo faz

Executa o **Google ML Kit no Android**, não um OCR simulado. Usa o mesmo `OfferParser.parse()` do laboratório 0.3 e testa os **10 prints reais** do pacote privado de homologação. A versão 0.3.1 possui identificador Android separado para não apagar ou sobrescrever os dados locais da versão 0.3.

## Execução no celular

1. Instale o APK de homologação 0.3.1.
2. Baixe o pacote `Vexo_OCR_0.3_Homologacao_10_Prints.zip` da conversa (não extraia).
3. Abra **Vexo OCR 0.3.1**, toque em **Teste automático · lote de prints**.
4. Toque em **Selecionar ZIP e testar tudo**, escolha o pacote em *Downloads*.
5. O aplicativo lê sequencialmente as imagens com ML Kit, compara com `manifest.jsonl` e apresenta divergências por campo.
6. Toque em **Exportar relatório JSON**. Esse arquivo é o que deve ser compartilhado para revisão, **sem precisar reenviar cada print**.

## Regras

- Imagens de homologação não são salvas no histórico do leitor.
- O relatório exportado contém valores OCR já interpretados e comparações com o gabarito, mas **não inclui fotos, mapas, endereços ou o texto bruto**.
- Alguns valores esperados são `null` no gabarito; isso significa que a informação não está visível, não que o valor seja zero.
- Erros de leitura / parser contam como divergências. A precisão é calculada **somente após rodar o pacote no celular**.
- O GitHub compila o APK. A compilação ou testes JUnit **não comprovam** que o ML Kit reconheceu os 10 prints.

## Limites

O teste é **offline/local** e usa imagens armazenadas pelo usuário. No contexto desta conversa, o ChatGPT não acessa a tela nem os apps instalados no celular remotamente. É necessário selecionar o ZIP uma vez no aparelho; depois a execução é automática.

**Privacidade:** não envie as fotos originais de passageiros ou endereço para repositórios públicos. O ZIP real de homologação deve permanecer privado.
