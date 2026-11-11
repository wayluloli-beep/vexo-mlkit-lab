package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.json.JSONObject;
import org.junit.Test;

public final class LiveCaptureDiagnosticPrivacyTest {
    @Test public void reportCanBeSharedWithoutLeakingRecognizedTextOrLocation() throws Exception {
        LiveCaptureState.begin();
        LiveCaptureState.frameReceived();
        LiveCaptureState.ocrAttempted();
        LiveCaptureState.ocrCompleted();
        String sensitive="99 Negocia R$12,64 8 min (2,1 km) 17 min (7,3 km) Aceitar Rua Privada 123";
        LiveCaptureState.recordContextEvidence(
            ScreenContextClassifier.diagnosticEvidenceMask(sensitive));
        LiveCaptureState.candidate("VALOR-SENSIVEL XYZ Rua Privada 123");
        String json=LiveCaptureState.safeDiagnosticReport();
        JSONObject o=new JSONObject(json);
        assertEquals("vexo-live-capture-diagnostic-v3",o.getString("schema"));
        assertEquals(1,o.getLong("framesReceived"));
        assertEquals(1,o.getLong("ocrCompleted"));
        assertEquals(1,o.getLong("offersAlerted"));
        assertEquals("OFFER_ALERT_GENERATED",o.getString("diagnosticStage"));
        assertEquals(1,o.getJSONObject("contextEvidenceCounts").getLong("readsWithTwoDistances"));
        assertEquals(1,o.getJSONObject("contextEvidenceCounts").getLong("readsWithPriceMarker"));
        assertEquals(0,o.getLong("offerGateHeldFrames"));
        assertEquals(0,o.getLong("candidatesWithout99Logo"));
        assertFalse(json.contains("12,64"));
        assertFalse(json.contains("2,1"));
        assertFalse(json.contains("7,3"));
        assertFalse(json.contains("Rua Privada"));
        assertFalse(json.contains("VALOR-SENSIVEL"));
        assertFalse(json.contains("XYZ"));
        assertFalse(o.getBoolean("containsScreenshotOrOcrText"));
        LiveCaptureState.end("fim");
    }

    @Test public void noFramesDoesNotPretendCaptureSuccess() throws Exception {
        LiveCaptureState.begin();
        JSONObject o=new JSONObject(LiveCaptureState.safeDiagnosticReport());
        assertEquals("WAITING_FOR_FRAMES",o.getString("diagnosticStage"));
        assertTrue(o.getBoolean("noFieldAccuracyMeasured"));
        LiveCaptureState.end("fim");
    }
}
