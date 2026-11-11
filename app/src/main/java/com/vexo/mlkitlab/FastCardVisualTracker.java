package com.vexo.mlkitlab;

import java.util.Arrays;

/**
 * Experimental low-cost VISUAL tracker, independent of ML Kit and of the
 * OfferEpisodeGate. Inspect every ImageReader callback before OCR throttling.
 *
 * It tracks a previously verified card-sized rectangle by 96 luminance
 * samples and small motion, without allocating or storing screen bitmaps.
 * A template is NOT proof of an active 99 offer: photos/replays can match it.
 *
 * This is a pure-Java component; Android integration and frame timing have
 * to be measured on-device before using it to show live financial values.
 */
public final class FastCardVisualTracker {
    private static final int COLS=12, ROWS=8;
    private static final int MAX_SHIFT=24, COARSE_STEP=4;
    private static final int MAX_MEAN_DIFFERENCE=27;
    private static final int MIN_TEXTURE_RANGE=35;

    public interface Pixels {
        int width();
        int height();
        /** 0..255 luminance for ONE point; no full-frame conversion required. */
        int luminance(int x,int y);
    }

    public static final class Box {
        public final int x,y,width,height;
        public Box(int x,int y,int width,int height) {
            this.x=x; this.y=y; this.width=width; this.height=height;
        }
    }

    public static final class Observation {
        public final boolean present;
        public final boolean appeared;
        public final boolean disappeared;
        public final int x,y;
        public final int meanDifference;
        Observation(boolean present, boolean appeared, boolean disappeared,
                    int x,int y,int meanDifference) {
            this.present=present; this.appeared=appeared;
            this.disappeared=disappeared; this.x=x; this.y=y;
            this.meanDifference=meanDifference;
        }
    }

    private final int[] template=new int[COLS*ROWS];
    private int x,y,width,height;
    private long lastTimestamp=-1;
    private boolean armed=false;
    private boolean present=false;

    public synchronized boolean armFromVerifiedCard(Pixels pixels, Box box) {
        reset();
        if(pixels==null || box==null || !valid(pixels,box.x,box.y,box.width,box.height)
                || box.width<36 || box.height<36) return false;
        int low=255,high=0,k=0;
        for(int row=0;row<ROWS;row++) {
            for(int col=0;col<COLS;col++) {
                int lum=at(pixels,box.x,box.y,box.width,box.height,col,row);
                if(lum<0 || lum>255) { reset(); return false; }
                template[k++]=lum;
                low=Math.min(low,lum);
                high=Math.max(high,lum);
            }
        }
        if(high-low<MIN_TEXTURE_RANGE) { reset(); return false; }
        x=box.x;y=box.y;width=box.width;height=box.height;
        armed=true;
        // Only arm after an independently confirmed, current card and mode.
        // Next real frame decides presence. No OCR or notifications here.
        return true;
    }

    public synchronized Observation inspect(Pixels pixels,long monotonicMs) {
        // Out-of-order callbacks must not fabricate disappearance or overwrite
        // a newer visual observation. Caller may ignore this neutral result.
        if(monotonicMs>=0 && monotonicMs<lastTimestamp)
            return new Observation(present,false,false,x,y,255);
        if(!armed || pixels==null || monotonicMs<0 ||
                pixels.width()<=0 || pixels.height()<=0) {
            boolean was=present;
            present=false;
            return new Observation(false,false,was,x,y,255);
        }
        lastTimestamp=monotonicMs;
        int best=256, bestX=x, bestY=y;
        for(int dy=-MAX_SHIFT;dy<=MAX_SHIFT;dy+=COARSE_STEP) {
            for(int dx=-MAX_SHIFT;dx<=MAX_SHIFT;dx+=COARSE_STEP) {
                int nextX=x+dx,nextY=y+dy;
                if(!valid(pixels,nextX,nextY,width,height)) continue;
                int score=distance(pixels,nextX,nextY);
                if(score<best) {best=score;bestX=nextX;bestY=nextY;}
            }
        }
        // Refine to single-pixel precision only around best coarse position.
        int centerX=bestX,centerY=bestY;
        for(int dy=-3;dy<=3;dy++) {
            for(int dx=-3;dx<=3;dx++) {
                int nextX=centerX+dx,nextY=centerY+dy;
                if(!valid(pixels,nextX,nextY,width,height)) continue;
                int score=distance(pixels,nextX,nextY);
                if(score<best) {best=score;bestX=nextX;bestY=nextY;}
            }
        }
        boolean nowPresent=best<=MAX_MEAN_DIFFERENCE;
        boolean appeared=nowPresent&&!present;
        boolean disappeared=present&&!nowPresent;
        if(nowPresent) {x=bestX;y=bestY;}
        present=nowPresent;
        // Hide an old financial summary on the FIRST absent observation;
        // do not wait 3 seconds or for an OCR callback.
        return new Observation(nowPresent,appeared,disappeared,x,y,best);
    }

    private int distance(Pixels pixels,int candidateX,int candidateY) {
        int total=0;
        for(int row=0,k=0;row<ROWS;row++) {
            for(int col=0;col<COLS;col++,k++) {
                int lum=at(pixels,candidateX,candidateY,width,height,col,row);
                if(lum<0 || lum>255) return 256;
                total+=Math.abs(lum-template[k]);
            }
        }
        return total/template.length;
    }

    private static int at(Pixels pixels,int x,int y,int w,int h,int col,int row) {
        int sx=x+1+((w-2)*col)/(COLS-1);
        int sy=y+1+((h-2)*row)/(ROWS-1);
        return pixels.luminance(sx,sy);
    }

    private static boolean valid(Pixels p,int x,int y,int w,int h) {
        return x>=0&&y>=0&&w>0&&h>0&&
            ((long)x+w)<=p.width()&&((long)y+h)<=p.height();
    }

    public synchronized boolean isArmed() {return armed;}
    public synchronized boolean isPresent() {return present;}
    public synchronized void reset() {
        Arrays.fill(template,0);
        x=0;y=0;width=0;height=0;
        lastTimestamp=-1;
        present=false;armed=false;
    }
}
