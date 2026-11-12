package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

/**
 * Synthetic pixels. No screenshots, private user data or 99 UI fixtures.
 * These assertions describe motion markers, NOT live-offer recognition.
 */
public final class LiveScreenMotionDetectorTest {
    private static final class Pixels implements FastCardVisualTracker.Pixels {
        final int w,h,x,y,bw,bh,inside,outside;
        Pixels(int w,int h,int x,int y,int bw,int bh,int inside,int outside) {
            this.w=w;this.h=h;this.x=x;this.y=y;this.bw=bw;this.bh=bh;
            this.inside=inside;this.outside=outside;
        }
        @Override public int width(){return w;}
        @Override public int height(){return h;}
        @Override public int luminance(int px,int py){
            return px>=x && px<x+bw && py>=y && py<y+bh ? inside : outside;
        }
    }
    private static Pixels baseline(){return new Pixels(400,700,0,0,0,0,0,80);}
    private static Pixels card(int x,int y,int shade){
        return new Pixels(400,700,x,y,170,100,shade,80);
    }
    @Test public void firstFrameIsBaselineNotFalseOffer() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        LiveScreenMotionDetector.Observation o=d.inspect(baseline(),0);
        assertTrue(o.current);
        assertFalse(o.motion);
        assertNull(o.box);
    }
    @Test public void rectangleCausesBlueMotionMarkerInFirstChangedFrame() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        LiveScreenMotionDetector.Observation o=d.inspect(card(105,200,230),33);
        assertTrue(o.motion);
        assertNotNull(o.box);
        assertTrue(Math.abs(o.box.x-105)<=30);
        assertTrue(Math.abs(o.box.y-200)<=30);
    }
    @Test public void stationaryCardDoesNotCauseFakeContinuousMotion() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        assertTrue(d.inspect(card(105,200,230),33).motion);
        LiveScreenMotionDetector.Observation still=d.inspect(card(105,200,230),66);
        assertFalse(still.motion);
        assertNull(still.box);
    }
    @Test public void movingCardCreatesNewMarker() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        d.inspect(card(105,200,230),33);
        LiveScreenMotionDetector.Observation moved=d.inspect(card(130,218,230),66);
        assertTrue(moved.motion);
    }
    @Test public void removingCardProducesDisappearanceMotion() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        d.inspect(card(105,200,230),33);
        LiveScreenMotionDetector.Observation gone=d.inspect(baseline(),66);
        assertTrue(gone.motion);
        assertNotNull(gone.box);
    }
    @Test public void fullScreenAppSwitchNotMistakenForLocalCard() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        LiveScreenMotionDetector.Observation screen=d.inspect(
            new Pixels(400,700,0,0,400,700,230,80),33);
        assertTrue(screen.wholeScreenChanged);
        assertNull(screen.box);
    }
    @Test public void rotationReinitializes() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        LiveScreenMotionDetector.Observation r=d.inspect(
            new Pixels(700,400,0,0,0,0,80,80),33);
        assertTrue(r.resized);
        assertNull(r.box);
    }
    @Test public void framesAreCountedAsMeasuredNotAssumedThirtyFps() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        for(int k=1;k<=15;k++)d.inspect(baseline(),k*100L);
        assertTrue(d.inspect(baseline(),1600).fps>=8);
        assertTrue(d.inspect(baseline(),1600).fps<=11);
    }
    @Test public void outOfOrderFrameDoesNotResetVisualState() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),100);
        d.inspect(card(105,200,230),133);
        LiveScreenMotionDetector.Observation old=d.inspect(baseline(),120);
        assertFalse(old.current);
        assertFalse(old.motion);
        assertFalse(d.inspect(card(105,200,230),166).motion);
    }
    @Test public void stopResetsOldVisualState() {
        LiveScreenMotionDetector d=new LiveScreenMotionDetector();
        d.inspect(baseline(),0);
        d.inspect(card(105,200,230),33);
        d.reset();
        LiveScreenMotionDetector.Observation first=d.inspect(card(105,200,230),100);
        assertFalse(first.motion);
        assertEquals(0,first.fps);
    }
}
