package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

/** Synthetic rectangles only. These tests do NOT prove 99 screen recognition. */
public final class AdaptiveCardRegionDetectorTest {
    private static final class Scene implements FastCardVisualTracker.Pixels {
        final int w,h,x,y,bw,bh,inside,outside;
        Scene(int w,int h,int x,int y,int bw,int bh,int inside,int outside) {
            this.w=w;this.h=h;this.x=x;this.y=y;this.bw=bw;this.bh=bh;
            this.inside=inside;this.outside=outside;
        }
        @Override public int width(){return w;}
        @Override public int height(){return h;}
        @Override public int luminance(int px,int py){
            return px>=x && px<x+bw && py>=y && py<y+bh ? inside : outside;
        }
    }
    private static Scene screen(int w,int h) {
        return new Scene(w,h,0,0,0,0,0,80);
    }
    private static Scene card(int w,int h,int x,int y,int cw,int ch,int intensity) {
        return new Scene(w,h,x,y,cw,ch,intensity,80);
    }
    private static boolean near(int actual,int expected,int tolerance){
        return Math.abs(actual-expected)<=tolerance;
    }

    @Test public void findsFirstCardAnywhereWithoutHardcodedCoordinates() {
        for(int[] xy:new int[][]{{20,70},{135,210},{180,410}}){
            AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
            assertTrue(d.armOnVerifiedNonOffer(screen(400,700)));
            AdaptiveCardRegionDetector.Result result=d.inspect(
                card(400,700,xy[0],xy[1],170,95,220),33);
            assertTrue("missing candidate x="+xy[0],result.suspiciousRegion);
            assertTrue(result.changedSinceLastFrame);
            assertNotNull(result.region);
            assertTrue(near(result.region.x,xy[0],25));
            assertTrue(near(result.region.y,xy[1],25));
        }
    }

    @Test public void adaptsToLandscapeAndDifferentSizes() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        assertTrue(d.armOnVerifiedNonOffer(screen(760,390)));
        AdaptiveCardRegionDetector.Result r=d.inspect(card(760,390,300,110,260,100,225),33);
        assertTrue(r.suspiciousRegion);
        assertTrue(near(r.region.x,300,25));
        assertTrue(near(r.region.y,110,25));
    }

    @Test public void stableSameCardDoesNotTriggerRepeatedUpdates() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        for(int i=1;i<=300;i++){
            AdaptiveCardRegionDetector.Result r=d.inspect(card(400,700,110,230,170,110,220),i*33L);
            assertTrue(r.suspiciousRegion);
            if(i>1) assertFalse("frame "+i,r.changedSinceLastFrame);
        }
    }

    @Test public void detectsDirectChangeFromCardAToBWithoutMap() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        assertTrue(d.inspect(card(400,700,110,230,170,110,220),33).changedSinceLastFrame);
        AdaptiveCardRegionDetector.Result b=d.inspect(card(400,700,110,230,170,110,155),66);
        assertTrue(b.suspiciousRegion);
        assertTrue("must notice A->B without intermediate map",b.changedSinceLastFrame);
    }

    @Test public void visibleCardReturnsToBackgroundInFirstFrame() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        d.inspect(card(400,700,110,230,170,110,220),0);
        AdaptiveCardRegionDetector.Result background=d.inspect(screen(400,700),33);
        assertFalse(background.suspiciousRegion);
        assertEquals(0,background.changedCells);
    }

    @Test public void wholeScreenAppTransitionIsNotClassifiedAsCard() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        AdaptiveCardRegionDetector.Result result=d.inspect(
            new Scene(400,700,0,0,400,700,220,80),33);
        assertFalse(result.suspiciousRegion);
        assertTrue(result.changedCells>0);
    }

    @Test public void resizeInvalidatesOldReferenceSafely() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        AdaptiveCardRegionDetector.Result r=d.inspect(screen(760,390),33);
        assertTrue(r.frameDimensionsChanged);
        assertFalse(d.isArmed());
        assertFalse(d.inspect(card(760,390,260,90,200,100,220),66).suspiciousRegion);
        assertTrue(d.armOnVerifiedNonOffer(screen(760,390)));
        assertTrue(d.inspect(card(760,390,260,90,200,100,220),99).suspiciousRegion);
    }

    @Test public void refusesBlankInvalidOrSmallBaseline() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        assertFalse(d.armOnVerifiedNonOffer(null));
        assertFalse(d.armOnVerifiedNonOffer(screen(80,100)));
        assertFalse(d.isArmed());
    }

    @Test public void mapAnimationWouldBeOnlyASuspectNotALiveOffer() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        AdaptiveCardRegionDetector.Result r=d.inspect(card(400,700,120,220,180,110,210),33);
        assertTrue(r.suspiciousRegion);
        // Scanner has no "is 99 offer" flag or alert API: only changed pixels.
        assertNotNull(r.region);
    }

    @Test public void stopDropsBaselineAndPosition() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        d.inspect(card(400,700,110,230,170,110,220),0);
        d.reset();
        assertFalse(d.isArmed());
        assertFalse(d.inspect(card(400,700,110,230,170,110,220),33).baselineReady);
    }

    @Test public void olderTimestampDoesNotReprocessFrame() {
        AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
        d.armOnVerifiedNonOffer(screen(400,700));
        d.inspect(screen(400,700),100);
        AdaptiveCardRegionDetector.Result old=d.inspect(card(400,700,110,230,170,110,220),99);
        assertFalse(old.suspiciousRegion);
    }
}
