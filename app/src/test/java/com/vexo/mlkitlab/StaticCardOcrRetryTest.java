package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public final class StaticCardOcrRetryTest {
    @Test public void cardWithoutChangesRetriesAfterFailureInsteadOfFreezing() {
        StaticCardOcrRetry r=new StaticCardOcrRetry();
        assertTrue(r.mayStart(11,100));
        r.started(11,100);
        assertFalse(r.mayStart(11,120));
        r.finished(11,200,false);
        assertFalse(r.mayStart(11,649));
        assertTrue(r.mayStart(11,650));
        r.started(11,650);
        r.finished(11,730,true);
        assertFalse(r.mayStart(11,2000));
        assertEquals(2,r.attempts(11));
    }

    @Test public void stopsAfterThreeFailedAttempts() {
        StaticCardOcrRetry r=new StaticCardOcrRetry();
        long t=0;
        for(int i=0;i<3;i++) {
            assertTrue(r.mayStart(1,t));
            r.started(1,t);
            r.finished(1,t+50,false);
            t=t+50+(450L*(i+1));
        }
        assertTrue(r.exhausted(1));
        assertFalse(r.mayStart(1,100000));
        assertEquals(3,r.attempts(1));
    }

    @Test public void newVisualRevisionImmediatelyInvalidatesOldFailedSlot() {
        StaticCardOcrRetry r=new StaticCardOcrRetry();
        r.started(1,0);
        r.finished(1,10,false);
        assertFalse(r.mayStart(1,20));
        assertTrue(r.mayStart(2,20));
        r.started(2,20);
        r.finished(1,999,true); // stale callback from a previous card must not succeed
        assertFalse(r.mayStart(2,21)); // new OCR is still in flight
        r.finished(2,30,true);
        assertFalse(r.mayStart(2,800));
    }

    @Test public void successfulResultNeverRepeatsOnStillFrame() {
        StaticCardOcrRetry r=new StaticCardOcrRetry();
        r.started(4,100);
        r.finished(4,110,true);
        assertFalse(r.mayStart(4,100000));
        assertFalse(r.exhausted(4));
    }

    @Test public void stopClearsAllRetryState() {
        StaticCardOcrRetry r=new StaticCardOcrRetry();
        r.started(5,0);
        r.finished(5,10,false);
        r.reset();
        assertTrue(r.mayStart(5,20));
        r.started(5,20);
        assertEquals(1,r.attempts(5));
    }

    @Test public void noTimeTravelOrInvalidRevision() {
        StaticCardOcrRetry r=new StaticCardOcrRetry();
        assertFalse(r.mayStart(-1,100));
        assertFalse(r.mayStart(1,-10));
    }
}
