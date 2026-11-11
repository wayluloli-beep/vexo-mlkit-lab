package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

/** Casos inteiramente fictícios. Não guarda texto OCR na telemetria. */
public class CaptureContextEvidenceTest {
    @Test public void fullOfferHasAllEvidenceBits() {
        String full="99 Negocia R$12,64 8 min (2,1 km) 17 min (7,3 km) Aceitar";
        int flags=ScreenContextClassifier.diagnosticEvidenceMask(full);
        assertEquals(127,flags);
        assertEquals(ScreenContextClassifier.Kind.OFFER_CANDIDATE,
            ScreenContextClassifier.classify(full));
    }

    @Test public void partialOfferWithoutButtonIsNotPromotedToAlert() {
        String partial="99 Negocia R$12,64 8 min (2,1 km) 17 min (7,3 km)";
        int flags=ScreenContextClassifier.diagnosticEvidenceMask(partial);
        assertEquals(125,flags);
        assertEquals(ScreenContextClassifier.Kind.UNCERTAIN,
            ScreenContextClassifier.classify(partial));
    }

    @Test public void adWithPriceHasNoOfferContext() {
        String banner="Promocao no mercado: R$0,99. Aproveite!";
        int flags=ScreenContextClassifier.diagnosticEvidenceMask(banner);
        assertTrue((flags&ScreenContextClassifier.EVIDENCE_PRICE)!=0);
        assertFalse((flags&ScreenContextClassifier.EVIDENCE_PARTIAL_OFFER)!=0);
        assertFalse((flags&ScreenContextClassifier.EVIDENCE_TWO_DISTANCES)!=0);
    }

    @Test public void counterOverlapDoesNotEqualClassificationAndResetWorks() {
        CaptureContextEvidence evidence=new CaptureContextEvidence();
        evidence.record(ScreenContextClassifier.diagnosticEvidenceMask(
            "99 Negocia R$12,64 8 min (2,1 km) 17 min (7,3 km)"));
        evidence.record(ScreenContextClassifier.diagnosticEvidenceMask(
            "Promocao R$0,99"));
        long[] snapshot=evidence.snapshot();
        assertArrayEquals(new long[]{2,2,0,1,1,1,1,1},snapshot);
        evidence.reset();
        assertArrayEquals(new long[8],evidence.snapshot());
    }
}
