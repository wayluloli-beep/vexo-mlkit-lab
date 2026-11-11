package com.vexo.mlkitlab;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Regras locais para interpretar texto OCR. Não é um modelo de ML treinado.
 * Valores duvidosos ficam vazios para conferência, sem 'autocorreção' silenciosa.
 */
public final class OfferParser {
    private OfferParser() {}

    public static final String[] KEYS = {
        "platform", "offerType", "offerPrice", "payment", "perKm",
        "pickupMin", "pickupKm", "tripMin", "tripKm",
        "rating", "rides", "surge", "negotiations"
    };
    public static final String[] LABELS = {
        "Plataforma", "Tipo de oferta", "Valor principal (R$)", "Pagamento",
        "R$/km exibido pela plataforma", "Busca: tempo (min)", "Busca: distância (km)",
        "Viagem: tempo (min)", "Viagem: distância (km)",
        "Nota do passageiro", "Corridas do passageiro", "Multiplicador", "Contrapropostas (R$; separadas por ;)"
    };

    public static class Offer {
        private final LinkedHashMap<String,String> values = new LinkedHashMap<>();
        public Offer() { for (String key : KEYS) values.put(key, ""); }
        public String get(String key) { return values.get(key); }
        public void set(String key, String val) {
            if (values.containsKey(key)) values.put(key, val == null ? "" : val.trim());
        }
        public LinkedHashMap<String,String> fields() { return new LinkedHashMap<>(values); }
        public int filled() {
            int n = 0; for (String key : KEYS) if (!get(key).isEmpty()) n++;
            return n;
        }
    }

    private static Pattern p(String regex) {
        return Pattern.compile(regex, Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE | Pattern.DOTALL);
    }
    private static String first(String text, String regex) {
        Matcher m = p(regex).matcher(text);
        return m.find() ? m.group(1) : "";
    }
    private static String cleanNumber(String s) {
        return s == null ? "" : s.trim().replace(".", ",");
    }
    public static double decimal(String s) {
        try {
            String v = s == null ? "" : s.trim().replace("R$", "").replace(" ", "").replace(",", ".");
            return Double.parseDouble(v);
        } catch (Exception e) { return Double.NaN; }
    }
    private static String kmFrom(String n, String unit) {
        double x = decimal(n);
        if (Double.isNaN(x)) return "";
        if (unit.equalsIgnoreCase("m")) x /= 1000d;
        if (x < 0 || x > 1500) return "";
        return String.format(Locale.forLanguageTag("pt-BR"), "%.3f", x)
            .replaceAll("0+$", "").replaceAll(",$", "");
    }

    public static Offer parse(String raw) {
        Offer out = new Offer();
        if (raw == null || raw.trim().isEmpty()) return out;
        String s = raw.replace('\u00a0',' ').replace('＄','$')
                      .replace('−','-').replace('–','-');
        boolean negotiate = p("\\bNegocia\\b|Aceitar\\s+por|Pre[cç]o\\s*x").matcher(s).find();
        boolean is99 = p("(?<!\\d)99(?!\\d)|\\bNegocia\\b|Perfil\\s+Premium").matcher(s).find();
        boolean isUber = p("\\bUber\\b|UberX|Comfort\\b").matcher(s).find();
        out.set("platform", is99 ? "99" : (isUber ? "Uber" : ""));
        out.set("offerType", negotiate ? "99 Negocia" : (is99 ? "99 padrão" : ""));
        if (p("Pagamento\\s+no\\s+app").matcher(s).find()) out.set("payment","No aplicativo");

        // Anchor price to the 99's payment label; never choose the biggest amount.
        String main = first(s, "Pagamento\\s+no\\s+app[\\s\\S]{0,180}?R\\$\\s*(\\d{1,4}[.,]\\d{2})(?!\\s*/\\s*km)");
        if (main.isEmpty()) {
            main = first(s, "Aceitar\\s+por\\s*(?:R\\$\\s*)?(\\d{1,4}[.,]\\d{2})");
        }
        if (main.isEmpty()) {
            // Ambiguous texts must be confirmed manually, not guessed from R$/km.
            out.set("offerPrice", "");
        } else {
            out.set("offerPrice", cleanNumber(main));
        }

        String perKm = first(s, "R\\$\\s*(\\d{1,3}[.,]\\d{2})\\s*/\\s*km\\b");
        out.set("perKm", cleanNumber(perKm));

        // Parenthesized distances are offer-card fields; isolated "350 m" is navigation.
        Matcher trips = p("(\\d{1,3})\\s*min\\s*\\(\\s*(\\d{1,4}(?:[.,]\\d{1,3})?)\\s*(km|m)\\s*\\)").matcher(s);
        ArrayList<String[]> legs = new ArrayList<>();
        while (trips.find()) {
            String distance = kmFrom(trips.group(2), trips.group(3));
            if (!distance.isEmpty() && legs.size() < 3)
                legs.add(new String[]{trips.group(1), distance});
        }
        if (legs.size() >= 1) {
            out.set("pickupMin", legs.get(0)[0]);
            out.set("pickupKm", legs.get(0)[1]);
        }
        if (legs.size() >= 2) {
            out.set("tripMin", legs.get(1)[0]);
            out.set("tripKm", legs.get(1)[1]);
        }

        Matcher rider = p("([3-5][.,]\\d{2})\\s*[-·•.]?\\s*(\\d{1,5})\\s*corridas").matcher(s);
        if (rider.find()) {
            out.set("rating", cleanNumber(rider.group(1)));
            out.set("rides", rider.group(2));
        }
        out.set("surge", cleanNumber(first(s, "Pre[cç]o\\s*x\\s*(\\d+(?:[.,]\\d+)?)")));

        // Negotiation suggestions: price-like tokens greater than the original offer.
        // Excludes the base price, rate/km, passenger rating, and overlay readings.
        double base = decimal(out.get("offerPrice"));
        if (negotiate && !Double.isNaN(base) && base > 0) {
            LinkedHashSet<String> suggestions = new LinkedHashSet<>();
            Matcher prices = p("(?<![\\d])(?:R\\$\\s*)?(\\d{1,4}[.,]\\d{2})(?![\\d])").matcher(s);
            while (prices.find()) {
                double value = decimal(prices.group(1));
                int end = prices.end();
                String after = s.substring(end, Math.min(s.length(), end + 5)).replaceAll("\\s+", "");
                if (after.startsWith("/km")) continue;
                if (value > base * 1.01 && value <= base * 1.35) {
                    suggestions.add(cleanNumber(prices.group(1)));
                }
            }
            out.set("negotiations", String.join("; ", suggestions));
        }
        return out;
    }
}