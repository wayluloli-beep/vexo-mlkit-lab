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
    private static final long MAX_MATCH_GAP_MS=5500L;
    private String fingerprint="";
    private int matchedFrames=0;
    private int interveningUncertain=0;
    private long lastValidAtMs=-1;
    private int absentFrames=0;
    private boolean alerted=false;
    private boolean summaryHidden=false;
    private int restoreFrames=0;
    private boolean restorationPending=false;

    public synchronized boolean observe(String next) {
        return observeAt(next,System.nanoTime()/1000000L);
    }

    /** Clock monotônico explícito para testes e confirmação temporal. */
    public synchronized boolean observeAt(String next,long elapsedMs) {
        if(next==null || next.isEmpty()) {
            uncertain();
            return false;
        }
        absentFrames=0;
        if(alerted) {
            // O resumo oculto pode reaparecer somente após DUAS leituras
            // idênticas à oferta confirmada, sem disparar novo alerta.
            if(summaryHidden) {
                if(next.equals(fingerprint)) {
                    restoreFrames=Math.min(2,restoreFrames+1);
                    if(restoreFrames>=2) {
                        summaryHidden=false;
                        restorationPending=true;
                    }
                } else {
                    restoreFrames=0; // valor diferente pode ser OCR errado
                }
            }
            return false;
        }
        // Uma leitura incerta entre duas completas não apaga a primeira.
        // Para confirmar: mesmo fingerprint e intervalo máximo 5,5s.
        if(!next.equals(fingerprint) || matchedFrames==0 ||
                lastValidAtMs<0 || elapsedMs<lastValidAtMs ||
                elapsedMs-lastValidAtMs>MAX_MATCH_GAP_MS) {
            fingerprint=next;
            matchedFrames=1;
        } else {
            matchedFrames=Math.min(2,matchedFrames+1);
        }
        lastValidAtMs=elapsedMs;
        interveningUncertain=0;
        if(matchedFrames<2) return false;
        alerted=true;
        summaryHidden=false;
        restorationPending=false;
        restoreFrames=0;
        return true;
    }

    /** OCR parcial, oclusão, guarda financeira ou tela ambígua. */
    public synchronized void uncertain() {
        absentFrames=0;
        if(!alerted && matchedFrames>0) {
            interveningUncertain++;
            if(interveningUncertain>=2) {
                matchedFrames=0;
                fingerprint="";
                lastValidAtMs=-1;
                interveningUncertain=0;
            }
        }
        if(alerted) {
            summaryHidden=true;
            restorationPending=false;
            restoreFrames=0;
        }
    }

    /**
     * A UI pode restaurar o resumo sem disparar novo alerta nem incrementar
     * contador de ofertas; consume uma vez o sinal de restauração.
     */
    public synchronized boolean consumeRestoredSummary() {
        if(!restorationPending) return false;
        restorationPending=false;
        return true;
    }

    /**
     * Quadro definitivamente sem oferta ativa (mapa/post/histórico).
     * true somente ao encerrar um episódio no segundo quadro seguro.
     */
    public synchronized boolean nonOffer() {
        absentFrames=Math.min(2,absentFrames+1);
        if(absentFrames<2) {
            if(!alerted) {
                matchedFrames=0;
                lastValidAtMs=-1;
                interveningUncertain=0;
            }
            return false;
        }
        boolean closed=alerted || !fingerprint.isEmpty();
        fingerprint="";
        matchedFrames=0;
        interveningUncertain=0;
        lastValidAtMs=-1;
        alerted=false;
        summaryHidden=false;
        restoreFrames=0;
        restorationPending=false;
        return closed;
    }

    public synchronized void reset() {
        fingerprint="";
        matchedFrames=0;
        interveningUncertain=0;
        lastValidAtMs=-1;
        absentFrames=0;
        alerted=false;
        summaryHidden=false;
        restoreFrames=0;
        restorationPending=false;
    }
}
