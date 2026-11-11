package com.vexo.mlkitlab;

import java.util.concurrent.atomic.AtomicLong;
import org.json.JSONObject;
import org.json.JSONException;

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
    private static final AtomicLong offerCandidates=new AtomicLong();
    private static final AtomicLong contextRejected=new AtomicLong();
    private static final AtomicLong contextUncertain=new AtomicLong();
    private static final AtomicLong financeRejected=new AtomicLong();
    private static final AtomicLong waitingConfirmation=new AtomicLong();
    private static final CaptureLatencyStats latency=new CaptureLatencyStats();

    static synchronized void begin() {
        frames.set(0);
        ocrStarted.set(0);
        ocrRuns.set(0);
        ocrFailures.set(0);
        visibility="não informada";
        alertCount.set(0);
        offerCandidates.set(0);
        contextRejected.set(0);
        contextUncertain.set(0);
        financeRejected.set(0);
        waitingConfirmation.set(0);
        latency.reset();
        lastCandidate="";
        status="Capturando tela com autorização. Aguardando oferta confiável.";
        active=true;
    }

    static void frameReceived() {
        if(active) frames.incrementAndGet();
    }

    static void ocrLatency(long milliseconds) {
        if(active) latency.record(milliseconds);
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

    static void classifiedOffer() {
        if(active) offerCandidates.incrementAndGet();
    }
    static void rejectedContext(boolean uncertain) {
        if(!active) return;
        if(uncertain) contextUncertain.incrementAndGet();
        else contextRejected.incrementAndGet();
    }
    static void rejectedFinance() {
        if(active) financeRejected.incrementAndGet();
    }
    static void awaitingConfirmation() {
        if(active) waitingConfirmation.incrementAndGet();
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

    // Após a estabilidade voltar, revelar o MESMO resumo sem criar um novo alerta.
    static synchronized void restoreCandidate(String summary) {
        if(!active) return;
        lastCandidate=summary==null?"":summary;
        status="Mesma oferta confirmada novamente; sem novo aviso.";
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

    public static long[] ocrLatencyStats() { return latency.snapshot(); }

    public static long[] stageCounts() {
        return new long[]{offerCandidates.get(),contextUncertain.get(),
            contextRejected.get(),financeRejected.get(),waitingConfirmation.get()};
    }

    public static String captureVisibility() { return visibility; }

    public static synchronized String snapshot() {
        return (active?"CAPTURA ATIVA: ":"SEM CAPTURA: ")+status+
            "\nFrames: "+frames.get()+" • OCR iniciado: "+ocrStarted.get()+
            " • OCR concluído: "+ocrRuns.get()+
            " • erros OCR: "+ocrFailures.get()+
            " • avisos: "+alertCount.get()+
            " • contextos de oferta: "+offerCandidates.get()+
            " • leituras incertas: "+contextUncertain.get()+
            " • guardas financeiras: "+financeRejected.get()+
            " • OCR p95: "+latency.snapshot()[4]+" ms"+
            " • janela: "+visibility+
            (active && !lastCandidate.isEmpty()?"\n"+lastCandidate:"");
    }

    /**
     * Diagnóstico para o usuário copiar e compartilhar voluntariamente.
     * Não exporta o conteúdo da tela, o último candidato, OCR bruto,
     * trajetos, dados pessoais nem o token de MediaProjection.
     */
    public static synchronized String safeDiagnosticReport() {
        long[] n=counts();
        String stage=CaptureHealthAnalyzer.stage(
            n[0],n[3],n[1],n[4],n[2],active);
        try {
            JSONObject report=new JSONObject();
            report.put("schema","vexo-live-capture-diagnostic-v1");
            report.put("app","Vexo Captura 0.4 experimental");
            report.put("status",active?"CAPTURE_ACTIVE":"CAPTURE_STOPPED");
            report.put("diagnosticStage",stage);
            report.put("diagnosticExplanation",CaptureHealthAnalyzer.explanation(stage));
            report.put("framesReceived",n[0]);
            report.put("ocrAttempts",n[3]);
            report.put("ocrCompleted",n[1]);
            report.put("ocrFailures",n[4]);
            report.put("offersAlerted",n[2]);
            long[] timing=latency.snapshot();
            report.put("ocrLatencySamples",timing[0]);
            report.put("ocrLatencyLastMs",timing[1]);
            report.put("ocrLatencyMeanMs",timing[2]);
            report.put("ocrLatencyP50Ms",timing[3]);
            report.put("ocrLatencyP95Ms",timing[4]);
            report.put("ocrLatencyMaxMs",timing[5]);
            report.put("offerContextCandidates",offerCandidates.get());
            report.put("screenContextUncertain",contextUncertain.get());
            report.put("screenContextRejected",contextRejected.get());
            report.put("financiallyUnconfirmedFrames",financeRejected.get());
            report.put("awaitingTwoStableReadings",waitingConfirmation.get());
            report.put("capturedWindowVisibility",visibility);
            report.put("noFieldAccuracyMeasured",true);
            report.put("containsScreenshotOrOcrText",false);
            report.put("privacyNote",
                "Contadores da sessao, sem imagens, texto OCR, enderecos ou identificadores.");
            return report.toString(2);
        } catch(JSONException ex) {
            // Um erro de serialização nunca deve expor o texto reconhecido.
            return "{\"schema\":\"vexo-live-capture-diagnostic-v1\",\"error\":\"REPORT_ENCODING\"}";
        }
    }


}
