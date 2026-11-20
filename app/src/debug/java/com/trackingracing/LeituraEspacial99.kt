package com.trackingracing

import android.graphics.Rect
import com.google.mlkit.vision.text.Text
import kotlin.math.abs
import kotlin.math.max

/**
 * Complemento ESPACIAL para tempo/km: usa as coordenadas de cada linha
 * reconhecida na MESMA inferencia ML Kit (sem nova captura ou OCR).
 *
 * O parser antigo continua responsavel por preco, nota, viagens,
 * verificacao e enderecos. Se nao houver dois pares inequivocos,
 * devolve a leitura antiga sem modificar nenhum campo.
 */
object LeituraEspacial99 {
    private data class Linha(val texto: String, val caixa: Rect, val indice: Int) {
        val centroY: Int get() = caixa.centerY()
    }
    private data class Par(val minutos: Int, val km: Double, val y: Int)

    private val preco = Regex("""R\s*[${'$'}S]\s*\d""", RegexOption.IGNORE_CASE)
    private val tempo = Regex(
        """(?<![\p{L}\d])(\d+\s*h(?:oras?)?\s*(?:\d+\s*(?:min(?:utos?)?|m))?|\d+\s*min(?:utos?)?)(?![\p{L}\d])""",
        RegexOption.IGNORE_CASE
    )
    private val distancia = Regex(
        """(?<![\p{L}\d/])(\d+(?:[.,]\d+)?)\s*(k[mn]|m)(?![\p{L}\d])""",
        RegexOption.IGNORE_CASE
    )
    private val horas = Regex(
        """(\d+)\s*h(?:oras?)?\s*(?:(\d+)\s*(?:min(?:utos?)?|m))?""",
        RegexOption.IGNORE_CASE
    )
    private val minutos = Regex("""(\d+)\s*(?:min(?:utos?)?|m)""", RegexOption.IGNORE_CASE)
    private val dadosDoProprioApp = Regex(
        """\b(?:ganho|pre[cç]o|tarifa|total|[uú]ltima)\b|(?:busca|viagem)\s*:""",
        RegexOption.IGNORE_CASE
    )

    private fun tempoValido(s: String): Int? {
        val h = horas.matchEntire(s)
        val t = if (h != null) {
            val hh = h.groupValues[1].toIntOrNull() ?: return null
            val mm = h.groupValues[2].ifBlank { "0" }.toIntOrNull() ?: return null
            hh * 60 + mm
        } else {
            minutos.matchEntire(s)?.groupValues?.get(1)?.toIntOrNull() ?: return null
        }
        return t.takeIf { it in 1..300 }
    }

    private fun kmValido(numero: String, unidade: String): Double? {
        val v = numero.replace(',', '.').toDoubleOrNull() ?: return null
        val km = if (unidade.equals("m", true)) v / 1000.0 else v
        return km.takeIf { it.isFinite() && it in 0.1..200.0 }
    }

    private fun distanciaNaLinha(linha: Linha, depoisDe: Int): Double? =
        distancia.findAll(linha.texto).firstOrNull { it.range.first >= depoisDe }?.let {
            kmValido(it.groupValues[1], it.groupValues[2])
        }

    /** Retorna somente pares tempo/distancia presentes e geometricamente proximos. */
    private fun paresDasLinhas(linhas: List<Linha>): List<Par> {
        val usados = mutableSetOf<Int>()
        val pares = mutableListOf<Par>()
        for (linha in linhas) {
            if (dadosDoProprioApp.containsMatchIn(linha.texto)) continue
            val encontrados = tempo.findAll(linha.texto).toList()
            for (t in encontrados) {
                val min = tempoValido(t.value) ?: continue
                var km = distanciaNaLinha(linha, t.range.last + 1)
                if (km == null) {
                    // ML Kit pode separar "4 min" e "(1,5 km)" em duas linhas.
                    // So une quando as caixas estao muito proximas na tela.
                    val vizinha = linhas.asSequence()
                        .filter { it.indice != linha.indice && it.indice !in usados }
                        .filter { !dadosDoProprioApp.containsMatchIn(it.texto) }
                        .filter { !tempo.containsMatchIn(it.texto) }
                        .filter { distancia.containsMatchIn(it.texto) }
                        .filter {
                            val dy = abs(it.centroY - linha.centroY)
                            val limiteY = max(linha.caixa.height(), it.caixa.height()) * 2
                            val dx = abs(it.caixa.centerX() - linha.caixa.centerX())
                            dy <= limiteY && dx <= max(200, linha.caixa.width() * 4)
                        }
                        .minByOrNull {
                            abs(it.centroY - linha.centroY) +
                                abs(it.caixa.centerX() - linha.caixa.centerX()) / 6
                        }
                    if (vizinha != null) {
                        km = distanciaNaLinha(vizinha, 0)
                        if (km != null) usados.add(vizinha.indice)
                    }
                }
                if (km != null) pares.add(Par(min, km, linha.centroY))
            }
        }
        return pares.sortedBy { it.y }
    }

    fun ler(resultado: Text): Corrida? {
        // Mantem fielmente o resultado original quando a geometria e insuficiente.
        val original = LeitorDeCorrida.ler(resultado.text.trim()) ?: return null
        val linhas = resultado.textBlocks.flatMap { bloco -> bloco.lines }
            .mapIndexedNotNull { indice, linha ->
                val r = linha.boundingBox ?: return@mapIndexedNotNull null
                linha.text.trim().takeIf { it.isNotEmpty() }?.let { Linha(it, r, indice) }
            }
            .sortedWith(compareBy<Linha> { it.caixa.top }.thenBy { it.caixa.left })
        if (linhas.size < 2) return original

        // A maior linha com R$ costuma ser o preco principal do card.
        // Exclui tempos no mapa e na miniatura flutuante acima do preco.
        val precoPrincipal = linhas.filter { preco.containsMatchIn(it.texto) }
            .maxByOrNull { it.caixa.height() }
        val candidatas = if (precoPrincipal != null) {
            linhas.filter { it.caixa.top >= precoPrincipal.caixa.bottom }
        } else linhas
        val pares = paresDasLinhas(candidatas)
        if (pares.size < 2) return original

        // Os dois ultimos pares, na ordem vertical, sao busca e viagem.
        // Nao mistura linhas com a mesma altura (duas colunas lado a lado).
        val (busca, viagem) = pares.takeLast(2)
        if (viagem.y - busca.y < 10) return original

        return original.copy(
            busca = Trecho(busca.minutos, busca.km, original.busca?.endereco),
            viagem = Trecho(viagem.minutos, viagem.km, original.viagem?.endereco)
        )
    }
}
