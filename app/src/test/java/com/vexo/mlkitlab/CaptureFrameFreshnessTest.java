package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public class CaptureFrameFreshnessTest {
    @Test public void expiresLateRecognitionInsteadOfAlertingOldOffer() {
        assertTrue(CaptureFrameFreshness.isFresh(1000,2000,3000));
        assertTrue(CaptureFrameFreshness.isFresh(1000,4000,3000));
        assertFalse(CaptureFrameFreshness.isFresh(1000,4001,3000));
        assertFalse(CaptureFrameFreshness.isFresh(1000,5000,3000));
        assertFalse(CaptureFrameFreshness.isFresh(3000,2000,3000));
    }
}
