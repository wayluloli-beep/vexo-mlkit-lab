package com.vexo.mlkitlab;

import org.junit.Test;
import static org.junit.Assert.*;

/** Textos sinteticos sem enderecos de passageiros. Nao mede ML Kit real. */
public class ScreenContextClassifierTest {
    private static void kind(String transcript, ScreenContextClassifier.Kind expected) {
        assertEquals(expected, ScreenContextClassifier.classify(transcript));
    }

    @Test public void screenOfArchivedOfferIsNotLive() {
        kind("99 Motorista\nR$14,00\nR$21,40\n" +
            "Pop Nova R$29,20 1,9x R$2,42/km 4,95 999 corridas " +
            "5 min (2,2 km) 29 min (9,9 km) Escolher\n" +
            "Selecione uma ação Rota Detalhes Exportar Apagar este registro",
            ScreenContextClassifier.Kind.ARCHIVED_OFFER_SCREENSHOT);
    }

    @Test public void finishedRidePayoutIsNotOffer() {
        kind("Detalhes da corrida Você ganhou R$20,90 " +
            "Duração 26m35s Distância 9,9 km Tipo de corrida Pop " +
            "Seus ganhos R$14,60 Preço dinâmico R$3,20 " +
            "Pago pelo passageiro Total R$30,10",
            ScreenContextClassifier.Kind.COMPLETED_TRIP);
        kind("Detalhes da viagem Preço antecipado R$38,04 " +
            "Duração 18 min 57 segundos Distância 11,88 km " +
            "Valor recebido em dinheiro R$18,09",
            ScreenContextClassifier.Kind.COMPLETED_TRIP);
    }

    @Test public void onlineHeatmapNumbersCannotBecomeOffer() {
        kind("R$154,65 +R$20 +R$13 Próxima viagem +R$21 Você está online",
            ScreenContextClassifier.Kind.MAP_WITHOUT_OFFER);
    }

    @Test public void actualOffersStayCandidateIncludingDeliveryMoto() {
        kind("99 Moto R$40,70 2,8x 4,98 971 corridas " +
            "9 min (3 km) 24 min (11,8 km) Aceitar",
            ScreenContextClassifier.Kind.OFFER_CANDIDATE);
        kind("Entrega Moto R$6,80 4,94 Cartão verif. " +
            "7 min (2,8 km) 13 min (6 km) Aceitar",
            ScreenContextClassifier.Kind.OFFER_CANDIDATE);
        kind("Solicitações 99 Negocia R$11,52 R$1,28/km " +
            "6 min (2,7 km) 17 min (6,3 km) Aceitar por R$11,52",
            ScreenContextClassifier.Kind.OFFER_CANDIDATE);
    }

    @Test public void onlineOverlayMustNotHidePlausibleRealOffer() {
        // OCR perdeu o botão Aceitar e o sufixo "min", mas preservou
        // parte do card de corrida sob a notificação do mapa.
        kind("Você está online Próxima viagem 99 Moto R$28,80 1,3x " +
            "4,98 971 corridas 9 (3 km) 24 (11,8 km)",
            ScreenContextClassifier.Kind.UNCERTAIN);

        // Mesmo sem reconhecer as distâncias, os marcadores de modalidade
        // devem impedir um bloqueio automático irreversível.
        kind("Próxima viagem 99 Negocia R$23,90 " +
            "Perfil Premium Cartão verif.",
            ScreenContextClassifier.Kind.UNCERTAIN);

        // A informação de trajeto sem botão também exige revisão humana.
        kind("Você está online 9 min (3 km) 24 min (11,8 km) R$40,70",
            ScreenContextClassifier.Kind.UNCERTAIN);
    }

    @Test public void fullSocialPostIsNotLiveButAnOverlayAloneIsUncertain() {
        kind("Posts Comentário: alguém publicou imagem. " +
            "Escreva um comentário público. 99 Negocia R$227,86 " +
            "6 min (1,9 km) 86 min (67 km) Aceitar por R$227,86",
            ScreenContextClassifier.Kind.SOCIAL_POST_WITH_SCREENSHOT);

        // Texto sobreposto sem os controles próprios da rede social:
        // não confundir com uma captura de post arquivado.
        kind("99 Moto R$7,90 9 min (5,7 km) 9 min (4,9 km) " +
            "Aceitar Alguém comentou que a viagem está cara",
            ScreenContextClassifier.Kind.OFFER_CANDIDATE);

        // Uma única palavra genérica não justifica bloquear.
        kind("Posts 99 Moto R$28,80 9 min (3 km) 24 min (11,8 km) Aceitar",
            ScreenContextClassifier.Kind.OFFER_CANDIDATE);
    }

    @Test public void ordinaryMapWithSurgeZonesStillIsNotOffer() {
        kind("Você está online Próxima viagem +R$21 +R$13 R$154,65",
            ScreenContextClassifier.Kind.MAP_WITHOUT_OFFER);
        kind("Próxima viagem R$ 154,65 +R$20",
            ScreenContextClassifier.Kind.MAP_WITHOUT_OFFER);
    }

    @Test public void expiredRequestAndAdvertisingNeverBecomeLiveOffers() {
        kind("Solicitação de corrida expirou 99 Negocia R$12,64 " +
            "8 min (2,1 km) 17 min (7,3 km) Aceitar",
            ScreenContextClassifier.Kind.EXPIRED_REQUEST);
        kind("Promoção do mercado R$0,99", ScreenContextClassifier.Kind.PROMOTION);
        kind("99 Negocia R$12,64 8 min (2,1 km) " +
            "17 min (7,3 km) Aceitar",
            ScreenContextClassifier.Kind.OFFER_CANDIDATE);
    }

    @Test public void partialOrUnknownScreenDoesNotBecomeConfirmed() {
        kind("R$29,20 5 min (2,2 km) Pop Nova",ScreenContextClassifier.Kind.UNCERTAIN);
        kind("",ScreenContextClassifier.Kind.UNCERTAIN);
        kind("MAPA +R$20",ScreenContextClassifier.Kind.UNCERTAIN);
    }
}
