package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

/** Synthetic grayscale rectangles; never reads a real ride screenshot. */
public final class FastRoiActivityProbeTest {
    private static final class Pixels implements FastCardVisualTracker.Pixels {
        final int patch;
        Pixels(int patch){this.patch=patch;}
        @Override public int width(){return 200;}
        @Override public int height(){return 160;}
        @Override public int luminance(int x,int y){
            if(x>=50 && x<150 && y>=30 && y<125) return patch;
            return 120;
        }
    }

    private static FastRoiActivityProbe start() {
        FastRoiActivityProbe p=new FastRoiActivityProbe();
        assertTrue(p.armOnVerifiedNonOffer(new Pixels(120),
            new FastCardVisualTracker.Box(50,30,100,95)));
        return p;
    }

    @Test public void detectsVisualChangeOnFirstFrameBeforeOcr() {
        FastRoiActivityProbe p=start();
        assertFalse(p.inspect(new Pixels(120),0).changed);
        FastRoiActivityProbe.Signal s=p.inspect(new Pixels(230),33);
        assertTrue(s.changed);
        assertTrue(s.risingEdge);
    }

    @Test public void stableCandidateOnlyTriggersOneRisingEdge() {
        FastRoiActivityProbe p=start();
        assertTrue(p.inspect(new Pixels(230),33).risingEdge);
        assertFalse(p.inspect(new Pixels(230),66).risingEdge);
        assertFalse(p.inspect(new Pixels(230),99).risingEdge);
    }

    @Test public void returnToBaselineDetectedInOneFrame() {
        FastRoiActivityProbe p=start();
        p.inspect(new Pixels(230),0);
        FastRoiActivityProbe.Signal s=p.inspect(new Pixels(120),33);
        assertTrue(s.returnedToBaseline);
        assertFalse(s.changed);
    }

    @Test public void anotherCandidateCanWakeImmediatelyAfterReturn() {
        FastRoiActivityProbe p=start();
        p.inspect(new Pixels(230),0);
        p.inspect(new Pixels(120),33);
        assertTrue(p.inspect(new Pixels(180),66).risingEdge);
    }

    @Test public void backgroundChangesAlsoTriggerAndAreNotRideEvidence() {
        FastRoiActivityProbe p=start();
        // A map scroll or gallery image can trigger. OCR/context decide safety.
        assertTrue(p.inspect(new Pixels(180),33).changed);
    }

    @Test public void invalidOrMissingRoiIsRejected() {
        FastRoiActivityProbe p=new FastRoiActivityProbe();
        assertFalse(p.armOnVerifiedNonOffer(new Pixels(120),
            new FastCardVisualTracker.Box(150,70,100,95)));
        assertFalse(p.isArmed());
    }

    @Test public void stopResetsBaselineAndCannotCarryOldTrigger() {
        FastRoiActivityProbe p=start();
        p.inspect(new Pixels(230),0);
        p.reset();
        assertFalse(p.isArmed());
        assertFalse(p.inspect(new Pixels(230),33).changed);
    }

    @Test public void staleTimestampDoesNotMakeNewOffer() {
        FastRoiActivityProbe p=start();
        assertTrue(p.inspect(new Pixels(230),100).risingEdge);
        assertFalse(p.inspect(new Pixels(230),99).risingEdge);
    }
}
