package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import java.nio.ByteBuffer;
import org.junit.Test;

public final class RgbaLumaPixelsTest {
    private static ByteBuffer onePixel(int r,int g,int b,int a) {
        ByteBuffer p=ByteBuffer.allocate(4);
        p.put(0,(byte)r);p.put(1,(byte)g);
        p.put(2,(byte)b);p.put(3,(byte)a);
        return p;
    }

    @Test public void blackWhiteLuminanceMatchesExpected() {
        assertEquals(0,new RgbaLumaPixels(onePixel(0,0,0,255),1,1,4,4).luminance(0,0));
        assertEquals(256,new RgbaLumaPixels(onePixel(255,255,255,255),1,1,4,4).luminance(0,0)+1);
    }

    @Test public void greenWeightingIsGreaterThanBlueWeighting() {
        int green=new RgbaLumaPixels(onePixel(0,255,0,255),1,1,4,4).luminance(0,0);
        int blue=new RgbaLumaPixels(onePixel(0,0,255,255),1,1,4,4).luminance(0,0);
        assertTrue(green>blue);
    }

    @Test public void rowPaddingIsIgnored() {
        ByteBuffer p=ByteBuffer.allocate(16);
        p.put(0,(byte)10);p.put(1,(byte)10);p.put(2,(byte)10);
        p.put(8,(byte)200);p.put(9,(byte)200);p.put(10,(byte)200);
        RgbaLumaPixels adapter=new RgbaLumaPixels(p,1,2,8,4);
        assertEquals(10,adapter.luminance(0,0));
        assertEquals(200,adapter.luminance(0,1));
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectInsufficientPlaneBytes() {
        new RgbaLumaPixels(ByteBuffer.allocate(3),1,1,4,4);
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectUnexpectedPixelStride() {
        new RgbaLumaPixels(ByteBuffer.allocate(8),1,1,8,3);
    }

    @Test(expected=IndexOutOfBoundsException.class)
    public void outOfBoundsSamplingRejected() {
        new RgbaLumaPixels(onePixel(0,0,0,255),1,1,4,4).luminance(1,0);
    }
}
