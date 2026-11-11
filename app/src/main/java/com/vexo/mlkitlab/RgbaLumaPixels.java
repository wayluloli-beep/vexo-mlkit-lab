package com.vexo.mlkitlab;

import java.nio.ByteBuffer;

/**
 * Read-only adapter for the RGBA_8888 Image.Plane supplied by ImageReader.
 * Instantiate/use it ONLY while the Image is still open in its callback.
 * Does not copy pixels or persist ByteBuffer/screenshots.
 */
public final class RgbaLumaPixels implements FastCardVisualTracker.Pixels {
    private final ByteBuffer view;
    private final int width,height,rowStride,pixelStride;

    public RgbaLumaPixels(ByteBuffer rgba,int width,int height,
                          int rowStride,int pixelStride) {
        if(rgba==null || width<=0 || height<=0 ||
            pixelStride!=4 || rowStride<(long)width*4 ||
            (long)(height-1)*rowStride+(long)width*4>rgba.limit())
            throw new IllegalArgumentException("invalid RGBA plane");
        this.view=rgba.asReadOnlyBuffer();
        this.width=width;
        this.height=height;
        this.rowStride=rowStride;
        this.pixelStride=pixelStride;
    }

    @Override public int width() {return width;}
    @Override public int height() {return height;}

    @Override public int luminance(int x,int y) {
        if(x<0 || x>=width || y<0 || y>=height)
            throw new IndexOutOfBoundsException("pixel outside frame");
        int offset=y*rowStride+x*pixelStride;
        int red=view.get(offset)&255;
        int green=view.get(offset+1)&255;
        int blue=view.get(offset+2)&255;
        return (77*red+150*green+29*blue+128)>>8;
    }
}
