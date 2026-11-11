package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public final class OfferEpisodeGateTest {
    @Test public void uncertainHidesButRestoresSummaryWithoutReAlert() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("A"));
        assertTrue(g.observe("A"));
        g.uncertain();
        assertFalse(g.observe("A"));
        assertFalse(g.consumeRestoredSummary());
        assertFalse(g.observe("A"));
        assertTrue("Resumo da oferta confirmada pode voltar",g.consumeRestoredSummary());
        assertFalse(g.consumeRestoredSummary());
        assertFalse("Mesmo card não gera segundo alerta",g.observe("A"));
    }

    @Test public void wrongNumbersCannotRestoreHiddenOriginal() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observe("A"));
        assertTrue(g.observe("A"));
        g.uncertain();
        assertFalse(g.observe("B_ocr"));
        assertFalse(g.observe("B_ocr"));
        assertFalse(g.consumeRestoredSummary());
        assertFalse(g.observe("A"));
        assertFalse(g.consumeRestoredSummary());
        assertFalse(g.observe("A"));
        assertTrue(g.consumeRestoredSummary());
    }

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

    @Test public void onePartialOcrBetweenTwoCompleteReadsStillConfirms() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observeAt("offerA",1000));
        g.uncertain();
        assertTrue("Duas leituras completas e iguais em poucos segundos",
            g.observeAt("offerA",2400));
    }

    @Test public void twoPartialReadsBreakConfirmation() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observeAt("offerA",1000));
        g.uncertain();
        g.uncertain();
        assertFalse(g.observeAt("offerA",2300));
        assertTrue(g.observeAt("offerA",3400));
    }

    @Test public void distantReadsAndMapNeverCreateFakeConfirmation() {
        OfferEpisodeGate g=new OfferEpisodeGate();
        assertFalse(g.observeAt("offerA",1000));
        g.uncertain();
        assertFalse("Passou da janela máxima",
            g.observeAt("offerA",7000));
        assertTrue(g.observeAt("offerA",8100));

        g.reset();
        assertFalse(g.observeAt("offerA",1000));
        g.nonOffer();
        assertFalse("Mapa quebra confirmação",g.observeAt("offerA",2500));
        assertTrue(g.observeAt("offerA",3500));
    }

    @Test public void distinctOfferNeedsThreeStableReadsWhenMapWasUnclear() {
        OfferEpisodeGate gate=new OfferEpisodeGate();
        assertFalse(gate.observeAt("A",1000));
        assertTrue(gate.observeAt("A",2000));
        assertTrue(gate.hasActiveAlert());
        assertFalse(gate.observeAt("B",11000));
        assertFalse(gate.observeAt("B",12000));
        assertTrue("Três B estáveis depois de 7,5s permitem novo aviso",
            gate.observeAt("B",13000));
        assertFalse(gate.observeAt("B",14000)); // sem duplicar B
    }

    @Test public void shortGapAndOcrGlitchDoNotRearmOffer() {
        OfferEpisodeGate gate=new OfferEpisodeGate();
        assertFalse(gate.observeAt("A",1000));
        assertTrue(gate.observeAt("A",2000));
        assertFalse(gate.observeAt("B",3000));
        assertFalse(gate.observeAt("B",4000));
        assertFalse(gate.observeAt("B",5000));
        assertFalse(gate.observeAt("A",6000));
        assertFalse(gate.observeAt("B",11000));
        gate.uncertain();
        assertFalse(gate.observeAt("B",12000));
        assertFalse(gate.observeAt("B",13000));
        assertTrue(gate.observeAt("B",14000));
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
