package com.vexo.mlkitlab;

/**
 * Diagnóstico sem conteúdo privado. Interpreta contadores do pipeline;
 * NUNCA declara precisão OCR, compatibilidade com 99 ou sucesso financeiro.
 */
public final class CaptureHealthAnalyzer {
    private CaptureHealthAnalyzer() {}

    public static String stage(long frames,long attempted,long completed,
                               long errors,long alerts,boolean active) {
        if(frames==0) return active?"WAITING_FOR_FRAMES":"NO_FRAMES_RECORDED";
        if(attempted==0) return "FRAMES_WITHOUT_OCR_START";
        if(completed==0) return errors>0?"OCR_FAILED":"OCR_NOT_COMPLETED";
        if(alerts==0) return "OCR_OK_NO_CONFIRMED_OFFER";
        return "OFFER_ALERT_GENERATED";
    }

    public static String explanation(String stage) {
        switch(stage) {
            case "WAITING_FOR_FRAMES":
                return "Sessao ativa, mas ainda sem frame confirmado.";
            case "NO_FRAMES_RECORDED":
                return "Nenhuma imagem chegou ao leitor nesta sessao.";
            case "FRAMES_WITHOUT_OCR_START":
                return "Imagens chegaram, mas o reconhecimento nao iniciou.";
            case "OCR_FAILED":
                return "OCR iniciou e registrou falhas; nenhuma leitura concluida.";
            case "OCR_NOT_COMPLETED":
                return "OCR foi iniciado, mas nenhuma leitura concluiu; conferir latencia e encerramento.";
            case "OCR_OK_NO_CONFIRMED_OFFER":
                return "OCR concluiu, mas nenhuma oferta foi confirmada pelo filtro de seguranca.";
            case "OFFER_ALERT_GENERATED":
                return "O aplicativo gerou ao menos um aviso. Isto nao comprova acerto dos numeros.";
            default:
                return "Diagnostico indeterminado.";
        }
    }
}
