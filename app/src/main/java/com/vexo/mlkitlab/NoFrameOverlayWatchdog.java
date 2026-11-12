package com.vexo.mlkitlab;

/**
 * Session-local absence-of-frames gate for clearing stale visible numbers.
 * Does not claim anything about an app or card, only about callback freshness.
 */
public final class NoFrameOverlayWatchdog {
    private long lastFrameMs=-1;
    private long lastClearedFrameMs=-1;

    public synchronized void onFrame(long nowMs) {
        if(nowMs<0 || nowMs<lastFrameMs)return;
        lastFrameMs=nowMs;
    }
    /** Returns true at most once per last frame; avoids repeated UI blinking. */
    public synchronized boolean shouldClear(long nowMs,long maxIdleMs) {
        if(lastFrameMs<0 || nowMs<lastFrameMs || maxIdleMs<1 ||
            nowMs-lastFrameMs<=maxIdleMs || lastClearedFrameMs==lastFrameMs)
            return false;
        lastClearedFrameMs=lastFrameMs;
        return true;
    }
    public synchronized long ageMs(long nowMs) {
        if(lastFrameMs<0 || nowMs<lastFrameMs)return -1;
        return nowMs-lastFrameMs;
    }
    public synchronized void reset() {
        lastFrameMs=-1;lastClearedFrameMs=-1;
    }
}
