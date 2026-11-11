package com.vexo.mlkitlab;

import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Identifica contexto da TELA antes de tratar qualquer numero como oferta.
 * Nao e um classificador treinado nem substitui validacao por pixels/usuario.
 *
 * Motivacao: segundo pacote da 99 inclui telas de viagens concluidas,
 * mapa de zonas dinamicas e uma captura antiga de oferta dentro de outro app.
 * Numeros dessas telas nao sao ofertas ativas, mesmo que parecam R$ e km.
 */
public final class ScreenContextClassifier {
    private ScreenContextClassifier() {}

    public enum Kind {
        OFFER_CANDIDATE,
        COMPLETED_TRIP,
        MAP_WITHOUT_OFFER,
        ARCHIVED_OFFER_SCREENSHOT,
        UNCERTAIN;

        public boolean definitelyNotLiveOffer() {
            return this==COMPLETED_TRIP || this==MAP_WITHOUT_OFFER ||
                this==ARCHIVED_OFFER_SCREENSHOT;
        }
    }

    private static String norm(String text) {
        if (text==null) return "";
        String stripped=Normalizer.normalize(text,Normalizer.Form.NFD)
            .replaceAll("\\p{M}+","");
        return stripped.toLowerCase(Locale.ROOT).replace('\u00a0',' ')
            .replaceAll("\\s+"," ").trim();
    }

    private static boolean has(String text,String regex) {
        return Pattern.compile(regex,Pattern.CASE_INSENSITIVE).matcher(text).find();
    }

    private static final Pattern PRICE=Pattern.compile("r\\s*\\$\\s*\\d{1,4}[.,]\\d{2}");
    private static final Pattern DISTANCE=Pattern.compile("\\b\\d{1,4}(?:[.,]\\d{1,3})?\\s*(?:km|m)\\b");
    private static final Pattern MINUTES=Pattern.compile("\\b\\d{1,3}\\s*min\\b");

    public static Kind classify(String raw) {
        String t=norm(raw);
        if(t.isEmpty()) return Kind.UNCERTAIN;

        // Ordem deliberada: tela de historico com foto de oferta embutida
        // nao deve tornar-se oferta atual.
        if (has(t,"selecione uma acao|apagar este registro") &&
            has(t,"detalhes|exportar|escolher|rota"))
            return Kind.ARCHIVED_OFFER_SCREENSHOT;

        if ((t.contains("detalhes da corrida") &&
                has(t,"voce ganhou|seus ganhos|pago pelo passageiro")) ||
            (t.contains("detalhes da viagem") &&
                has(t,"duracao|valor recebido|preco antecipado")))
            return Kind.COMPLETED_TRIP;

        if (has(t,"proxima viagem|voce esta online") &&
            !has(t,"\\baceitar\\b|\\bescolher\\b") &&
            !has(t,"\\b\\d+\\s*min\\b"))
            return Kind.MAP_WITHOUT_OFFER;

        Matcher d=DISTANCE.matcher(t);
        int distances=0;
        while(d.find()) distances++;
        Matcher m=MINUTES.matcher(t);
        int minutes=0;
        while(m.find()) minutes++;
        boolean modality=has(t,"\\b(?:99|moto|negocia|prioritario|solicitacoes|pgto|entrega)\\b");
        boolean action=has(t,"\\baceitar\\b|\\bescolher\\b");
        boolean price=PRICE.matcher(t).find();

        // Ambas as etapas de rota e preco sao necessarios para reconhecer
        // candidato; nao forca classificacao de tela parcialmente visivel.
        if(price && modality && action && distances>=2 && minutes>=2)
            return Kind.OFFER_CANDIDATE;

        return Kind.UNCERTAIN;
    }
}
