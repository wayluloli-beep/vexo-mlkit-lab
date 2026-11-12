package com.vexo.reader;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Parses plain ML Kit text. This is a cautious heuristic, not an official 99 integration. */
public final class OfferParser {
    private static final Pattern MONEY = Pattern.compile(
        "(?i)R\\s*\\$\\s*([0-9]{1,4}(?:\\.[0-9]{3})*,[0-9]{2}|[0-9]{1,4}[.,][0-9]{2})");
    private static final Pattern LEG = Pattern.compile(
        "(?i)(\\d{1,3})\\s*min\\s*\\(?\\s*(\\d{1,4}(?:[.,]\\d{1,2})?)\\s*km\\s*\\)?");
    private static final Pattern RATING = Pattern.compile(
        "(?i)(?:nota|avalia(?:ç|c)[aã]o|⭐|★)\\s*[:\\s]*([0-5][.,]\\d{1,2})");
    private OfferParser() { }

    public static OfferRecord parse(String input, long now) {
        String text = input == null ? "" : input.replace('\r', '\n');
        int price = 0;
        // If there is an accept button, its price wins; otherwise avoid hourly rates.
        Matcher accept = Pattern.compile("(?i)aceitar\\s+por\\s+R\\s*\\$\\s*([\\d.,]+)").matcher(text);
        if (accept.find()) price = parseMoney(accept.group(1));
        if (price == 0) {
            Matcher m = MONEY.matcher(text);
            while (m.find()) {
                String suffix = text.substring(m.end(), Math.min(text.length(), m.end() + 9));
                if (suffix.matches("(?is)^\\s*/\\s*(?:hora|h).*")) continue;
                price = parseMoney(m.group(1));
                if (price > 0) break;
            }
        }
        Matcher m = LEG.matcher(text);
        int om = 0, ok = 0, dm = 0, dk = 0;
        String origin = "", destination = "";
        if (m.find()) {
            om = safeInt(m.group(1));
            ok = parseKmTenths(m.group(2));
            origin = addressAfter(text, m.end());
            if (m.find()) {
                dm = safeInt(m.group(1));
                dk = parseKmTenths(m.group(2));
                destination = addressAfter(text, m.end());
            }
        }
        Matcher rating = RATING.matcher(text);
        String score = rating.find() ? rating.group(1).replace('.', ',') : "";
        return new OfferRecord(price, om, ok, dm, dk, origin, destination, score, now);
    }

    private static String addressAfter(String text, int afterLeg) {
        int newline = text.indexOf('\n', afterLeg);
        if (newline < 0) return "";
        String[] lines = text.substring(newline + 1).split("\\n", 5);
        for (String s : lines) {
            String line = s.trim();
            if (line.isEmpty() || line.startsWith("R$") ||
                line.toLowerCase().contains("aceitar") ||
                line.toLowerCase().contains("corridas") ||
                line.matches("(?i)^\\d+\\s*min.*") ||
                line.toLowerCase().contains("taxa99")) return "";
            return line.length() > 140 ? line.substring(0, 140) : line;
        }
        return "";
    }

    static int parseMoney(String value) {
        if (value == null) return 0;
        String s = value.replace(" ", "").replace(".", "").replace(',', '.');
        try { return Math.round(Float.parseFloat(s) * 100f); }
        catch (NumberFormatException e) { return 0; }
    }

    static int parseKmTenths(String value) {
        if (value == null) return 0;
        try { return Math.round(Float.parseFloat(value.replace(',', '.')) * 10f); }
        catch (NumberFormatException e) { return 0; }
    }

    private static int safeInt(String s) {
        try { return Integer.parseInt(s); }
        catch (NumberFormatException e) { return 0; }
    }
}
