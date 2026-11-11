package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

/**
 * Casos de OCR em que o símbolo da moeda some, mas o valor/km permanece.
 * Evita associar números do GPS ou do perfil ao rendimento por km.
 */
public class PerKmMissingCurrencyTest {
    @Test public void handlesMissingCurrencySymbolInWhiteCard() {
        OfferParser.Offer offer=OfferParser.parse(
            "Solicitações\nNegocia\nR$11,52 1,28/km\n"
            +"5,00 11 corridas\n(6 min 2,7 km)\n(17 min 6,3 km)\n"
            +"Aceitar por R$11,52");
        assertEquals("11,52",offer.get("offerPrice"));
        assertEquals("1,28",offer.get("perKm"));
    }

    @Test public void acceptsExplicitCurrencyWithSlash() {
        OfferParser.Offer offer=OfferParser.parse(
            "Prioritário R$41,40 2,2x\nR$5,19/km\n"
            +"4,95 665 corridas\n3 min (668 m)\n25 min (7,3 km)");
        assertEquals("5,19",offer.get("perKm"));
    }

    @Test public void doesNotGuessPerKmFromDistanceOrRating() {
        OfferParser.Offer offer=OfferParser.parse(
            "Negocia R$6,15\n4,89 307 corridas\n(9 min 2,9 km)\n(8 min 3,3 km)");
        assertEquals("",offer.get("perKm"));
    }

    @Test public void ambiguityDoesNotAutoConvertIconToMultiplier() {
        OfferParser.Offer offer=OfferParser.parse(
            "Moto R$40,70 42,8x\n4,98 971 corridas\n"
            +"9 min (3 km)\n24 min (1,8 km)");
        assertEquals("",offer.get("surge"));
        assertEquals("1,8",offer.get("tripKm"));
        assertFalse(FinancialGuard.assess(offer).canCalculate);
    }
}
