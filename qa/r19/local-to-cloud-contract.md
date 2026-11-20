# R19 · Primeiro uso e migração local → nuvem (#261–262)

## O que existe na R18

A edição manual funciona sem conta. Os dados abaixo ficam no `localStorage` da WebView, na origem `https://appassets.androidplatform.net`. A meta por hora é uma exceção nativa. Não há migração, identidade de nuvem ou consentimento de sincronização nesse fluxo. Para ler o legado, atualizar o mesmo pacote com assinatura compatível, manter a origem e não limpar dados. O APK interno é `com.trackingracing.aurora` e a R18 não habilita backup Android.

| Origem real | Tratamento proposto |
| --- | --- |
| `vexo.entry.sequence.x4` (`interview`/`app`), `vexo.entry.disclosure.v1` (versão da minuta) | Manter locais. A aceitação da minuta não autoriza envio. |
| `vexo.gain-profile.v1`, `vexo.gain-draft.v1`; preferência Android `vexo.gain-goal` / `hourly_cents` | Oferecer perfil concluído e meta ativa em centavos/h. Rascunho permanece local. Não confundir o campo de meta digitado com a meta ativa do Android. |
| `vexo.meu-veiculo.v1` (Ka), `vexo.meu-veiculo.<id>.v1` (demais), `{data,examples,refills}`; `vexo.meu-veiculo.selecao.v1`, `vexo.garagem.pintura.<id>` | Oferecer campos reais e abastecimentos `{km,full,amount,liters}` validados. Excluir os campos marcados em `examples`, a placa, seleção e pintura da primeira migração. `vexo.obd.ka-unit.v1` é vínculo do aparelho e fica local. |
| `vexo.turno-manual.v1`, `{active,history}` | Oferecer turnos encerrados com início/fim, lançamentos e totais. Turno ativo e rascunho continuam locais até encerrar. Preservar centavos inteiros e não confundir `null` com zero. |

Fonte auditada: `index.html`, `onboarding.html`, `veiculo.html`, `turno.js`, `AuroraActivity.kt`, configuração do APK e manifesto em `r18/aurora/`. Inventário por código, sem ler dados reais.

## Contrato proposto, ainda desligado

1. **Entrar sem conta** é o caminho padrão e funciona offline. Sem conta anônima no servidor, telemetria ou fila de envio criada em segundo plano. Depois de autenticar uma conta confirmada, mostrar categorias, contagens e destino em prévia local. Só enviar o que a pessoa selecionar e confirmar. Consentimento específico, versionado e vinculado à conta. Recusar, sair ou revogar pausa o envio sem apagar os dados locais. Não enviar OCR, GPS, OBD, capturas ou diagnósticos.
2. Ler só chaves permitidas, validar e montar um lote versionado sem sobrescrever o legado. Salvar IDs aleatórios por registro legado num manifesto local durável antes do primeiro envio, preservando ocorrências distintas. O servidor deduplica reenvios pela mesma conta e ID. Não deduplicar por valor, km ou horário. Aguardar confirmação por registro antes de marcar como importado e manter os originais mesmo depois dela. Falhas ou itens inválidos ficam locais com indicação para revisão.
3. Tratar horários do aparelho como valores históricos, não como ordem de versão. Usar revisão/CAS do servidor para atualizações. Em conflito preservar as duas versões e pedir escolha, sem substituição automática. Datas incoerentes não são corrigidas silenciosamente. Abastecimentos legados sem data mantêm a ordem original.

**Antes de ativar:** validar em atualização Android com dados sintéticos, modo offline, recusa, troca de conta, envio parcial seguido de retry, abastecimentos iguais distintos e relógio atrasado. Infra, autenticação e teste de isolamento por conta ainda pendentes. Nenhum envio realizado.
