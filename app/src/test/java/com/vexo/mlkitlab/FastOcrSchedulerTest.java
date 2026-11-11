package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public final class FastOcrSchedulerTest {
    @Test public void firstCardCanStartOcrOnFirstPresentFrame() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        assertEquals(1,s.maybeStart(true,0));
        assertTrue(s.isCurrent(1));
    }

    @Test public void fastVisualFramesDoNotStartThirtyConcurrentOcrCalls() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        assertEquals(1,s.maybeStart(true,0));
        for(int t=33;t<1000;t+=33) assertEquals(-1,s.maybeStart(true,t));
        assertTrue(s.complete(1));
        assertEquals(2,s.maybeStart(true,1023));
    }

    @Test public void newOcrImmediatelyAfterPreviousFinishWhenGapElapsed() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        long first=s.maybeStart(true,0);
        assertEquals(-1,s.maybeStart(true,33));
        assertTrue(s.complete(first));
        assertEquals(-1,s.maybeStart(true,66));
        assertEquals(2,s.maybeStart(true,132));
    }

    @Test public void missingCardInvalidatesPendingOcrBeforeCompletion() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        long old=s.maybeStart(true,0);
        assertEquals(-1,s.maybeStart(false,33));
        assertFalse(s.isCurrent(old));
        assertFalse(s.complete(old));
        long next=s.maybeStart(true,66);
        assertTrue(next>old);
    }

    @Test public void oldCallbackCannotFinishNewVisualEpisode() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        long first=s.maybeStart(true,0);
        s.markInvisible();
        long second=s.maybeStart(true,35);
        assertFalse(s.complete(first));
        assertTrue(s.isCurrent(second));
        assertTrue(s.complete(second));
    }

    @Test public void resetOnStopNeverReusesTicket() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        long a=s.maybeStart(true,0);
        s.reset();
        assertFalse(s.complete(a));
        long b=s.maybeStart(true,0);
        assertTrue(b>a);
    }

    @Test public void slowOcrCannotQueueHistoricalScreenshots() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        long ticket=s.maybeStart(true,0);
        for(int t=33;t<3000;t+=33) assertEquals(-1,s.maybeStart(true,t));
        assertTrue(s.complete(ticket));
        assertEquals(2,s.maybeStart(true,3003));
    }

    @Test public void timeRegressionCannotStartOcr() {
        FastOcrScheduler s=new FastOcrScheduler(120);
        long t=s.maybeStart(true,100);
        assertEquals(-1,s.maybeStart(true,99));
        assertTrue(s.isCurrent(t));
    }

    @Test(expected=IllegalArgumentException.class)
    public void invalidGapRejected() {
        new FastOcrScheduler(0);
    }
}
