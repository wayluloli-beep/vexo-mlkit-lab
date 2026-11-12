package com.vexo.reader;

import org.junit.Test;
import static org.junit.Assert.*;

public final class OfferParserTest {
    private static final String CARD =
        "Moto Negocia\nR$ 72,32\n⚡ 3,2x\nR$ 118,61/hora\n" +
        "⭐ 4,73 • 114 corridas\n" +
        "5 min (1,5 km)\nRua Bento Hinoto, 48, Nossa Sra. de Fátima\n" +
        "32 min (20,2 km)\nRua Augusto Pereira dos Reis, 417, Torreões\n" +
        "Aceitar por R$ 72,32";

    @Test public void readsScreenshotWithoutBorrowingHourlyRate() {
        OfferRecord r = OfferParser.parse(CARD, 123L);
        assertEquals(7232, r.priceCents);
        assertEquals(5, r.originMin);
        assertEquals(15, r.originTenthsKm);
        assertEquals(32, r.destinationMin);
        assertEquals(202, r.destinationTenthsKm);
        assertEquals("4,73", r.rating);
        assertTrue(r.origin.startsWith("Rua Bento"));
        assertTrue(r.destination.startsWith("Rua Augusto"));
        assertTrue(r.hasMinimumFields());
    }

    @Test public void refusesIncompleteCard() {
        OfferRecord r = OfferParser.parse("R$ 72,32\n5 min (1,5 km)", 999L);
        assertFalse(r.hasMinimumFields());
    }

    @Test public void hourlyPriceIsNotOffer() {
        OfferRecord r = OfferParser.parse("R$ 118,61/hora\n5 min (1,5 km)\nRua A\n32 min (20,2 km)\nRua B", 1L);
        assertEquals(0, r.priceCents);
        assertFalse(r.hasMinimumFields());
    }

    @Test public void rejectsUnrealisticValues() {
        OfferRecord r = OfferParser.parse("R$ 4,99\n999 min (2000 km)\nRua A\n32 min (20,2 km)\nRua B", 1L);
        assertFalse(r.hasMinimumFields());
    }

    @Test public void fingerprintChangesIfDestinationChanges() {
        OfferRecord a = OfferParser.parse(CARD, 1L);
        OfferRecord b = OfferParser.parse(CARD.replace("Torreões", "Centro"), 2L);
        assertNotEquals(a.fingerprint(), b.fingerprint());
    }

    @Test public void moneyUsesBrazilianComma() {
        assertEquals(7232, OfferParser.parseMoney("72,32"));
        assertEquals(107220, OfferParser.parseMoney("1.072,20"));
        assertEquals(202, OfferParser.parseKmTenths("20,2"));
    }
}
