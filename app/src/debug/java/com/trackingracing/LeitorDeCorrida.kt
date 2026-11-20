package com.trackingracing

import java.util.Locale

/** Um pedaço do caminho: quanto tempo, quantos km e o endereço (se achou). */
data class Trecho(val minutos: Int, val km: Double?, val endereco: String?)

/** Tudo o que o robozinho conseguiu entender de uma corrida. Vazio = null. */
data class Corrida(
    val preco: Double?,
    val notaPassageiro: Double?,
    val viagensPassageiro: Int?,
    val busca: Trecho?,   // do motorista até o passageiro
    val viagem: Trecho?,  // do passageiro até o destino
    val paradas: Int?,
    val verificacao: String?
) {
    private val kmTotal: Double? =
        if (busca?.km != null && viagem?.km != null) busca.km + viagem.km else null
    private val minutosTotal: Int? =
        if (busca != null && viagem != null) busca.minutos + viagem.minutos else null

    /** O texto bonitinho que aparece no app e na notificação. */
    fun resumo(hora: String): String {
        val linhas = mutableListOf<String>()
        linhas += "Última corrida lida às $hora"
        linhas += ""
        linhas += "💰 Preço: " + (preco?.let { dinheiro(it) } ?: "não achei")
        linhas += "⭐ Nota do passageiro " + (notaPassageiro?.let { numero(it, 2) } ?: "?") +
            " | " + (viagensPassageiro?.toString() ?: "?") + " viagens feitas"
        if (busca != null) {
            linhas += "🚗 Busca: ${busca.minutos} min | " + (busca.km?.let { numero(it, 1) + " km" } ?: "distância não lida")
            linhas += "     " + (busca.endereco ?: "endereço não achei")
        }
        if (paradas != null && paradas > 0) linhas += "🛑 Paradas: $paradas"
        if (viagem != null) {
            linhas += "🏁 Viagem: ${viagem.minutos} min | " + (viagem.km?.let { numero(it, 1) + " km" } ?: "distância não lida")
            linhas += "     " + (viagem.endereco ?: "endereço não achei")
        }
        if (kmTotal != null && minutosTotal != null) {
            linhas += "📏 Total: $minutosTotal min | ${numero(kmTotal, 1)} km"
            if (preco != null && kmTotal > 0 && minutosTotal > 0) {
                linhas += "💵 Ganho por km: " + dinheiro(preco / kmTotal)
                linhas += "⏱ Ganho por hora: " + dinheiro(preco / (minutosTotal / 60.0))
            }
        }
        return linhas.joinToString("\n")
    }

    private fun dinheiro(v: Double) = "R\$ " + String.format(BR, "%,.2f", v)
    private fun numero(v: Double, casas: Int) = String.format(BR, "%.${casas}f", v)

    private companion object {
        val BR: Locale = Locale.forLanguageTag("pt-BR")
    }
}

object LeitorDeCorrida {

    // "R$ 72,32" (o leitor às vezes confunde o $ com S, então aceitamos os dois)
    private const val DINHEIRO = """R\s*[S$]\s*(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})"""

    private val regexAceitar = Regex("""Aceitar\s+por\s*$DINHEIRO""", RegexOption.IGNORE_CASE)

    // Preço solto na tela, mas que NÃO seja "R$ 2,17/km" nem "R$ 118,61/hora"
    private val regexPrecoSolto = Regex("""$DINHEIRO(?!\s*/)""", RegexOption.IGNORE_CASE)

    // "4,94 +999 corridas" e "4,94 365 corridas": ignora o + no número.
    private val regexNota = Regex(
        """([1-5][.,]\d{1,2})\D{0,12}?\+?\s*(\d+)\s*(?:corridas|viagens)\b""",
        RegexOption.IGNORE_CASE
    )
    // Nota isolada com rótulo/estrela, mesmo antes de o OCR reconhecer as viagens.
    private val regexNotaIsolada = Regex(
        """(?:⭐|★|\bnota\b\s*:?|\bavalia[cç][aã]o\b\s*:?)\s*([1-5][.,]\d{1,2})""",
        RegexOption.IGNORE_CASE
    )

