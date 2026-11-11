package com.vexo.mlkitlab;

/**
 * Conta episódios VISUAIS de oferta, não número de frames ou tempo em tela.
 * Sem dados pessoais, histórico, persistência nem relógio/cooldown.
 *
 * Duas leituras válidas iguais confirmam o episódio. Dois frames seguidos
 * de mapa/outra tela encerram a oferta e permitem detectar uma nova com
 * valores idênticos. Uma única falha de OCR não reabre alerta já emitido.
 */
public final class OfferEpisodeGate {
    private String fingerprint="";
    private int matchedFrames=0;
    private int absentFrames=0;
    private boolean alerted=false;

    public synchronized boolean observe(String next) {
        if(next==null || next.isEmpty()) {
            nonOffer();
            return false;
        }
        absentFrames=0;
        if(!next.equals(fingerprint)) {
            fingerprint=next;
            matchedFrames=1;
            alerted=false;
        } else {
            matchedFrames=Math.min(2,matchedFrames+1);
        }
        if(matchedFrames<2 || alerted) return false;
        alerted=true;
        return true;
    }

    public synchronized void nonOffer() {
        absentFrames=Math.min(2,absentFrames+1);
        matchedFrames=0;
        if(absentFrames>=2) {
            fingerprint="";
            alerted=false;
        }
    }

    public synchronized void reset() {
        fingerprint="";
        matchedFrames=0;
        absentFrames=0;
        alerted=false;
    }
}
