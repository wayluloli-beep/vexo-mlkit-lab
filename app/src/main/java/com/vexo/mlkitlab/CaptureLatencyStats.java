package com.vexo.mlkitlab;

import java.util.Arrays;

/**
 * Métricas agregadas exclusivamente na RAM; não retém OCR, frames nem dados
 * pessoais. Histórico máximo de 128 amostras, nunca logs de trajetos.
 */
public final class CaptureLatencyStats {
    private static final int MAX_SAMPLES=128;
    private final long[] recentMs=new long[MAX_SAMPLES];
    private int count=0;
    private int next=0;
    private long last=0;
    private long max=0;
    private long total=0;
    private long totalSamples=0;

    public synchronized void reset() {
        count=0;
        next=0;
        last=0;
        max=0;
        total=0;
        totalSamples=0;
        Arrays.fill(recentMs,0L);
    }

    public synchronized void record(long elapsedMs) {
        if(elapsedMs<0 || elapsedMs>600000) return;
        recentMs[next]=elapsedMs;
        next=(next+1)%MAX_SAMPLES;
        if(count<MAX_SAMPLES) count++;
        totalSamples++;
        total+=elapsedMs;
        last=elapsedMs;
        max=Math.max(max,elapsedMs);
    }

    public synchronized long[] snapshot() {
        if(count==0) return new long[]{0,0,0,0,0,0};
        long[] sorted=Arrays.copyOf(recentMs,count);
        Arrays.sort(sorted);
        long p50=sorted[(int)Math.ceil(count*0.5)-1];
        long p95=sorted[(int)Math.ceil(count*0.95)-1];
        return new long[]{totalSamples,last,total/totalSamples,p50,p95,max};
    }
}