    // Os exemplos seguem acompanhados da distância: "1h 15m (25 km)", "8 min (1,8 km)".
    // Preserva "2 min (599 m)" e a tolerância do OCR para "kn".
    private val regexTrecho = Regex(
        """(?<![\p{L}\d])((?:\d+\s*h(?:oras?)?\s*(?:\d+\s*(?:min(?:utos?)?|m))?|\d+\s*(?:min(?:utos?)?|m)))(?:\s*\(\s*(\d+(?:[.,]\d+)?)\s*(k[mn]|m)\s*\))?""",
        RegexOption.IGNORE_CASE
    )
    private val regexHoras = Regex(
        """(\d+)\s*h(?:oras?)?\s*(?:(\d+)\s*(?:min(?:utos?)?|m))?""",
        RegexOption.IGNORE_CASE
    )
    private val regexMinutos = Regex("""(\d+)\s*(?:min(?:utos?)?|m)""", RegexOption.IGNORE_CASE)

    private fun tempoEmMinutos(valor: String): Int? {
        val horas = regexHoras.matchEntire(valor)
        if (horas != null) {
            val h = horas.groupValues[1].toLongOrNull() ?: return null
            val m = horas.groupValues[2].ifEmpty { "0" }.toLongOrNull() ?: return null
            return (h * 60 + m).takeIf { it in 0..Int.MAX_VALUE.toLong() }?.toInt()
        }
        return regexMinutos.matchEntire(valor)?.groupValues?.get(1)?.toIntOrNull()
    }

    // Mantém exatamente o texto da verificação que o OCR conseguiu reconhecer.
    private val regexVerificacao = Regex(
        """CPF\s*(?:e|&|/)\s*Cart[aã]o\s+verif(?:icad[oa])?\.?|Perfil\s+Premium|CPF\s+verif(?:icad[oa])?\.?|Cart[aã]o\s+verif(?:icad[oa])?\.?""",
        RegexOption.IGNORE_CASE
    )

    // Somente o número dentro dos parênteses é distância.
    // O '15m' de '1h 15m (45 km)' NUNCA será tratado como 15 metros.
    private fun distanciaDoTrecho(numeroTexto: String, unidade: String): Double? {
        val valor = numeroTexto.replace(",", ".").toDoubleOrNull()?.takeIf { it.isFinite() && it > 0 }
            ?: return null
        val km = if (unidade.equals("m", ignoreCase = true)) valor / 1000.0 else valor
        return km.takeIf { it in 0.1..200.0 }
    }

    // "1 parada(s)"  (o leitor lê a bolinha do ícone como "O" ou "0")
    private val regexParadas = Regex("""(?<![\p{L}\d])[Oo]?(\d+)\s*parada""", RegexOption.IGNORE_CASE)

    private val regexRua = Regex(
        """(?<![\p{L}])(?:avenida|av\.?|rua|r\.|alameda|al\.?|travessa|tv\.?|estrada|estr\.?|rodovia|rod\.?|pra[cç]a|largo|viela|beco|via)(?=\s|$)""",
        RegexOption.IGNORE_CASE
    )

