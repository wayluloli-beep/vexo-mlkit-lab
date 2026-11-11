package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

public class OfferTypeLot02Test {
    @Test public void entregaMotoIsNotMisclassifiedAsPassengerMoto() {
        OfferParser.Offer p=OfferParser.parse(
            "Entrega Moto R$6,80 4,94 Cartao verif. "+
            "7 min (2,8 km) 13 min (6 km) Aceitar");
        assertEquals("Entrega Moto",p.get("offerType"));
        assertEquals("6,80",p.get("offerPrice"));
        assertEquals("2,8",p.get("pickupKm"));
        assertEquals("6",p.get("tripKm"));
        assertTrue(FinancialGuard.assess(p).canCalculate);
    }

    @Test public void regularMotoStillHasItsOriginalType() {
        OfferParser.Offer p=OfferParser.parse(
            "99 Moto R$9,50 4,89 37 corridas 2 min (486 m) "+
            "17 min (12,2 km) Aceitar");
        assertEquals("Moto",p.get("offerType"));
    }
}
