package com.vexo.mlkitlab;

/**
 * Limited OCR retries on a visually STABLE selection.
 *
 * OCR may fail transiently while the same selected card stays on-screen.
 * Do not spin endlessly or resurrect an obsolete revision.
 * Instance is confined to the capture handler thread.
 */
final class StaticCardOcrRetry {
    private static final int MAX_ATTEMPTS=3;
    private static final long BASE_BACKOFF_MS=450L;
    private long revision=Long.MIN_VALUE;
    private int attempts;
    private long nextAttemptAt;
    private boolean inFlight;
    private boolean success;

    void reset() {
        revision=Long.MIN_VALUE;
        attempts=0;
        nextAttemptAt=0;
        inFlight=false;
        success=false;
    }

    private void acceptRevision(long value) {
        if(revision!=value) {
            revision=value;
            attempts=0;
            nextAttemptAt=0;
            inFlight=false;
            success=false;
        }
    }

    boolean mayStart(long value,long nowMs) {
        if(value<0 || nowMs<0)return false;
        acceptRevision(value);
        return !inFlight && !success &&
            attempts<MAX_ATTEMPTS && nowMs>=nextAttemptAt;
    }

    void started(long value,long nowMs) {
        if(!mayStart(value,nowMs))throw new IllegalStateException("OCR retry slot unavailable");
        attempts++;
        inFlight=true;
    }

    void finished(long value,long nowMs,boolean readable) {
        if(value!=revision || !inFlight)return;
        inFlight=false;
        if(readable) {
            success=true;
        } else {
            long delay=BASE_BACKOFF_MS * attempts;
            nextAttemptAt=Math.max(nextAttemptAt,nowMs+delay);
        }
    }

    boolean exhausted(long value) {
        return revision==value && !success && !inFlight &&
            attempts>=MAX_ATTEMPTS;
    }

    int attempts(long value) {
        return revision==value ? attempts : 0;
    }
}
