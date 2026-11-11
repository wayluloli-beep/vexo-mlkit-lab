package com.vexo.mlkitlab;

/**
 * Event-driven OCR admission policy for a future card tracker integration.
 * Fast pixel observation MUST NOT be rate-limited by this policy.
 *
 * One OCR in flight, newest ROI only; never queue historical screenshots.
 * A callback may publish ONLY if its ticket remains current and the Android
 * service independently validates consent, epoch, content and frame age.
 */
public final class FastOcrScheduler {
    private final long minimumStartGapMs;
    private long previousStartMs=-1;
    private long lastObservedMs=-1;
    private long nextTicket=0;
    private long activeTicket=-1;
    private boolean visible=false;

    public FastOcrScheduler(long minimumStartGapMs) {
        if(minimumStartGapMs<50 || minimumStartGapMs>5000)
            throw new IllegalArgumentException("invalid experimental gap");
        this.minimumStartGapMs=minimumStartGapMs;
    }

    /** -1 = no work. Track every frame regardless of this return value. */
    public synchronized long maybeStart(boolean visualCardPresent,long nowMs) {
        if(nowMs<0 || nowMs<lastObservedMs) return -1;
        lastObservedMs=nowMs;
        if(!visualCardPresent) {
            markInvisible();
            return -1;
        }
        visible=true;
        if(activeTicket!=-1) return -1;
        if(previousStartMs!=-1 && nowMs-previousStartMs<minimumStartGapMs)
            return -1;
        activeTicket=++nextTicket;
        previousStartMs=nowMs;
        return activeTicket;
    }

    /** Does NOT publish OCR contents; the Android service must validate safety. */
    public synchronized boolean complete(long ticket) {
        if(ticket<0 || ticket!=activeTicket || !visible) return false;
        activeTicket=-1;
        return true;
    }

    /** A card disappearing invalidates callbacks immediately without OCR wait. */
    public synchronized void markInvisible() {
        visible=false;
        activeTicket=-1;
        previousStartMs=-1; // next new visual episode can request OCR immediately
    }

    public synchronized boolean isCurrent(long ticket) {
        return visible && activeTicket==ticket && ticket>=0;
    }

    public synchronized void reset() {
        markInvisible();
        lastObservedMs=-1;
        // Do NOT reuse ticket after STOP/restart. Increment monotonically.
    }
}
