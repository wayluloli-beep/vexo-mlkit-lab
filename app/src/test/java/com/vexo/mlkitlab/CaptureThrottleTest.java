package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public final class CaptureThrottleTest {
    @Test public void dropsIntermediateFramesAndNeverRunsConcurrent() {
        CaptureThrottle g=new CaptureThrottle(1400);
        assertTrue(g.begin(10000));
        assertFalse("Frame in flight must prevent concurrent OCR",g.begin(12000));
        g.finish();
        assertFalse("Timeout between reads must be respected",g.begin(11000));
        assertTrue(g.begin(11401));
        g.finish();
    }

    @Test public void startsCleanOnNewSession() {
        CaptureThrottle old=new CaptureThrottle(1400);
        assertTrue(old.begin(1000));
        CaptureThrottle next=new CaptureThrottle(1400);
        assertTrue(next.begin(1005));
        old.finish(); // finishing old session must not release new gate
        assertFalse(next.begin(1007));
        next.finish();
        next.reset();
        assertTrue(next.begin(1008));
    }

    @Test(expected=IllegalArgumentException.class)
    public void refusesDangerouslyFastFrameLoop() {
        new CaptureThrottle(100);
    }
}
