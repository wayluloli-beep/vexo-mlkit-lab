package com.vexo.mlkitlab;

import org.junit.Test;
import java.util.Locale;
import static org.junit.Assert.*;

/**
 * Matriz determinística de transcrições artificiais: não representa precisão
 * do ML Kit nem testes em imagens da 99. Detecta regressão do parser/guardas.
 */
public class SyntheticOfferMatrixTest {
    @Test public void hundredsOfSyntheticFaresAndRatesArePreserved() {
        for (int i=0;i<320;i++) {
            String fare=String.format(Locale.US,"%d,%02d",3+(i%67),(i*17)%100);
            String rate=String.format(Locale.US,"%d,%02d",1+(i%4),(i*43)%100);
            String display=(i%3==0?"R$":i%3==1?"":"R$ ")+rate+(i%2==0?"/km":" / km");
            String text="99 Negocia Dinheiro\nR$"+fare+"\n"+display+
                "\n4,90 71 corridas\n8 min (3 km)\n23 min (9,4 km)\nAceitar por R$"+fare;
            OfferParser.Offer parsed=OfferParser.parse(text);
            assertEquals("iteration "+i+" fare",fare,parsed.get("offerPrice"));
            assertEquals("iteration "+i+" rate",rate,parsed.get("perKm"));
            assertEquals("iteration "+i+" distance","9,4",parsed.get("tripKm"));
            assertEquals("iteration "+i+" payment","Dinheiro",parsed.get("payment"));
        }
    }

    @Test public void correctedAndCorruptedMultiplierAreNotConfused() {
        OfferParser.Offer good=OfferParser.parse("Moto R$40,70 2,8x 4,98 971 corridas 9 min (3 km) 24 min (11,8 km)");
        OfferParser.Offer broken=OfferParser.parse("Moto R$40,70 42,8x 4,98 971 corridas 9 min (3 km) 24 min (1,8 km)");
        assertEquals("2,8",good.get("surge"));
        assertEquals("",broken.get("surge"));
        assertEquals("1,8",broken.get("tripKm"));
        assertFalse(FinancialGuard.assess(broken).canCalculate);
    }

    @Test public void noFareOrNoTripDistanceNeverGetsRecommendation() {
        OfferParser.Offer missingPrice=OfferParser.parse(
            "99 Moto 4,98 971 corridas 9 min (3 km) 24 min (11,8 km)");
        OfferParser.Offer missingTrip=OfferParser.parse(
            "99 Moto R$40,70 4,98 971 corridas 9 min (3 km)");
        assertFalse(FinancialGuard.assess(missingPrice).canCalculate);
        assertFalse(FinancialGuard.assess(missingTrip).canCalculate);
    }

    @Test public void zeroTripTimeIsNotFinanciallyUsable() {
        OfferParser.Offer offer=new OfferParser.Offer();
        offer.set("offerPrice","30,00");
        offer.set("pickupKm","2");
        offer.set("tripKm","10");
        offer.set("pickupMin","5");
        offer.set("tripMin","0");
        assertFalse("Tempo de viagem zero nao pode gerar lucro/hora",
            FinancialGuard.assess(offer).canCalculate);
    }
}
