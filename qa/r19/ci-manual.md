# Gate do beta manual Vexo

O produto atual é Android Kotlin com WebView, dados e testes próprios em JavaScript. O gate roda contra a árvore `aurora/` já materializada, não contra os arquivos do pacote de QA antes de aplicar as camadas.

Na cópia de trabalho deste candidato, rode o modo Web a partir do diretório `r19/`:

```sh
node qa/ci-manual.cjs web aurora
```

O modo Web valida sintaxe de JavaScript avulso e inline nos HTML do app e executa todos os `*.test.cjs` em `qa/` com `VEXO_SOURCE_DIR` apontando para a árvore validada. Ele gera `VEXO_CI:WEB_PASS` se terminar sem falhas. Isso não valida Kotlin nem dispensa o gate de Android.

## Como encaixar no GitHub Actions

Na etapa que já reconstrói o código em `qa/run-live.sh` da R18, aplique e verifique também a camada R19. Em um job que tenha SDK Android do projeto, Java 17 e o Gradle 8.11.1 com o SHA-256 verificado como na R18, rode depois da preparação:

```sh
node qa/ci-manual.cjs android "$work/src/aurora" "$work/gradle-8.11.1/bin/gradle"
```

O modo Android repete o gate Web, recusa SDK ausente, exige sucesso de `:app:lintDebug` e `:app:testDebugUnitTest`, e lê o relatório XML para impedir que advertências de lint passem com exit code zero do Gradle. Se a versão inicial revelar avisos já presentes, revise a lista e resolva ou documente as exceções no projeto antes de exigir este check. Não importe uma baseline ampla que esconda novas regressões.

O script e seus testes não publicam builds, não alteram permissões nem habilitam proteção de branch. Para impedir merge automaticamente, um workflow deve executar o modo Android em cada PR e seu check estável deve ser configurado como obrigatório na branch de destino. O workflow privado R18 é uma validação pontual acionada por criação de branch e não fornece um check obrigatório de PR. Preserve-o como verificação de upgrade e fluxo de dispositivo, distinta deste gate. Nem o build `.aab` de release nem testes em emulador ou aparelho fazem parte deste script.
