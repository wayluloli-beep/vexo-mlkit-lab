package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

/** Fully fabricated pixels. No screenshots, fares, addresses or 99 recordings. */
public final class FastCardVisualTrackerTest {
    private static final class PatternPixels implements FastCardVisualTracker.Pixels {
        final int width=260,height=200;
        final int x,y,w=112,h=86;
        final boolean card;
        final int variant;

        PatternPixels(int x,int y,boolean card,int variant) {
            this.x=x;this.y=y;this.card=card;this.variant=variant;
        }
        @Override public int width(){return width;}
        @Override public int height(){return height;}
        @Override public int luminance(int px,int py) {
            if(card && px>=x && px<x+w && py>=y && py<y+h) {
                int xx=px-x, yy=py-y;
                return (xx*31+yy*17+(xx/5)*(yy/7)*13+variant*41)&255;
            }
            return 110;
        }
    }

    private static FastCardVisualTracker make() {
        FastCardVisualTracker tracker=new FastCardVisualTracker();
        assertTrue(tracker.armFromVerifiedCard(new PatternPixels(65,44,true,0),
            new FastCardVisualTracker.Box(65,44,112,86)));
        return tracker;
    }

    @Test public void firstFrameShowsVisualPresenceWithoutOcr() {
        FastCardVisualTracker tracker=make();
        FastCardVisualTracker.Observation obs=tracker.inspect(
            new PatternPixels(65,44,true,0),0);
        assertTrue(obs.present);
        assertTrue(obs.appeared);
        assertFalse(obs.disappeared);
        assertEquals(0,obs.meanDifference);
    }

    @Test public void smallPositionDriftIsTrackedAtOnePixelPrecision() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),0);
        FastCardVisualTracker.Observation obs=tracker.inspect(
            new PatternPixels(74,37,true,0),33);
        assertTrue(obs.present);
        assertFalse(obs.appeared);
        assertEquals(74,obs.x);
        assertEquals(37,obs.y);
    }

    @Test public void multipleSmallMotionStepsRemainVisible() {
        FastCardVisualTracker tracker=make();
        for(int i=0;i<9;i++) {
            FastCardVisualTracker.Observation o=tracker.inspect(
                new PatternPixels(65+i*3,44+i*2,true,0),i*33);
            assertTrue("frame "+i,o.present);
            if(i>0) assertFalse(o.appeared);
        }
    }

    @Test public void disappearingCardIsHiddenOnFirstFrameNotAfterThreeSeconds() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),0);
        FastCardVisualTracker.Observation vanished=tracker.inspect(
            new PatternPixels(65,44,false,0),33);
        assertTrue(vanished.disappeared);
        assertFalse(vanished.present);
    }

    @Test public void oldTemplateDoesNotClaimNewCardWithChangedPixels() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),0);
        FastCardVisualTracker.Observation changed=tracker.inspect(
            new PatternPixels(65,44,true,1),33);
        assertFalse(changed.present);
        assertTrue(changed.disappeared);
    }

    @Test public void sameCardDoesNotBlinkOverTenSeconds() {
        FastCardVisualTracker tracker=make();
        int appearances=0;
        for(int i=0;i<301;i++) {
            FastCardVisualTracker.Observation o=tracker.inspect(
                new PatternPixels(65,44,true,0),i*33);
            appearances+=o.appeared?1:0;
            assertTrue(o.present);
        }
        assertEquals(1,appearances);
    }

    @Test public void firstFrameAfterFiveSecondsStillTrackedVisually() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),0);
        assertTrue(tracker.inspect(new PatternPixels(65,44,true,0),5000).present);
    }

    @Test public void flatBackgroundCannotArmAsCard() {
        FastCardVisualTracker tracker=new FastCardVisualTracker();
        assertFalse(tracker.armFromVerifiedCard(new PatternPixels(65,44,false,0),
            new FastCardVisualTracker.Box(65,44,112,86)));
        assertFalse(tracker.isArmed());
    }

    @Test public void offscreenBoxCannotArm() {
        FastCardVisualTracker tracker=new FastCardVisualTracker();
        assertFalse(tracker.armFromVerifiedCard(new PatternPixels(65,44,true,0),
            new FastCardVisualTracker.Box(220,150,112,86)));
    }

    @Test public void resetOnStopErasesReferenceAndPresence() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),0);
        tracker.reset();
        assertFalse(tracker.isPresent());
        assertFalse(tracker.isArmed());
        assertFalse(tracker.inspect(new PatternPixels(65,44,true,0),100).present);
    }

    @Test public void olderFrameCannotFabricateDisappearance() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),100);
        FastCardVisualTracker.Observation old=tracker.inspect(
            new PatternPixels(65,44,false,0),99);
        assertTrue(old.present);
        assertFalse(old.disappeared);
        assertFalse(old.appeared);
        assertTrue(tracker.isPresent());
        assertTrue(tracker.inspect(new PatternPixels(65,44,true,0),101).present);
    }

    @Test public void olderCardCannotResurrectAfterNewerDisappearance() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),100);
        assertTrue(tracker.inspect(new PatternPixels(65,44,false,0),102).disappeared);
        FastCardVisualTracker.Observation old=tracker.inspect(
            new PatternPixels(65,44,true,0),101);
        assertFalse(old.present);
        assertFalse(old.appeared);
        assertFalse(old.disappeared);
        assertFalse(tracker.isPresent());
        assertTrue(tracker.inspect(new PatternPixels(65,44,true,0),103).appeared);
    }

    @Test public void reacquireSameReferenceAfterBriefOcclusion() {
        FastCardVisualTracker tracker=make();
        tracker.inspect(new PatternPixels(65,44,true,0),0);
        tracker.inspect(new PatternPixels(65,44,false,0),33);
        FastCardVisualTracker.Observation again=tracker.inspect(
            new PatternPixels(65,44,true,0),66);
        assertTrue(again.present);
        assertTrue(again.appeared);
    }
}
