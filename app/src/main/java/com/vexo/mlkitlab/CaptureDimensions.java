package com.vexo.mlkitlab;

/** Limite de pixels antes de alocar ImageReader, superfície e bitmaps RGBA. */
public final class CaptureDimensions {
    private static final int MAX_DIMENSION=4096;
    private static final long MAX_PIXELS=6_000_000L;

    private static final int OCR_MAX_WIDTH=1080;
    private static final int OCR_REDUCED_SHORT_EDGE=640;
    private static final int OCR_REDUCED_LONG_EDGE=1440;

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

    /** Reduz só o bitmap do OCR; a superfície de captura mantém seu tamanho. */
    static int[] forOcr(int width,int height,boolean reduced) {
        if(width<=0 || height<=0)
            throw new IllegalArgumentException("dimensões de OCR inválidas");
        double scale=Math.min(1.0,OCR_MAX_WIDTH/(double)width);
        if(reduced) {
            scale=Math.min(scale,Math.min(
                OCR_REDUCED_SHORT_EDGE/(double)Math.min(width,height),
                OCR_REDUCED_LONG_EDGE/(double)Math.max(width,height)));
        }
        return new int[]{
            Math.max(1,(int)Math.round(width*scale)),
            Math.max(1,(int)Math.round(height*scale))
        };
    }

    public static boolean withinBudget(int w,int h) {
        return w>0 && h>0 && w<=MAX_DIMENSION && h<=MAX_DIMENSION &&
            (long)w*h<=MAX_PIXELS;
    }
}