    /** Devolve a corrida entendida, ou null se na tela NÃO tem uma corrida. */
    fun ler(texto: String): Corrida? {
        val aceitar = regexAceitar.find(texto)
        val nota = regexNota.find(texto)
        // Não descartar tempo legível quando o OCR falhou apenas na distância:
        // outro frame pode fornecer os km faltantes.
        val trechos = regexTrecho.findAll(texto).toList()

        // Sem nenhuma pista de corrida (botão Aceitar, nota ou minutos/km) = não é corrida
        if (aceitar == null && nota == null && trechos.isEmpty()) return null

        // O valor da oferta vem do botao "Aceitar por" quando estiver legivel.
        // Sem esse botao, evite confundir valores extras e resultados do proprio app.
        val limitePreco = nota?.range?.first ?: texto.length
        val precoSolto = regexPrecoSolto.findAll(texto).firstOrNull { candidato ->
            val inicioLinha = texto.lastIndexOf('\n', candidato.range.first).let { it + 1 }
            val linha = texto.substring(inicioLinha).substringBefore('\n')
            val descricaoSecundaria = listOf(
                "tarifa", "dinâmica", "dinamica", "por dirigir",
                "garantido", "bônus", "bonus", "preço:",
                "preco:", "ganho", "total:", "negociação:"
            ).any { linha.contains(it, ignoreCase = true) }
            candidato.range.first < limitePreco && !descricaoSecundaria
        }
        val preco = (aceitar ?: precoSolto)
            ?.groupValues?.get(1)?.let { dinheiroParaNumero(it) }

        val limiteFinal = aceitar?.range?.first

        val enderecos = trechos.mapIndexed { i, m ->
            val fim = if (i + 1 < trechos.size) {
                trechos[i + 1].range.first
            } else {
                limiteFinal?.takeIf { it > m.range.last } ?: texto.length
            }
            acharEnderecos(texto.substring(m.range.last + 1, fim))
        }
        val associados = enderecos.map { it.firstOrNull() }.toMutableList()
        // O OCR às vezes lê os dois tempos antes dos dois endereços.
        // Nesses casos, respeita a ordem: primeiro busca, depois destino.
        if (enderecos.size == 2) {
            if (enderecos[0].isEmpty() && enderecos[1].size >= 2) {
                associados[0] = enderecos[1][0]
                associados[1] = enderecos[1][1]
            } else if (enderecos[0].size >= 2 && enderecos[1].isEmpty()) {
                associados[0] = enderecos[0][0]
                associados[1] = enderecos[0][1]
            } else if (enderecos[0].isEmpty() && enderecos[1].size == 1) {
                // Um endereço solto após ambos os tempos não identifica qual trecho é.
                associados[1] = null
            }
        }

        val montados = trechos.mapIndexedNotNull { i, m ->
            val minutos = tempoEmMinutos(m.groupValues[1])?.takeIf { it in 1..300 }
                ?: return@mapIndexedNotNull null
            Trecho(
                minutos = minutos,
                km = distanciaDoTrecho(m.groupValues[2], m.groupValues[3]),
                endereco = associados.getOrNull(i)
            )
        }
        val notaTexto = nota?.groupValues?.get(1)
            ?: regexNotaIsolada.find(texto)?.groupValues?.get(1)
        val verificacoes = regexVerificacao.findAll(texto)
            .map { it.value.replace(Regex("""\s+"""), " ").trim() }
            .distinct()
            .toList()

        return Corrida(
            preco = preco,
            notaPassageiro = notaTexto?.let { kmParaNumero(it) }?.takeIf { it in 1.0..5.0 },
            viagensPassageiro = nota?.groupValues?.get(2)?.toIntOrNull(),
            busca = montados.firstOrNull(),
            viagem = if (montados.size >= 2) montados.last() else null,
            paradas = regexParadas.find(texto)?.groupValues?.get(1)?.toIntOrNull(),
            verificacao = verificacoes.takeIf { it.isNotEmpty() }?.joinToString(" / ")
        )
    }

    private fun acharEnderecos(pedaco: String): List<String> =
        pedaco.lines()
            .map { it.trim().trimStart('-', '–', '—', '·', '•', ' ') }
            .mapNotNull { linha ->
                val inicio = regexRua.find(linha)?.range?.first ?: return@mapNotNull null
                val endereco = linha.substring(inicio).trimEnd(',', '.', ' ')
                // Não salvar "R", "r", "R." nem números isolados como endereços.
                endereco.takeIf { it.length >= 6 && it.count(Char::isLetter) >= 4 }
            }
            .distinct()

    private fun dinheiroParaNumero(s: String): Double? =
        s.replace(".", "").replace(",", ".").toDoubleOrNull()

    private fun kmParaNumero(s: String): Double? {
        val limpo = if (s.contains(',')) s.replace(".", "").replace(',', '.') else s
        return limpo.toDoubleOrNull()
    }
}
