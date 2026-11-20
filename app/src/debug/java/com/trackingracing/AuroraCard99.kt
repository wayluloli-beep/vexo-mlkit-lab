package com.trackingracing

internal object AuroraCard99 {
    private val cardLegado = Regex("""(?i)\b(?:99\s*(?:pop|negocia)|aceitar\s+por|at[eé]\s+o\s+passageiro)\b""")
    private val foraDeOferta = Regex("""(?i)\b(?:corrida\s+(?:conclu[íi]da|cancelada|em\s+andamento)|comprovante\s+da\s+viagem)\b""")
    private val historico = Regex("""(?im)^\s*hist[oó]rico\s+de\s+ganhos\s*$""")
    private val seloPrioritario = Regex("""(?i)\bpriorit[aá]rio\b""")
    private val pagamentoNoApp = Regex("""(?i)\b(?:pgto\.?|pagamento)\s*no\s+app\b""")
    private val tarifaPrincipal = Regex("""(?im)^[ \t]*R\s*[\u0024S]\s*(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}(?:[ \t]*[^\p{L}\d/\r\n]*\d+(?:[.,]\d+)?[ \t]*[x×])?[ \t]*\r?$""")

    private val valorComum = Regex("""^[ \t]*R\s*(?:S?\$|S)\s*(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})[ \t]*$""", RegexOption.IGNORE_CASE)
    private val tarifaPorKm = Regex("""(?i)^\s*R\s*(?:S?\$|S)\s*\d+[,.]\d{2}\s*/\s*km\s*$""")
    private val passageiro = Regex("""(?i)(?<!\d)[1-5][,.]\d{1,2}[^\d\r\n]{0,12}\d+\s*(?:corridas|viagens)\b""")
    private val trecho = Regex("""(?i)(?<![\p{L}\d])(?:\d+\s*h(?:\s*\d+\s*(?:min|m))?|\d+\s*min)\s*\(\s*\d+(?:[,.]\d+)?\s*(?:km|m)\s*\)""")

    private fun bloqueado(bruto:String) =
        foraDeOferta.containsMatchIn(bruto) || historico.containsMatchIn(bruto)

    fun precoComumSemRotulo(bruto:String):Double? {
        if (bloqueado(bruto) || cardLegado.containsMatchIn(bruto) ||
            seloPrioritario.containsMatchIn(bruto) || !pagamentoNoApp.containsMatchIn(bruto)) return null
        val linhas=bruto.lines()
        val pagamentos=linhas.indices.filter { pagamentoNoApp.containsMatchIn(linhas[it]) }
        val precos=linhas.mapIndexedNotNull { i, linha ->
            valorComum.matchEntire(linha)?.let { i to it.groupValues[1] }
        }.filter { (i,_) -> pagamentos.any { it < i } }
        val (i, valor) = precos.singleOrNull() ?: return null
        val depois=linhas.drop(i+1)
        val taxa=depois.indexOfFirst(tarifaPorKm::matches)
        val nota=depois.indexOfFirst(passageiro::containsMatchIn)
        if(taxa<0 || nota<=taxa || depois.drop(nota+1).count(trecho::containsMatchIn)!=2)return null
        return valor.replace(".","").replace(",",".").toDoubleOrNull()?.takeIf { it.isFinite() && it>0 }
    }

    fun aceitaTexto(bruto: String, precoComum:Double?=precoComumSemRotulo(bruto)): Boolean {
        if (bloqueado(bruto)) return false
        if (cardLegado.containsMatchIn(bruto)) return true
        // O botão pode estar fora do quadro. O selo sozinho não é uma oferta.
        // A leitura espacial ainda precisa confirmar preço e os dois pares tempo/distância.
        return precoComum != null || (seloPrioritario.containsMatchIn(bruto) &&
            pagamentoNoApp.containsMatchIn(bruto) &&
            tarifaPrincipal.containsMatchIn(bruto))
    }
}
