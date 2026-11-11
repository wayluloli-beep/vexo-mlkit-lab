package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public class VexoOverlaySummaryTest {
    @Test public void displaysOnlyThreeNumericOfferFields() {
        assertEquals("R$ 12,64  •  7,3 km / 17 min\nConfira antes de decidir",
            VexoOverlaySummary.format("12,64","7,3","17"));
    }
    @Test public void whiteGreenCardCalculatesFullRouteNotJustTrip() {
        VexoOverlaySummary.Metrics m=VexoOverlaySummary.fromFields(
            "12,64","2,1","7,3","8","17","4,96");
        assertTrue(m.valid);
        assertEquals("1,34",m.perKm);
        assertEquals("30,34",m.perHour);
        assertEquals("4,96",m.rating);
        assertEquals("25m",m.totalTime);
        assertEquals("9.4km",m.totalKm);
        assertEquals("—",m.profit); // sem custos cadastrados não há lucro.
    }

    @Test public void longJourneyFormatsHoursAndMissingRatingIsNotInvented() {
        VexoOverlaySummary.Metrics m=VexoOverlaySummary.fromFields(
            "228,00","1,0","67,9","12","80","");
        assertTrue(m.valid);
        assertEquals("1h32m",m.totalTime);
        assertEquals("68.9km",m.totalKm);
        assertEquals("—",m.rating);
    }

    @Test public void invalidOrPersonalDataNeverReachesCard() {
        assertFalse(VexoOverlaySummary.fromFields("R$12,64 Rua Privada",
            "2,1","7,3","8","17","5,00").valid);
        assertFalse(VexoOverlaySummary.fromFields("12,64",
            "2,1 km / Passageiro","7,3","8","17","5,00").valid);
        assertFalse(VexoOverlaySummary.fromFields("12,64",
            "0","0","0","0","5,00").valid);
    }

    @Test public void rejectsRawOcrNamesAddressesAndInvalidFields() {
        String x=VexoOverlaySummary.format("12,64 Rua 123","7,3","17");
        assertEquals("Confira a oferta no aplicativo",x);
        assertFalse(x.contains("Rua"));
        assertEquals("Confira a oferta no aplicativo",
            VexoOverlaySummary.format("12,64",null,"17"));
    }
}
