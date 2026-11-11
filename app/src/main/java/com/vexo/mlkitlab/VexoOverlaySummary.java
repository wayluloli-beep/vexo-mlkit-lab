package com.vexo.mlkitlab;

/**
 * Formatação fail-closed: a janela exibe APENAS preço, km e minutos
 * validados sintaticamente, nunca texto livre do OCR.
 */
public final class VexoOverlaySummary {
    private VexoOverlaySummary() {}

    public static String format(String price,String tripKm,String tripMin) {
        if(price==null || !price.matches("\\d{1,4}[.,]\\d{2}") ||
            tripKm==null || !tripKm.matches("\\d{1,4}(?:[.,]\\d{1,3})?") ||
            tripMin==null || !tripMin.matches("\\d{1,3}")) {
            return "Confira a oferta no aplicativo";
        }
        return "R$ "+price+"  •  "+tripKm+" km / "+tripMin+
            " min\nConfira antes de decidir";
    }
}
