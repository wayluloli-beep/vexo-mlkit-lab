package com.vexo.mlkitlab;

/** Rejeita callback OCR que chega muito depois do frame do ImageReader. */
public final class CaptureFrameFreshness {
    private CaptureFrameFreshness() {}
    public static boolean isFresh(long acquiredAtMs,long nowMs,long maxAgeMs) {
        return acquiredAtMs>=0 && nowMs>=acquiredAtMs &&
            maxAgeMs>0 && nowMs-acquiredAtMs<=maxAgeMs;
    }
}
