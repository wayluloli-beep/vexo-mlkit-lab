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
        LiveCaptureState.candidate("VALOR-SENSIVEL XYZ Rua Privada 123");
        String json=LiveCaptureState.safeDiagnosticReport();
        JSONObject o=new JSONObject(json);
        assertEquals("vexo-live-capture-diagnostic-v1",o.getString("schema"));
        assertEquals(1,o.getLong("framesReceived"));
        assertEquals(1,o.getLong("ocrCompleted"));
        assertEquals(1,o.getLong("offersAlerted"));
        assertEquals("OFFER_ALERT_GENERATED",o.getString("diagnosticStage"));
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
