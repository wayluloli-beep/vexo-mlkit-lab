package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public final class CaptureLatencyStatsTest {
    @Test public void smallSamplePercentilesAreConservative() {
        CaptureLatencyStats s=new CaptureLatencyStats();
        s.record(300);
        s.record(1500);
        s.record(500);
        assertArrayEquals(new long[]{3,500,766,500,1500,1500},s.snapshot());
    }

    @Test public void rejectsInvalidLatenciesAndResetsBetweenSessions() {
        CaptureLatencyStats s=new CaptureLatencyStats();
        s.record(-1);
        s.record(600001);
        assertEquals(0,s.snapshot()[0]);
        s.record(800);
        assertEquals(1,s.snapshot()[0]);
        s.reset();
        assertArrayEquals(new long[]{0,0,0,0,0,0},s.snapshot());
    }

    @Test public void retainsOnlyLast128SamplesForPercentileButAllForMean() {
        CaptureLatencyStats s=new CaptureLatencyStats();
        for(int i=0;i<200;i++) s.record(i);
        long[] values=s.snapshot();
        assertEquals(200,values[0]);
        assertEquals(199,values[1]);
        assertEquals(99,values[2]);
        assertEquals(135,values[3]);
        assertEquals(192,values[4]);
        assertEquals(199,values[5]);
    }
}
