package com.vexo.mlkitlab;

import java.util.Locale;

/**
 * Dados de uma oferta financeira já confirmada. NUNCA usar texto livre OCR,
 * endereço, origem, destino, telefone, placa ou nome do passageiro na janela.
 * R$/km e R$/h incluem a aproximação até o embarque.
 */
public final class VexoOverlaySummary {
    private VexoOverlaySummary() {}

    public static final class Metrics {
        public final boolean valid;
        public final String perKm, perHour, rating, profit, totalTime, totalKm;
        private Metrics(boolean valid,String perKm,String perHour,String rating,
                String profit,String totalTime,String totalKm) {
            this.valid=valid;
            this.perKm=perKm;this.perHour=perHour;this.rating=rating;
            this.profit=profit;this.totalTime=totalTime;this.totalKm=totalKm;
        }
    }

    private static final Metrics EMPTY=
        new Metrics(false,"—","—","—","—","—","—");

    private static double decimal(String value,String pattern) {
        if(value==null || !value.matches(pattern)) return Double.NaN;
        try { return Double.parseDouble(value.replace(',','.')); }
        catch(NumberFormatException ignored) { return Double.NaN; }
    }

    private static String formatPt(double n) {
        return String.format(Locale.forLanguageTag("pt-BR"),"%.2f",n);
    }

    public static Metrics fromFields(String price,String pickupKm,String tripKm,
            String pickupMin,String tripMin,String rating) {
        double p=decimal(price,"\\d{1,4}[.,]\\d{2}");
        double pk=decimal(pickupKm,"\\d{1,4}(?:[.,]\\d{1,3})?");
        double tk=decimal(tripKm,"\\d{1,4}(?:[.,]\\d{1,3})?");
        double pm=decimal(pickupMin,"\\d{1,3}");
        double tm=decimal(tripMin,"\\d{1,3}");
        double km=pk+tk, minutes=pm+tm;
        if(!Double.isFinite(p)||!Double.isFinite(km)||!Double.isFinite(minutes)
                ||p<=0||km<=0||minutes<=0||p>10000||km>1000||minutes>600) {
            return EMPTY;
        }
        double perKm=p/km, perHour=p*60/minutes;
        if(!Double.isFinite(perKm)||!Double.isFinite(perHour)||
                perKm>10000||perHour>100000) return EMPTY;

        double star=decimal(rating,"[0-5][.,]\\d{2}");
        String ratingLabel=Double.isFinite(star)&&star<=5 ? formatPt(star) : "—";
        long roundedM=Math.round(minutes);
        String time=roundedM>=60
            ? (roundedM/60)+"h"+String.format(Locale.ROOT,"%02d",roundedM%60)+"m"
            : roundedM+"m";
        // Os números da UI são derivados de campos financeiros confirmados.
        // Lucro exige custo por km/combustível e NÃO é inferido de uma oferta.
        return new Metrics(true,formatPt(perKm),formatPt(perHour),ratingLabel,"—",
            time,String.format(Locale.US,"%.1f",km)+"km");
    }

    /** Compatibilidade de apresentação antiga, sem revelar OCR bruto. */
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
