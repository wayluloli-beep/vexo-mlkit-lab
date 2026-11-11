package com.vexo.mlkitlab;

/**
 * Identidade de EPISÓDIO VISUAL de oferta, não do texto numérico isolado.
 *
 * Somente dois quadros inequivocamente sem oferta encerram o episódio.
 * OCR parcial/incerto NÃO é prova de que a oferta desapareceu.
 * Depois do primeiro alerta, um novo fingerprint sem essa transição
 * pode ser só erro numérico do OCR, portanto NÃO gera outro alerta.
 *
 * Dados conservados apenas durante a sessão, somente na memória local.
 */
public final class OfferEpisodeGate {
    private String fingerprint="";
    private int matchedFrames=0;
    private int absentFrames=0;
    private boolean alerted=false;

    public synchronized boolean observe(String next) {
        if(next==null || next.isEmpty()) {
            uncertain();
            return false;
        }
        absentFrames=0;
        if(alerted) {
            // Pode ser o mesmo card com erro de OCR, ou um segundo card com
            // valores diferentes sem transição observável. Não adivinhar.
            return false;
        }
        if(!next.equals(fingerprint)) {
            fingerprint=next;
            matchedFrames=1;
        } else {
            matchedFrames=Math.min(2,matchedFrames+1);
        }
        if(matchedFrames<2) return false;
        alerted=true;
        return true;
    }

    /** OCR parcial, oclusão, guarda financeira ou tela ambígua. */
    public synchronized void uncertain() {
        absentFrames=0;
        if(!alerted) matchedFrames=0; // exige dois frames válidos consecutivos
    }

    /**
     * Quadro definitivamente sem oferta ativa (mapa/post/histórico).
     * true somente ao encerrar um episódio no segundo quadro seguro.
     */
    public synchronized boolean nonOffer() {
        absentFrames=Math.min(2,absentFrames+1);
        if(absentFrames<2) {
            if(!alerted) matchedFrames=0;
            return false;
        }
        boolean closed=alerted || !fingerprint.isEmpty();
        fingerprint="";
        matchedFrames=0;
        alerted=false;
        return closed;
    }

    public synchronized void reset() {
        fingerprint="";
        matchedFrames=0;
        absentFrames=0;
        alerted=false;
    }
}
