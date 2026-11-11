package com.vexo.mlkitlab;

import java.util.concurrent.atomic.AtomicLong;

/**
 * Estado e contadores SOMENTE em RAM para que o usuário veja se a captura
 * de verdade recebeu frames e executou OCR. Sem screenshots, texto bruto,
 * endereços, tokens, histórico ou comunicação de rede.
 */
public final class LiveCaptureState {
    private LiveCaptureState() {}
    private static volatile boolean active=false;
    private static volatile String status="Nenhuma captura ativa.";
    private static volatile String lastCandidate="";
    private static final AtomicLong frames=new AtomicLong();
    private static final AtomicLong ocrStarted=new AtomicLong();
    private static final AtomicLong ocrRuns=new AtomicLong();
    private static final AtomicLong ocrFailures=new AtomicLong();
    private static volatile String visibility="não informada";
    private static final AtomicLong alertCount=new AtomicLong();

    static synchronized void begin() {
        frames.set(0);
        ocrStarted.set(0);
        ocrRuns.set(0);
        ocrFailures.set(0);
        visibility="não informada";
        alertCount.set(0);
        lastCandidate="";
        status="Capturando tela com autorização. Aguardando oferta confiável.";
        active=true;
    }

    static void frameReceived() {
        if(active) frames.incrementAndGet();
    }

    static void ocrAttempted() {
        if(active) ocrStarted.incrementAndGet();
    }

    static void ocrFailed() {
        if(active) ocrFailures.incrementAndGet();
    }

    static void capturedContentVisibility(boolean visible) {
        if(active) visibility=visible?"visível":"oculto";
    }

    static void ocrCompleted() {
        if(active) ocrRuns.incrementAndGet();
    }

    static synchronized void candidate(String summary) {
        if(!active) return;
        lastCandidate=summary==null?"":summary;
        status="Possível oferta reconhecida. Confira os dados.";
        alertCount.incrementAndGet();
    }

    static synchronized void clearCandidate() {
        if(!active) return;
        lastCandidate="";
        status="Aguardando uma nova oferta confiável.";
    }

    static synchronized void end(String reason) {
        active=false;
        lastCandidate="";
        status=reason==null?"Sessão encerrada.":reason;
    }

    /** Apenas contadores agregados, sem pixels/OCR bruto. */
    public static long[] counts() {
        return new long[]{frames.get(),ocrRuns.get(),alertCount.get(),
            ocrStarted.get(),ocrFailures.get()};
    }

    public static String captureVisibility() { return visibility; }

    public static synchronized String snapshot() {
        return (active?"CAPTURA ATIVA: ":"SEM CAPTURA: ")+status+
            "\nFrames: "+frames.get()+" • OCR iniciado: "+ocrStarted.get()+
            " • OCR concluído: "+ocrRuns.get()+
            " • erros OCR: "+ocrFailures.get()+
            " • avisos: "+alertCount.get()+
            " • janela: "+visibility+
            (active && !lastCandidate.isEmpty()?"\n"+lastCandidate:"");
    }
}
