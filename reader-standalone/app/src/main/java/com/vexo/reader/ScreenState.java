package com.vexo.reader;

import android.os.SystemClock;

/** UI telemetry exists only in RAM; no screenshot or OCR text is written to logs. */
public final class ScreenState {
    public static volatile boolean active;
    public static volatile String status = "Leitura desligada";
    public static volatile int receivedFrames;
    public static volatile int ocrCompleted;
    public static volatile long lastFrameAt;
    public static volatile long lastReadingAt;
    public static volatile OfferRecord preview;
    public static volatile String roiLabel = "ROI: 15%–100% da altura, largura total";

    private ScreenState() { }
    public static OfferRecord freshPreview() {
        return active && SystemClock.elapsedRealtime() - lastReadingAt < 2500
            ? preview : null;
    }
    public static void invalidate(String reason) {
        preview = null;
        lastReadingAt = 0;
        status = reason;
    }
}
