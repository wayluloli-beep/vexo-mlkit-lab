package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

public class OcrStageTimingsTest {
    @Test public void emptyIsUnknownNotZero() {
        OcrStageTimings t=new OcrStageTimings();
        assertEquals(-1,t.percentile(OcrStageTimings.Stage.OCR,95));
    }
    @Test public void percentileUsesMeasuredDurations() {
        OcrStageTimings t=new OcrStageTimings();
        for(int i=1;i<=100;i++) t.record(OcrStageTimings.Stage.OCR,1000,1000+i);
        assertEquals(50,t.percentile(OcrStageTimings.Stage.OCR,50));
        assertEquals(95,t.percentile(OcrStageTimings.Stage.OCR,95));
        assertEquals(0,t.count(OcrStageTimings.Stage.CROP));
    }
    @Test public void onlyLast128SamplesSurvive() {
        OcrStageTimings t=new OcrStageTimings();
        for(int i=0;i<200;i++) t.record(OcrStageTimings.Stage.DETECT,1000,1000+i);
        assertEquals(128,t.count(OcrStageTimings.Stage.DETECT));
        assertEquals(72,t.percentile(OcrStageTimings.Stage.DETECT,0));
        assertEquals(199,t.percentile(OcrStageTimings.Stage.DETECT,100));
    }
    @Test public void rejectsBadTimingAndClearsAll() {
        OcrStageTimings t=new OcrStageTimings();
        t.record(OcrStageTimings.Stage.CROP,20,10);
        t.record(OcrStageTimings.Stage.CROP,-1,10);
        t.record(OcrStageTimings.Stage.CROP,0,130000);
        assertEquals(0,t.count(OcrStageTimings.Stage.CROP));
        t.record(OcrStageTimings.Stage.CROP,100,105);
        t.clear();
        assertEquals(-1,t.percentile(OcrStageTimings.Stage.CROP,95));
    }
}
