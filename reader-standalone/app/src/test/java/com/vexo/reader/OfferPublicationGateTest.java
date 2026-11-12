package com.vexo.reader;

import org.junit.Test;

import static com.vexo.reader.OfferPublicationGate.Decision.*;
import static org.junit.Assert.*;

public final class OfferPublicationGateTest {
    @Test public void sameOfferAcrossFiveVisualChangesIsSavedOnce() {
        OfferPublicationGate gate = new OfferPublicationGate();
        int records = 0;
        for (int epoch = 1; epoch <= 5; epoch++) {
            assertEquals(CONFIRMING, gate.observe("A", epoch, false));
            if (gate.observe("A", epoch, false) == SAVE) {
                records++;
                gate.saved("A");
            }
        }
        assertEquals(1, records);
    }

    @Test public void confirmationCannotCombineReadingsFromDifferentFramesGenerations() {
        OfferPublicationGate gate = new OfferPublicationGate();
        assertEquals(CONFIRMING, gate.observe("A", 1, false));
        assertEquals(CONFIRMING, gate.observe("A", 2, false));
        assertEquals(SAVE, gate.observe("A", 2, false));
    }

    @Test public void differentConfirmedOfferCanBeSavedAtTheSamePosition() {
        OfferPublicationGate gate = recordedA();
        assertEquals(CONFIRMING, gate.observe("B", 1, false));
        assertEquals(SAVE, gate.observe("B", 1, false));
        gate.saved("B");
        assertEquals(ALREADY_RECORDED, gate.observe("B", 1, false));
    }

    @Test public void partialReadingsAndAnIsolatedSearchMessageDoNotReopenRecording() {
        OfferPublicationGate gate = recordedA();
        assertEquals(INCOMPLETE, gate.observe(null, 2, true));
        assertEquals(INCOMPLETE, gate.observe(null, 2, false));
        assertEquals(INCOMPLETE, gate.observe(null, 2, true));
        assertEquals(CONFIRMING, gate.observe("A", 3, false));
        assertEquals(ALREADY_RECORDED, gate.observe("A", 3, false));
    }

    @Test public void repeatedClearSearchAllowsAnIdenticalNewOfferToBeSaved() {
        OfferPublicationGate gate = recordedA();
        assertEquals(INCOMPLETE, gate.observe(null, 2, true));
        assertEquals(INCOMPLETE, gate.observe(null, 2, true));
        assertEquals(CONFIRMING, gate.observe("A", 3, false));
        assertEquals(SAVE, gate.observe("A", 3, false));
    }

    @Test public void failedInsertIsNotCountedAsSaved() {
        OfferPublicationGate gate = new OfferPublicationGate();
        assertEquals(CONFIRMING, gate.observe("A", 1, false));
        assertEquals(SAVE, gate.observe("A", 1, false));
        assertEquals(SAVE, gate.observe("A", 1, false));
        gate.saved("A");
        assertEquals(ALREADY_RECORDED, gate.observe("A", 1, false));
    }

    @Test public void newSessionStartsWithNoRecordedOffer() {
        OfferPublicationGate gate = recordedA();
        gate.reset();
        assertEquals(CONFIRMING, gate.observe("A", 1, false));
        assertEquals(SAVE, gate.observe("A", 1, false));
    }

    @Test public void partialOfferCannotBeMistakenForClearSearch() {
        assertTrue(OfferParser.clearlyNoOffer("Procurando corridas"));
        assertFalse(OfferParser.clearlyNoOffer(""));
        assertFalse(OfferParser.clearlyNoOffer("Procurando corridas\nAceitar"));
        assertFalse(OfferParser.clearlyNoOffer("Procurando corridas\nR$"));
        assertFalse(OfferParser.clearlyNoOffer("Procurando corridas\n6 min"));
    }

    private static OfferPublicationGate recordedA() {
        OfferPublicationGate gate = new OfferPublicationGate();
        assertEquals(CONFIRMING, gate.observe("A", 1, false));
        assertEquals(SAVE, gate.observe("A", 1, false));
        gate.saved("A");
        return gate;
    }
}
