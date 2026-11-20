package com.trackingracing.replay

import com.trackingracing.Corrida
import com.trackingracing.Trecho
import org.junit.Assert.*
import org.junit.Test

class ReplayTest {
    @Test fun firstTapOwnsTheOnlyInFlightTurn() {
        val gate = ReplayGate()
        assertNull(gate.begin())
        gate.show()
        val run = requireNotNull(gate.begin())
        assertNull(gate.begin())
        assertTrue(gate.finish(run))
        assertFalse(gate.finish(run))
        assertNotNull(gate.begin())
    }

    @Test fun reopeningCannotReviveResultFromAHiddenScreen() {
        val gate = ReplayGate()
        gate.show()
        val old = requireNotNull(gate.begin())
        gate.hide()
        assertFalse(gate.canBegin)
        gate.show()
        assertFalse(gate.canBegin)
        assertFalse(gate.finish(old))
        val current = requireNotNull(gate.begin())
        assertFalse(gate.finish(old))
        assertFalse(gate.canBegin)
        assertTrue(gate.finish(current))
    }

    @Test fun parsedValuesAreFormattedWithoutCategoryOrAddress() {
        val parsed = Corrida(
            preco = 36.70, notaPassageiro = 4.98, viagensPassageiro = 243,
            busca = Trecho(6, 1.5, "ADDRESS_MARKER_1"),
            viagem = Trecho(33, 22.5, "ADDRESS_MARKER_2"),
            paradas = null, verificacao = null,
        )
        assertEquals(
            "Valor  R\$ 36,70\nBusca  6 min · 1,5 km\nViagem  33 min · 22,5 km\nNota  4,98\nCorridas  243",
            ReplayPresentation.offer(parsed),
        )
    }

    @Test fun omittedFieldsStayAbsentAndMetersDoNotRoundAway() {
        val parsed = Corrida(
            preco = 19.29, notaPassageiro = null, viagensPassageiro = null,
            busca = Trecho(4, 0.907, null), viagem = Trecho(18, 11.4, null),
            paradas = null, verificacao = null,
        )
        assertEquals(
            "Valor  R\$ 19,29\nBusca  4 min · 0,907 km\nViagem  18 min · 11,4 km",
            ReplayPresentation.offer(parsed),
        )
    }

    @Test fun rejectedOrIncompleteOfferDoesNotAcquireDefaultMetrics() {
        val incomplete = Corrida(
            preco = 36.70, notaPassageiro = null, viagensPassageiro = null,
            busca = Trecho(6, null, null), viagem = Trecho(33, 22.5, null),
            paradas = null, verificacao = null,
        )
        assertNull(ReplayPresentation.offer(null))
        assertNull(ReplayPresentation.offer(incomplete))
        assertNull(ReplayPresentation.offer(incomplete.copy(busca = Trecho(6, Double.NaN, null))))
    }
}
