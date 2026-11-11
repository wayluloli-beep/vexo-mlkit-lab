package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

public final class CaptureDimensionsTest {
    @Test public void typicalPhoneHasNoLoss() {
        assertArrayEquals(new int[]{1080,2400},CaptureDimensions.fit(1080,2400));
        assertArrayEquals(new int[]{1440,3200},CaptureDimensions.fit(1440,3200));
    }

    @Test public void rotationKeepsAspectAndBudget() {
        int[] portrait=CaptureDimensions.fit(2160,3840);
        int[] landscape=CaptureDimensions.fit(3840,2160);
        assertTrue(CaptureDimensions.withinBudget(portrait[0],portrait[1]));
        assertEquals(portrait[0],landscape[1]);
        assertEquals(portrait[1],landscape[0]);
    }

    @Test public void oversizedImageCannotExhaustMemory() {
        int[] result=CaptureDimensions.fit(12000,9000);
        assertTrue(CaptureDimensions.withinBudget(result[0],result[1]));
        assertTrue(result[0]<=4096);
    }

    @Test public void ocrPreservesDetailUntilReducedInputIsRequested() {
        assertArrayEquals(new int[]{1080,2400},CaptureDimensions.forOcr(1080,2400,false));
        assertArrayEquals(new int[]{640,1422},CaptureDimensions.forOcr(1080,2400,true));
        assertArrayEquals(new int[]{540,1200},CaptureDimensions.forOcr(540,1200,true));
    }

    @Test public void reducedOcrBoundsTallImagesAndDoesNotUpscaleLandscape() {
        assertArrayEquals(new int[]{480,1440},CaptureDimensions.forOcr(1080,3240,true));
        assertArrayEquals(new int[]{1080,486},CaptureDimensions.forOcr(2400,1080,true));
    }

    @Test(expected=IllegalArgumentException.class)
    public void invalidSizeIsRejected() {
        CaptureDimensions.fit(0,1024);
    }
}
