package com.trackingracing

import org.junit.Assert.*
import org.junit.Test

class VexoManualWebTest {
    @Test fun sameLocalOriginSupportsStartupAndDataPreservingNavigation() {
        assertEquals("aurora/index.html", VexoManualWeb.asset(VexoManualWeb.entry))
        assertEquals("aurora/assets/vexo-abertura.mp4", VexoManualWeb.asset("https://appassets.androidplatform.net/aurora/assets/vexo-abertura.mp4"))
        assertTrue(VexoManualWeb.handlesBack("https://appassets.androidplatform.net/aurora/central.html#config"))
        assertTrue(VexoManualWeb.handlesBack("https://appassets.androidplatform.net/aurora/onboarding.html"))
        assertFalse(VexoManualWeb.handlesBack("https://appassets.androidplatform.net/aurora/veiculo.html"))
    }

    @Test fun noExternalOriginLookalikeOrAssetPathEscape() {
        for (url in listOf(
            "http://appassets.androidplatform.net/aurora/index.html",
            "https://appassets.androidplatform.net.example/aurora/index.html",
            "https://appassets.androidplatform.net:443/aurora/index.html",
            "https://test@appassets.androidplatform.net/aurora/index.html",
            "https://appassets.androidplatform.net/aurora/../fixture",
            "https://appassets.androidplatform.net/aurora/%2e%2e/fixture",
            "https://appassets.androidplatform.net/aurora/assets//file",
            "https://appassets.androidplatform.net/overlay.html"
        )) assertNull(url, VexoManualWeb.asset(url))
    }

    @Test fun activeGoalUsesWholePositiveCents() {
        assertEquals(2500, VexoManualWeb.hourlyGoal(2500.0))
        for (invalid in listOf(0.0, -1.0, 100.5, 1_000_000_001.0, Double.NaN, Double.POSITIVE_INFINITY)) {
            assertNull(VexoManualWeb.hourlyGoal(invalid))
        }
    }

    @Test fun persistedFuelRejectsInvalidValues() {
        assertTrue(VexoManualWeb.validFuel(13.25, 5.89))
        assertFalse(VexoManualWeb.validFuel(Double.NaN, 5.89))
        assertFalse(VexoManualWeb.validFuel(10.0, Double.POSITIVE_INFINITY))
        assertFalse(VexoManualWeb.validFuel(0.0, 0.1))
    }

    @Test fun openingVideoReturnsBoundedByteRanges() {
        assertEquals(VexoManualWeb.MediaRange(0, 99, false), VexoManualWeb.mediaRange(100, null))
        assertEquals(VexoManualWeb.MediaRange(17, 99, true), VexoManualWeb.mediaRange(100, "bytes=17-"))
        assertEquals(40L, VexoManualWeb.mediaRange(100, "bytes=0-39")?.length)
        assertEquals(93L, VexoManualWeb.mediaRange(100, "bytes=7-400")?.length)
        for (invalid in listOf("bytes=100-", "bytes=10-0", "bytes=0-1,2-3", "bytes=0-9999999999999999999999")) {
            assertNull(VexoManualWeb.mediaRange(100, invalid))
        }
    }
}
