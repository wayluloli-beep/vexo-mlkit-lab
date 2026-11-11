package com.vexo.mlkitlab;

import java.text.Normalizer;
import java.util.Locale;

/**
 * Compara modalidades, não fragmentos de palavras.
 *
 * Regra financeira: Entrega Moto, Moto Negocia e Moto são classes diferentes.
 * Permitimos apenas aliases de grafia explicitamente conhecidos.
 */
public final class OfferTypeComparator {
    private OfferTypeComparator() {}

    static String canonical(String value) {
        if (value==null) return "";
        String normalized=Normalizer.normalize(value,Normalizer.Form.NFD)
            .replaceAll("\\p{M}+","")
            .toLowerCase(Locale.ROOT)
            .replaceAll("\\s+"," ")
            .trim()
            .replaceFirst("^99\\s+","");
        if (normalized.equals("entrega moto nova") ||
            normalized.equals("moto entrega") ||
            normalized.equals("moto entrega nova"))
            return "entrega moto";
        if (normalized.equals("negocia nova")) return "negocia";
        if (normalized.equals("pgto. no app") ||
            normalized.equals("pgto no app") ||
            normalized.equals("pagamento no app") ||
            normalized.equals("pagamento no aplicativo") ||
            normalized.equals("pgto. no aplicativo"))
            return "pagamento no app";
        if (normalized.equals("padrao")) return "padrao";
        return normalized;
    }

    public static boolean equivalent(String expected, String actual) {
        String e=canonical(expected),a=canonical(actual);
        return !e.isEmpty() && e.equals(a);
    }
}
