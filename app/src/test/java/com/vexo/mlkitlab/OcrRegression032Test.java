package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

/**
 * Transcrições manuais representativas dos dez prints.
 * Estes testes verificam o parser, NÃO a qualidade do OCR real do ML Kit.
 */
public class OcrRegression032Test {
    private OfferParser.Offer parse(String s) { return OfferParser.parse(s); }

    @Test public void cashNegotiationAndSuggestions() {
        OfferParser.Offer o=parse("Negocia · Dinheiro\nR$21,15\n4,62 • 108 corridas\n"
            +"9 min (2 km)\n26 min (19,2 km)\nAceitar por R$21,15\n"
            +"R$22,21   R$23,27   R$24,32");
        assertEquals("99",o.get("platform"));
        assertEquals("Dinheiro",o.get("payment"));
        assertEquals("21,15",o.get("offerPrice"));
        assertEquals("99 Negocia",o.get("offerType"));
        assertEquals("22,21; 23,27; 24,32",o.get("negotiations"));
    }

    @Test public void motoPriceWithoutAcceptAmount() {
        OfferParser.Offer o=parse("Moto\nR$9,50\n4,89 37 corridas CPF verif.\n"
            +"2 min (486 m)\n17 min (12,2 km)\nAceitar");
        assertEquals("Moto",o.get("offerType"));
        assertEquals("9,50",o.get("offerPrice"));
        assertEquals("0,486",o.get("pickupKm"));
        assertEquals("12,2",o.get("tripKm"));
    }

    @Test public void motoSurgeAndSeparateFee() {
        OfferParser.Offer o=parse("Moto\nR$40,70 ⚡2,8x\n"
            +"0% de Taxa99 semanal\nR$0,96 Tarifa base dinâmica incl.\n"
            +"4,98 971 corridas\n9 min (3 km)\n24 min (11,8 km)");
        assertEquals("Moto",o.get("offerType"));
        assertEquals("40,70",o.get("offerPrice"));
        assertEquals("2,8",o.get("surge"));
        assertEquals("11,8",o.get("tripKm"));
        assertTrue(FinancialGuard.assess(o).canCalculate);
    }

    @Test public void oneLostDigitIsNeverSilentlyFixed() {
        OfferParser.Offer o=parse("Moto R$40,70 2,8x 4,98 971 corridas "
            +"9 min (3 km) 24 min (1,8 km)");
        assertEquals("1,8",o.get("tripKm"));
        FinancialGuard.Assessment assessment=FinancialGuard.assess(o);
        assertFalse(assessment.canCalculate);
        assertTrue(assessment.message.contains("velocidade"));
    }

    @Test public void motoNegociaWithPerHour() {
        OfferParser.Offer o=parse("Moto Negocia\nR$72,32 3,2x\n"
            +"R$118,61/hora\n0% de Taxa99 semanal\n4,73 114 corridas\n"
            +"5 min (1,5 km)\n32 min (20,2 km)\n"
            +"Aceitar por R$72,32 R$75,94 R$79,55 R$83,17");
        assertEquals("Moto Negocia",o.get("offerType"));
        assertEquals("72,32",o.get("offerPrice"));
        assertEquals("3,2",o.get("surge"));
        assertEquals("20,2",o.get("tripKm"));
        assertEquals("75,94; 79,55; 83,17",o.get("negotiations"));
    }

    @Test public void amountAloneBeforeProfile() {
        OfferParser.Offer o=parse("Moto\nR$4,60\nR$1,39 Tarifa base dinâmica incl.\n"
            +"3,00 4 corridas CPF verif.\n2 min (599 m)\n5 min (2,3 km)");
        assertEquals("99",o.get("platform"));
        assertEquals("4,60",o.get("offerPrice"));
        assertEquals("3,00",o.get("rating"));
    }

    @Test public void dynamicNoAutoNegotiate() {
        OfferParser.Offer o=parse("Pgto. no app\nR$29,37 ⚡1,1x\nR$1,80/km\n"
            +"KM Garantido 99 ativo\nR$1,34 por dirigir entre áreas\n"
            +"5,00 26 corridas\n7 min (2 km)\n23 min (14,4 km)");
        assertEquals("No aplicativo",o.get("payment"));
        assertEquals("Pgto. no app",o.get("offerType"));
        assertEquals("29,37",o.get("offerPrice"));
        assertEquals("1,1",o.get("surge"));
        assertEquals("1,80",o.get("perKm"));
        assertEquals("",o.get("negotiations"));
    }

    @Test public void navigation853MetersIsNotPickup() {
        OfferParser.Offer o=parse("853 m\nR. Mal. Deodoro\n"
            +"Prioritário\nR$41,40 2,2x\nR$5,19/km\n0% de Taxa99 semanal\n"
            +"4,95 665 corridas\n3 min (668 m)\n25 min (7,3 km)");
        assertEquals("Prioritário",o.get("offerType"));
        assertEquals("41,40",o.get("offerPrice"));
        assertEquals("2,2",o.get("surge"));
        assertEquals("0,668",o.get("pickupKm"));
        assertEquals("7,3",o.get("tripKm"));
    }

    @Test public void lightListCardLegs() {
        OfferParser.Offer o=parse("Solicitações Corridas Entregas\n"
            +"Negocia R$6,15\n4,89 307 corridas Perfil Essencial\n"
            +"(9 min 2,9 km) Rua João Rosa\n(8 min 3,3 km) Rua Jurupana\n"
            +"Aceitar por R$6,15 R$6,46 R$6,64 R$6,77");
        assertEquals("9",o.get("pickupMin"));
        assertEquals("2,9",o.get("pickupKm"));
        assertEquals("8",o.get("tripMin"));
        assertEquals("3,3",o.get("tripKm"));
    }

    @Test public void lightListCardKmRate() {
        OfferParser.Offer o=parse("Solicitações\nNegocia R$11,52 ↑ R$1,28/km\n"
            +"5,00 11 corridas\n(6 min 2,7 km) Rua Itumbiara\n"
            +"(17 min 6,3 km) Rua Waldemar\nAceitar por R$11,52\n"
            +"R$12,10 R$12,44 R$12,67");
        assertEquals("1,28",o.get("perKm"));
        assertEquals("6",o.get("pickupMin"));
        assertEquals("2,7",o.get("pickupKm"));
        assertEquals("17",o.get("tripMin"));
        assertEquals("6,3",o.get("tripKm"));
    }

    @Test public void incompleteScreenMustNotShowMetrics() {
        OfferParser.Offer o=parse("99 Moto R$9,50\n4,89 37 corridas");
        assertFalse(FinancialGuard.assess(o).canCalculate);
        assertTrue(FinancialGuard.assess(o).message.contains("DADOS INSUFICIENTES"));
    }

    @Test public void missingPriceCannotBeSubstitutedByFee() {
        OfferParser.Offer o=parse("Moto\nR$1,39 Tarifa base dinâmica incl.\n"
            +"3,00 4 corridas\n2 min (599 m)\n5 min (2,3 km)");
        assertEquals("",o.get("offerPrice"));
        assertFalse(FinancialGuard.assess(o).canCalculate);
    }
}
