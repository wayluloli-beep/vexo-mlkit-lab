package com.vexo.mlkitlab;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Trava conservadora: não calcular rentabilidade sobre OCR incompleto ou suspeito. */
public final class FinancialGuard {
    private FinancialGuard() {}

    public static final class Assessment {
        public final boolean canCalculate;
        public final String message;
        public final List<String> reasons;
        Assessment(boolean canCalculate, List<String> reasons) {
            this.canCalculate=canCalculate;
            this.reasons=new ArrayList<>(reasons);
            this.message=canCalculate
                ? "Dados básicos presentes. Ainda confira o print antes de usar os cálculos."
                : "DADOS INSUFICIENTES / SUSPEITOS — não calcular rentabilidade. " +
                  String.join("; ",reasons);
        }
    }

    public static Assessment assess(OfferParser.Offer offer) {
        ArrayList<String> reasons=new ArrayList<>();
        double price=OfferParser.decimal(offer.get("offerPrice"));
        double pickKm=OfferParser.decimal(offer.get("pickupKm"));
        double tripKm=OfferParser.decimal(offer.get("tripKm"));
        double pickMin=OfferParser.decimal(offer.get("pickupMin"));
        double tripMin=OfferParser.decimal(offer.get("tripMin"));

        if (!Double.isFinite(price) || price<=0 || price>10000)
            reasons.add("valor principal não confirmado");
        if (!Double.isFinite(pickKm) || pickKm<0 || pickKm>1000)
            reasons.add("distância até embarque não confirmada");
        if (!Double.isFinite(tripKm) || tripKm<=0 || tripKm>1000)
            reasons.add("distância da corrida não confirmada");
        if (!Double.isFinite(pickMin) || pickMin<0 || pickMin>400)
            reasons.add("tempo de busca não confirmado");
        if (!Double.isFinite(tripMin) || tripMin<=0 || tripMin>400)
            reasons.add("tempo de viagem não confirmado");

        if (Double.isFinite(tripMin) && Double.isFinite(tripKm) && tripMin>0 && tripKm>0) {
            double speed=tripKm*60d/tripMin;
            // Indicador de suspeita, NÃO correção. Congestionamento pode ser real.
            if (tripMin>=12 && speed<7.0)
                reasons.add("velocidade implícita muito baixa; conferir km/min");
            if (speed>135.0)
                reasons.add("velocidade implícita muito alta; conferir km/min");
        }
        if (Double.isFinite(pickMin) && Double.isFinite(tripMin)
            && pickMin+tripMin<=0) reasons.add("tempo total igual a zero");
        if (Double.isFinite(price) && Double.isFinite(pickKm) && Double.isFinite(tripKm)
            && pickKm+tripKm>0) {
            double impliedPerKm=price/(pickKm+tripKm);
            double displayed=OfferParser.decimal(offer.get("perKm"));
            // Avisar em caso de divergência grosseira; a plataforma pode definir km de outro modo.
            if (Double.isFinite(displayed) && displayed>0
                && Math.abs(displayed-impliedPerKm)/Math.max(displayed,0.01)>0.35) {
                reasons.add("R$/km exibido diverge do cálculo pela distância total");
            }
        }
        return new Assessment(reasons.isEmpty(),reasons);
    }
}
