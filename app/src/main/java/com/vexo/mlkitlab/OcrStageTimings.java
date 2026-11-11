package com.vexo.mlkitlab;

import java.util.Arrays;

/** In-memory, aggregate-only stage timing. No OCR text, coordinates or images. */
public final class OcrStageTimings {
    public enum Stage { CAPTURE, DETECT, CROP, OCR, PARSE, PRESENT }
    private static final int CAPACITY=128;
    private final long[][] samples=new long[Stage.values().length][CAPACITY];
    private final int[] count=new int[Stage.values().length];
    private final int[] cursor=new int[Stage.values().length];

    /** Record only measured monotonic durations; invalid values are discarded. */
    public synchronized void record(Stage stage,long startedMs,long finishedMs) {
        if(stage==null || startedMs<0 || finishedMs<startedMs) return;
        long duration=finishedMs-startedMs;
        if(duration>120000) return;
        int i=stage.ordinal();
        samples[i][cursor[i]]=duration;
        cursor[i]=(cursor[i]+1)%CAPACITY;
        count[i]=Math.min(CAPACITY,count[i]+1);
    }
    public synchronized int count(Stage stage) { return count[stage.ordinal()]; }
    public synchronized long percentile(Stage stage,int percentile) {
        if(percentile<0 || percentile>100) throw new IllegalArgumentException("percentile");
        int i=stage.ordinal(),n=count[i];
        if(n==0) return -1;
        long[] copy=Arrays.copyOf(samples[i],n);
        Arrays.sort(copy);
        int index=Math.max(0,(int)Math.ceil(percentile*n/100.0)-1);
        return copy[index];
    }
    public synchronized void clear() {
        for(long[] row:samples) Arrays.fill(row,0);
        Arrays.fill(count,0);
        Arrays.fill(cursor,0);
    }
}
