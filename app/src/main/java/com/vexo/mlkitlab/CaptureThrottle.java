package com.vexo.mlkitlab;

/**
 * Controle independente da frequência. O código real nunca deve processar
 * vários frames simultaneamente; evita consumo excessivo e OCR de filas velhas.
 */
public final class CaptureThrottle {
    private final long minimumIntervalMs;
    private long lastStart=-1;
    private boolean busy=false;

    public CaptureThrottle(long intervalMs) {
        if(intervalMs<250) throw new IllegalArgumentException("intervalo muito curto");
        this.minimumIntervalMs=intervalMs;
    }

    public synchronized boolean begin(long monotonicMs) {
        if(busy) return false;
        if(lastStart>=0 && monotonicMs>=lastStart &&
            monotonicMs-lastStart<minimumIntervalMs) return false;
        busy=true;
        lastStart=monotonicMs;
        return true;
    }

    public synchronized void finish() { busy=false; }
    public synchronized void reset() { busy=false; lastStart=-1; }
}
