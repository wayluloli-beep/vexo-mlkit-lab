package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

public class OcrRoiPlannerTest {
    @Test public void expandsForPriceAndDistanceLabels() {
        OcrRoiPlanner.Roi r=OcrRoiPlanner.expand(1080,2400,200,500,600,450);
        assertNotNull(r);
        assertTrue(r.x<200 && r.y<500);
        assertTrue(r.x+r.width>800 && r.y+r.height>950);
        assertTrue(OcrRoiPlanner.worthwhile(1080,2400,r));
    }
    @Test public void clampsToScreenEdges() {
        OcrRoiPlanner.Roi r=OcrRoiPlanner.expand(1080,2400,0,0,200,300);
        assertEquals(0,r.x);assertEquals(0,r.y);
        assertTrue(r.width<=1080 && r.height<=2400);
    }
    @Test public void rejectsOutOfBoundsAndOverflow() {
        assertNull(OcrRoiPlanner.expand(1080,2400,1000,100,200,200));
        assertNull(OcrRoiPlanner.expand(1080,2400,Integer.MAX_VALUE,0,Integer.MAX_VALUE,10));
        assertNull(OcrRoiPlanner.expand(1080,2400,0,0,0,20));
        assertNull(OcrRoiPlanner.expand(0,2400,0,0,20,20));
    }
    @Test public void avoidsUselessNearlyFullScreenCrop() {
        OcrRoiPlanner.Roi r=OcrRoiPlanner.expand(1080,2400,0,0,1080,2400);
        assertFalse(OcrRoiPlanner.worthwhile(1080,2400,r));
    }
}
