package com.vexo.mlkitlab;

/**
 * Estado somente na memória do PROCESSO. NUNCA usa persistência,
 * arquivos, rede ou OCR bruto, nem retém token da tela.
 */
public final class LiveCaptureState {
    private LiveCaptureState() {}
    private static volatile boolean active=false;
    private static volatile String status="Nenhuma captura ativa.";
    private static volatile String lastCandidate="";

    static void begin() {
        lastCandidate="";
        status="Capturando tela com autorização. Aguardando oferta confiável.";
        active=true;
    }

    static void candidate(String summary) {
        if(!active) return;
        lastCandidate=summary==null?"":summary;
        status="Possível oferta reconhecida. Confira os dados.";
    }

    static void end(String reason) {
        active=false;
        lastCandidate="";
        status=reason==null?"Sessão encerrada.":reason;
    }

    public static String snapshot() {
        return (active?"CAPTURA ATIVA: ":"SEM CAPTURA: ")+status+
            (active && !lastCandidate.isEmpty()?"\n"+lastCandidate:"");
    }
}
