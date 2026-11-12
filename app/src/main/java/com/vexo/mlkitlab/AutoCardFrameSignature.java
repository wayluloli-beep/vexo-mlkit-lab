package com.vexo.mlkitlab;

import android.graphics.Bitmap;
import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import com.vexo.mlkitlab.FastCardVisualTracker.Pixels;

/**
 * Cheap ephemeral check: does the CURRENT MediaProjection frame still contain
 * the pixels recognized by a potentially slow full-screen OCR result?
 * Refuses to attach an old OCR rectangle to a different screen.
 */
final class AutoCardFrameSignature {
    private static final int COLUMNS=16, ROWS=12;
    private AutoCardFrameSignature() {}

    static byte[] fromBitmap(Bitmap original,int frameWidth,int frameHeight,Box box) {
        if(original==null || box==null || !fits(box,frameWidth,frameHeight))
            return null;
        byte[] result=new byte[COLUMNS*ROWS];
        int bmpW=original.getWidth(),bmpH=original.getHeight();
        if(bmpW<2 || bmpH<2)return null;
        for(int r=0;r<ROWS;r++)for(int c=0;c<COLUMNS;c++) {
            int fx=sample(box.x,box.width,c,COLUMNS);
            int fy=sample(box.y,box.height,r,ROWS);
            int x=Math.min(bmpW-1,(int)((long)fx*bmpW/frameWidth));
            int y=Math.min(bmpH-1,(int)((long)fy*bmpH/frameHeight));
            int argb=original.getPixel(x,y);
            int red=(argb>>16)&255,green=(argb>>8)&255,blue=argb&255;
            result[r*COLUMNS+c]=(byte)((77*red+150*green+29*blue+128)>>8);
        }
        return result;
    }

    static boolean matches(byte[] baseline,Pixels current,Box box) {
        if(baseline==null || baseline.length!=COLUMNS*ROWS ||
            current==null || box==null || !fits(box,current.width(),current.height()))
            return false;
        int deviation=0,large=0;
        for(int r=0;r<ROWS;r++)for(int c=0;c<COLUMNS;c++) {
            int x=sample(box.x,box.width,c,COLUMNS);
            int y=sample(box.y,box.height,r,ROWS);
            int diff=Math.abs((baseline[r*COLUMNS+c]&255)-current.luminance(x,y));
            deviation+=diff;
            if(diff>40)large++;
        }
        return deviation<=baseline.length*24 && large<=baseline.length/3;
    }

    private static boolean fits(Box box,int width,int height) {
        return width>0 && height>0 && box.width>=24 && box.height>=24 &&
            box.x>=0 && box.y>=0 && (long)box.x+box.width<=width &&
            (long)box.y+box.height<=height;
    }
    private static int sample(int from,int size,int at,int count) {
        return from+(int)((long)(2*at+1)*size/(2*count));
    }
}
