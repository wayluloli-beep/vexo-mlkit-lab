package com.vexo.mlkitlab;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Autoriza OCR atrasado somente quando um quadro recente confirma os mesmos pixels. */
final class CaptureFrameRecheck {
    private static final long DIRECT_AGE_MS=3000;
    private static final long SAMPLE_AFTER_MS=2700;
    private static final long SAMPLE_INTERVAL_MS=100;
    private static final long RECENT_SAMPLE_MS=300;

    static final class Fingerprint {
        private final int width, height;
        private final long hash;

        private Fingerprint(int width,int height,long hash) {
            this.width=width;
            this.height=height;
            this.hash=hash;
        }

        boolean sameAs(Fingerprint other) {
            return other!=null && width==other.width && height==other.height && hash==other.hash;
        }
    }

    private final long originalAtMs, originalTimestamp;
    private final Fingerprint original;
    private long latestAtMs=-1, latestTimestamp;
    private Fingerprint latest;

    CaptureFrameRecheck(long originalAtMs,long originalTimestamp,Fingerprint original) {
        this.originalAtMs=originalAtMs;
        this.originalTimestamp=originalTimestamp;
        this.original=original;
    }

    synchronized boolean shouldSample(long atMs) {
        return original!=null && originalTimestamp>0 && atMs>=originalAtMs &&
            atMs-originalAtMs>=SAMPLE_AFTER_MS &&
            (latestAtMs<0 || atMs-latestAtMs>=SAMPLE_INTERVAL_MS);
    }

    synchronized void observe(long atMs,long timestamp,Fingerprint sample) {
        if(atMs<originalAtMs || atMs<latestAtMs) return;
        latestAtMs=atMs;
        latestTimestamp=timestamp;
        latest=sample;
    }

    synchronized boolean canPublish(long nowMs) {
        if(CaptureFrameFreshness.isFresh(originalAtMs,nowMs,DIRECT_AGE_MS)) return true;
        return originalAtMs>=0 && originalTimestamp>0 && latestTimestamp>originalTimestamp &&
            latestAtMs>originalAtMs && original!=null && original.sameAs(latest) &&
            CaptureFrameFreshness.isFresh(latestAtMs,nowMs,RECENT_SAMPLE_MS);
    }

    /** Hash de todos os pixels RGBA, sem padding da linha e sem guardar a imagem. */
    static Fingerprint fingerprint(ByteBuffer rgba,int width,int height,int stride,int pixelStride) {
        if(rgba==null || width<=0 || height<=0 || pixelStride!=4 || stride<(long)width*4 ||
            (long)(height-1)*stride+(long)width*4>rgba.limit()) return null;
        ByteBuffer view=rgba.duplicate().order(ByteOrder.BIG_ENDIAN);
        long hash=0xcbf29ce484222325L;
        for(int y=0;y<height;y++) {
            int start=y*stride, end=start+width*4;
            for(int offset=start;offset<end;offset+=4)
                hash=(hash^Integer.toUnsignedLong(view.getInt(offset)))*0x100000001b3L;
        }
        return new Fingerprint(width,height,hash);
    }
}
