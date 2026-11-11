package com.vexo.mlkitlab;

/** Limite de pixels antes de alocar ImageReader, superfície e bitmaps RGBA. */
public final class CaptureDimensions {
    private static final int MAX_DIMENSION=4096;
    private static final long MAX_PIXELS=6_000_000L;

    private CaptureDimensions() {}

    public static int[] fit(int width,int height) {
        if(width<=0 || height<=0)
            throw new IllegalArgumentException("dimensões de captura inválidas");
        long pixels=(long)width*height;
        double scale=Math.min(1.0,
            Math.min(MAX_DIMENSION/(double)Math.max(width,height),
                Math.sqrt(MAX_PIXELS/(double)pixels)));
        int w=Math.max(1,(int)Math.floor(width*scale));
        int h=Math.max(1,(int)Math.floor(height*scale));
        return new int[]{w,h};
    }

    public static boolean withinBudget(int w,int h) {
        return w>0 && h>0 && w<=MAX_DIMENSION && h<=MAX_DIMENSION &&
            (long)w*h<=MAX_PIXELS;
    }
}
