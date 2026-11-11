package com.vexo.mlkitlab;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public final class CaptureHealthAnalyzerTest {
    @Test public void distinguishesEveryRelevantStage() {
        assertEquals("WAITING_FOR_FRAMES",CaptureHealthAnalyzer.stage(0,0,0,0,0,true));
        assertEquals("NO_FRAMES_RECORDED",CaptureHealthAnalyzer.stage(0,0,0,0,0,false));
        assertEquals("FRAMES_WITHOUT_OCR_START",CaptureHealthAnalyzer.stage(5,0,0,0,0,true));
        assertEquals("OCR_FAILED",CaptureHealthAnalyzer.stage(8,3,0,3,0,false));
        assertEquals("OCR_NOT_COMPLETED",CaptureHealthAnalyzer.stage(8,3,0,0,0,true));
        assertEquals("OCR_OK_NO_CONFIRMED_OFFER",CaptureHealthAnalyzer.stage(8,3,2,0,0,true));
        assertEquals("OFFER_ALERT_GENERATED",CaptureHealthAnalyzer.stage(8,3,2,0,1,true));
    }

    @Test public void anAlertDoesNotClaimAccuracy() {
        assertEquals("O aplicativo gerou ao menos um aviso. Isto nao comprova acerto dos numeros.",
            CaptureHealthAnalyzer.explanation("OFFER_ALERT_GENERATED"));
    }
}
