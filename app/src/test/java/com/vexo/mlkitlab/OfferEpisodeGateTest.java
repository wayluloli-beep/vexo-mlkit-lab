package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public final class OfferEpisodeGateTest {
    @Test public void sameOfferIn350FramesNotifiesOnceOnly() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        int notifications=0;
        for(int i=0;i<350;i++) if(g.observe("99-moto-40,70-11,8-24")) notifications++;
        assertEquals(1,notifications);
    }

    @Test public void mapSeparatesNewOfferEvenWithIdenticalAmounts() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("identical"));
        assertTrue(g.observe("identical"));
        g.nonOffer(); // uma leitura falha não cria episódio novo
        assertFalse(g.observe("identical"));
        g.nonOffer();
        g.nonOffer(); // duas telas sem oferta encerram card anterior
        assertFalse(g.observe("identical"));
        assertTrue("Pode ser nova oferta com os mesmos números",g.observe("identical"));
    }

    @Test public void differentFingerprintNeedsVisibleTransitionToAvoidOcrNoise() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("offerA"));
        assertTrue(g.observe("offerA"));
        assertFalse(g.observe("offerB"));
        assertFalse("B sem transição pode ser um erro do OCR",g.observe("offerB"));
        assertFalse(g.observe("offerA"));
        g.nonOffer();
        g.nonOffer(); // duas leituras de mapa comprovam mudança
        assertFalse(g.observe("offerB"));
        assertTrue(g.observe("offerB"));
    }

    @Test public void twoUncertainFramesDoNotCreateSecondAlert() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("offerA"));
        assertTrue(g.observe("offerA"));
        g.uncertain();
        g.uncertain();
        assertFalse(g.observe("offerA"));
        assertFalse(g.observe("offerA"));
    }

    @Test public void numericallyUnstableOcrDoesNotCreateThreeAlerts() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        int notifications=0;
        String[] frames={"A","A","B_ocr","B_ocr","A","A"};
        for(String frame:frames) if(g.observe(frame)) notifications++;
        assertEquals("uma oferta com leitura instável deve dar um alerta",1,notifications);
    }

    @Test public void uncertainBetweenTwoPreConfirmationFramesPreventsFalseAgreement() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("offerA"));
        g.uncertain();
        assertFalse(g.observe("offerA"));
        assertTrue(g.observe("offerA"));
    }

    @Test public void definiteMapThenSameFingerprintIsNewEpisode() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("offerA"));
        assertTrue(g.observe("offerA"));
        assertFalse(g.nonOffer());
        assertTrue(g.nonOffer());
        assertFalse(g.observe("offerA"));
        assertTrue(g.observe("offerA"));
    }

    @Test public void nonOfferBlocksAndResetDiscardsOldEpisode() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe(null));
        assertFalse(g.observe(""));
        assertFalse(g.observe("offerA"));
        assertTrue(g.observe("offerA"));
        g.reset();
        assertFalse(g.observe("offerA"));
        assertTrue(g.observe("offerA"));
    }

    @Test public void oneMissedOcrFrameDoesNotDuplicateAlert() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("offer"));
        assertTrue(g.observe("offer"));
        for(int i=0;i<30;i++) {
            g.nonOffer();
            assertFalse(g.observe("offer"));
            assertFalse(g.observe("offer"));
        }
    }
}
