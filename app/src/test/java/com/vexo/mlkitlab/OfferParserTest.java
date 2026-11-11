package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

public class OfferParserTest {
    @Test public void shortRideAvoidsGiguOverlay() {
        String ocr="15:40 G. Atélie da Juju\n"
            +"R$/Km\nR$/Hora\n99 0h5m . 1.50km\n|5.13 92.404.94\n"
            +"5min (1,1km)\nPagamento no app\nNota Educação Unificada José...\n"
            +"R$7,70\nR$5,10/km\nTaxa de deslocamento R$1,67\n"
            +"0min (449m)\n4,94 936 corridas Perfil Premium\nGigu";
        OfferParser.Offer a=OfferParser.parse(ocr);
        assertEquals("99",a.get("platform"));
        assertEquals("7,70",a.get("offerPrice"));
        assertEquals("5,10",a.get("perKm"));
        assertEquals("5",a.get("pickupMin"));
        assertEquals("1,1",a.get("pickupKm"));
        assertEquals("0",a.get("tripMin"));
        assertEquals("0,449",a.get("tripKm"));
        assertEquals("4,94",a.get("rating"));
        assertEquals("936",a.get("rides"));
        assertEquals("",a.get("negotiations"));
    }

    @Test public void longRideKeepsNegotiationsSeparate() {
        String ocr="22:18\n350 m\nAv. Domingos Odália Filho\n"
            +"Corrida longa\nNegocia Pagamento no app\nR$43,09\n"
            +"5min (894m)\nR$3,04/km\n45,24\n29min (13,3km)\n"
            +"4,92- 306 corridas Perfil Premium\nPreço x1,5\n"
            +"Aceitar por 43,09\n47,40\n49,55";
        OfferParser.Offer a=OfferParser.parse(ocr);
        assertEquals("99",a.get("platform"));
        assertEquals("99 Negocia",a.get("offerType"));
        assertEquals("43,09",a.get("offerPrice"));
        assertEquals("3,04",a.get("perKm"));
        assertEquals("5",a.get("pickupMin"));
        assertEquals("0,894",a.get("pickupKm"));
        assertEquals("29",a.get("tripMin"));
        assertEquals("13,3",a.get("tripKm"));
        assertEquals("4,92",a.get("rating"));
        assertEquals("306",a.get("rides"));
        assertEquals("1,5",a.get("surge"));
        assertEquals("45,24; 47,40; 49,55",a.get("negotiations"));
    }

    @Test public void missingMainPriceStaysEmpty() {
        OfferParser.Offer a=OfferParser.parse("Gigu R$/Km 5.13 R$/Hora 92.40 R$3,04/km 350 m");
        assertEquals("",a.get("offerPrice"));
    }
}
