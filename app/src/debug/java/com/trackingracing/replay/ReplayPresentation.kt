package com.trackingracing.replay

import com.trackingracing.Corrida
import com.trackingracing.Trecho
import java.text.NumberFormat
import java.util.Locale

/** Only typed metrics cross the UI boundary. Never pass addresses or raw OCR. */
internal object ReplayPresentation {
    private val br = Locale.forLanguageTag("pt-BR")

    fun offer(reading: Corrida?): String? {
        val price = reading?.preco?.takeIf { it.isFinite() && it > 0 } ?: return null
        val pickup = leg(reading.busca) ?: return null
        val trip = leg(reading.viagem) ?: return null
        return buildList {
            add("Valor  R\$ " + String.format(br, "%.2f", price))
            add("Busca  $pickup")
            add("Viagem  $trip")
            reading.notaPassageiro?.takeIf { it.isFinite() && it in 0.0..5.0 }
                ?.let { add("Nota  " + String.format(br, "%.2f", it)) }
            reading.viagensPassageiro?.takeIf { it >= 0 }?.let { add("Corridas  $it") }
        }.joinToString("\n")
    }

    private fun leg(value: Trecho?): String? {
        val km = value?.km?.takeIf { it.isFinite() && it > 0 } ?: return null
        if (value.minutos <= 0) return null
        val distance = NumberFormat.getNumberInstance(br).apply {
            isGroupingUsed = false
            maximumFractionDigits = 3
        }.format(km)
        return "${value.minutos} min · $distance km"
    }
}
