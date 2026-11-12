package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

/** Pure timing; no original screenshots, private ride data or Android hooks. */
public final class NoFrameOverlayWatchdogTest {
    @Test public void noFramesBeforeFirstImageIsNotAnOldRide() {
        NoFrameOverlayWatchdog g=new NoFrameOverlayWatchdog();
        assertFalse(g.shouldClear(5000,1200));
        assertEquals(-1,g.ageMs(5000));
    }
    @Test public void freshCaptureNeverClearsSummary() {
        NoFrameOverlayWatchdog g=new NoFrameOverlayWatchdog();
        g.onFrame(100);
        assertFalse(g.shouldClear(700,1200));
        assertFalse(g.shouldClear(1300,1200)); // equals threshold
    }
    @Test public void exactlyOnceAfterCaptureFreezes() {
        NoFrameOverlayWatchdog g=new NoFrameOverlayWatchdog();
        g.onFrame(100);
        assertTrue(g.shouldClear(1301,1200));
        assertFalse(g.shouldClear(1400,1200));
        assertFalse(g.shouldClear(1500,1200));
    }
    @Test public void newFrameAllowsNewStallDetection() {
        NoFrameOverlayWatchdog g=new NoFrameOverlayWatchdog();
        g.onFrame(100);
        assertTrue(g.shouldClear(1400,1200));
        g.onFrame(1600);
        assertFalse(g.shouldClear(1650,1200));
        assertTrue(g.shouldClear(2900,1200));
    }
    @Test public void outOfOrderFrameCannotCreateFalseTimeout() {
        NoFrameOverlayWatchdog g=new NoFrameOverlayWatchdog();
        g.onFrame(1000);
        g.onFrame(900);
        assertEquals(100,g.ageMs(1100));
        assertFalse(g.shouldClear(2000,1200));
    }
    @Test public void stopAndNewSessionForgetPreviousFrame() {
        NoFrameOverlayWatchdog g=new NoFrameOverlayWatchdog();
        g.onFrame(100);
        assertTrue(g.shouldClear(2000,1200));
        g.reset();
        assertFalse(g.shouldClear(3000,1200));
        g.onFrame(3200);
        assertFalse(g.shouldClear(3300,1200));
    }
}
