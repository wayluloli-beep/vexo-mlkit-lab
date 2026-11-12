package com.vexo.reader;

import java.util.Locale;

public final class OfferRecord {
    public final int priceCents, originMin, originTenthsKm, destinationMin, destinationTenthsKm;
    public final String origin, destination, rating;
    public final long seenAt;
    public long databaseId;

    public OfferRecord(int priceCents, int originMin, int originTenthsKm,
                       int destinationMin, int destinationTenthsKm, String origin,
                       String destination, String rating, long seenAt) {
        this.priceCents = priceCents;
        this.originMin = originMin;
        this.originTenthsKm = originTenthsKm;
        this.destinationMin = destinationMin;
        this.destinationTenthsKm = destinationTenthsKm;
        this.origin = origin == null ? "" : origin.trim();
        this.destination = destination == null ? "" : destination.trim();
        this.rating = rating == null ? "" : rating.trim();
        this.seenAt = seenAt;
    }

    public boolean hasMinimumFields() {
        return priceCents >= 200 && priceCents <= 200000 &&
            originMin > 0 && originMin <= 240 &&
            destinationMin > 0 && destinationMin <= 480 &&
            originTenthsKm > 0 && originTenthsKm <= 2500 &&
            destinationTenthsKm > 0 && destinationTenthsKm <= 5000;
    }

    public String fingerprint() {
        return priceCents + "|" + originMin + "|" + originTenthsKm + "|" +
            destinationMin + "|" + destinationTenthsKm + "|" + origin + "|" + destination;
    }

    public String price() {
        return String.format(Locale.forLanguageTag("pt-BR"), "R$ %,.2f", priceCents / 100.0);
    }

    public static String kilometers(int tenthsKm) {
        return String.format(Locale.forLanguageTag("pt-BR"), "%.1f km", tenthsKm / 10.0);
    }
}
