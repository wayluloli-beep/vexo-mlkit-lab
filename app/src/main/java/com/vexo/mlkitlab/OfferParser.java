package com.vexo.mlkitlab;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Interpreta a transcrição do ML Kit sem inventar valores.
 * OCR e parser são etapas distintas: se a transcrição perdeu um dígito,
 * o parser deve sinalizar dúvida, nunca reconstruir esse dígito sozinho.
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
        public void set(String key, String value) {
            if (values.containsKey(key)) values.put(key, value == null ? "" : value.trim());
        }
        public LinkedHashMap<String,String> fields() { return new LinkedHashMap<>(values); }
        public int filled() {
            int count=0;
            for (String key:KEYS) if (!get(key).isEmpty()) count++;
            return count;
        }
    }

    private static final Pattern NORMAL_LEG = p(
        "(\\d{1,3}|[Oo])\\s*min\\s*\\(\\s*(\\d{1,4}(?:[.,]\\d{1,3})?)\\s*(km|m)\\s*\\)"
    );
    // Lista "Solicitações": "(9 min 2,9 km)" sem parênteses ao redor da distância.
    private static final Pattern LIST_LEG = p(
        "\\(\\s*(\\d{1,3}|[Oo])\\s*min\\s*[,:;]?\\s*(\\d{1,4}(?:[.,]\\d{1,3})?)\\s*(km|m)\\s*\\)"
    );

    private static Pattern p(String expr) {
        return Pattern.compile(expr,Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    }
    private static boolean has(String s,String expr) { return p(expr).matcher(s).find(); }
    private static String first(String s,String expr) {
        Matcher m=p(expr).matcher(s);
        return m.find()?m.group(1):"";
    }
    private static String number(String s) {
        return s==null?"":s.trim().replace(".",",");
    }
    public static double decimal(String s) {
        try {
            String value=s==null?"":s.trim().replace("R$","")
                .replace("\u00a0","").replace(" ","").replace(",",".");
            return Double.parseDouble(value);
        } catch (Exception e) { return Double.NaN; }
    }
    private static String km(String n,String unit) {
        double v=decimal(n);
        if (!Double.isFinite(v)) return "";
        if ("m".equalsIgnoreCase(unit)) v/=1000d;
        if (v<0 || v>1500) return "";
        return String.format(Locale.forLanguageTag("pt-BR"),"%.3f",v)
            .replaceAll("0+$","").replaceAll(",$","");
    }

    private static final class Leg {
        final int position;
        final String minutes, distance;
        Leg(int position,String minutes,String distance) {
            this.position=position; this.minutes=minutes; this.distance=distance;
        }
    }

    private static void collectLegs(String s, Pattern pattern, ArrayList<Leg> found) {
        Matcher matcher=pattern.matcher(s);
        while (matcher.find()) {
            String dist=km(matcher.group(2),matcher.group(3));
            if (dist.isEmpty()) continue;
            String min=matcher.group(1).equalsIgnoreCase("O")?"0":matcher.group(1);
            found.add(new Leg(matcher.start(),min,dist));
        }
    }

    private static void parseLegs(String s, Offer out) {
        ArrayList<Leg> legs=new ArrayList<>();
        collectLegs(s,NORMAL_LEG,legs);
        collectLegs(s,LIST_LEG,legs);
        legs.sort(Comparator.comparingInt(leg -> leg.position));
        // Nenhuma correção automática quando o ML Kit perde "1" de "11,8 km".
        // Audit financeiro detecta velocidades estranhas e pede conferência.
        if (!legs.isEmpty()) {
            out.set("pickupMin",legs.get(0).minutes);
            out.set("pickupKm",legs.get(0).distance);
        }
        if (legs.size()>1) {
            out.set("tripMin",legs.get(1).minutes);
            out.set("tripKm",legs.get(1).distance);
        }
    }

    /**
     * Preço principal deve estar ANTES do perfil/corridas e não pode ser R$/km,
     * R$/hora, tarifa adicional ou contraproposta.
     */
    private static String price(String s) {
        String accepting=first(s,
            "\\bAceitar\\s+por\\s*(?:R\\s*\\$\\s*)?(\\d{1,4}[.,]\\d{2})(?!\\s*/\\s*(?:km|hora))");
        if (!accepting.isEmpty()) return number(accepting);

        int profile=s.toLowerCase(Locale.ROOT).indexOf(" corridas");
        String head=profile<0 ? s : s.substring(0,profile);
        if (head.length()>900) head=head.substring(head.length()-900);
        Matcher amounts=p("R\\s*\\$\\s*(\\d{1,4}[.,]\\d{2})(?!\\s*/\\s*(?:km|hora))").matcher(head);
        while (amounts.find()) {
            String tail=head.substring(amounts.end(),Math.min(head.length(),amounts.end()+12))
                .toLowerCase(Locale.ROOT);
            if (tail.matches("^\\s*/\\s*(?:km|h(?:ora)?).*")) continue;
            String before=head.substring(Math.max(0,amounts.start()-32),amounts.start())
                .toLowerCase(Locale.ROOT);
            if (has(before,"(?:tarifa\\s+base|taxa\\s+de\\s+deslocamento|por\\s+espera|por\\s+dirigir)\\s*$"))
                continue;
            double value=decimal(amounts.group(1));
            // Não inferir preço se só uma taxa adicional pequena foi encontrada.
            if (Double.isFinite(value) && value>=3 && value<=10000) return number(amounts.group(1));
        }
        return "";
    }

    public static Offer parse(String raw) {
        Offer out=new Offer();
        if (raw==null || raw.trim().isEmpty()) return out;
        String s=raw.replace('\u00a0',' ').replace('＄','$')
            .replace('−','-').replace('–','-').replace('×','x');

        boolean moto=has(s,"\\bMoto\\b");
        boolean negotiate=has(s,"\\bNegocia\\b");
        boolean priority=has(s,"Priorit[aá]rio");
        boolean inApp=has(s,"\\b(?:Pagamento|Pgto\\.?|Pgto)\\s*no\\s*app\\b|\\bno\\s+aplicativo\\b");
        boolean cash=has(s,"\\bDinheiro\\b");
        // O botão flutuante "Uber" nos prints não significa que a oferta seja Uber.
        boolean is99=has(s,"(?<!\\d)99(?!\\d)|Taxa\\s*99|KM\\s+Garantido\\s*99|Perfil\\s+(?:Premium|Essencial)")
            || moto || negotiate || priority || inApp;
        boolean isUber=has(s,"\\bUber(?:X)?\\b|\\bComfort\\b");
        out.set("platform",is99?"99":isUber?"Uber":"");

        if (moto && negotiate) out.set("offerType","Moto Negocia");
        else if (moto) out.set("offerType","Moto");
        else if (priority) out.set("offerType","Prioritário");
        else if (negotiate) out.set("offerType","99 Negocia");
        else if (inApp) out.set("offerType","Pgto. no app");
        else if (is99) out.set("offerType","99 padrão");

        if (cash) out.set("payment","Dinheiro");
        else if (inApp) out.set("payment","No aplicativo");

        out.set("offerPrice",price(s));
        // O OCR pode omitir "R$" mas preservar "1,28/km". Sem inventar o valor.
        out.set("perKm",number(first(s,
            "(?<![\\d.,])(?:R\\s*\\$\\s*)?(\\d{1,4}[.,]\\d{2})\\s*/\\s*k\\s*m\\b")));
        parseLegs(s,out);

        Matcher rider=p("([0-5][.,]\\d{2})\\s*[-·•.]?\\s*(\\d{1,5})\\s*corridas").matcher(s);
        if (rider.find()) {
            out.set("rating",number(rider.group(1)));
            out.set("rides",rider.group(2));
        }

        // Multiplicador pode ser "Preço x1,5", "⚡2,8x" ou "3,2x".
        out.set("surge",number(first(s,
            "(?<![\\d])([1-9][.,]\\d{1,2})\\s*x\\b")));
        if (out.get("surge").isEmpty()) {
            out.set("surge",number(first(s,"\\bPre[cç]o\\s*x\\s*(\\d+(?:[.,]\\d+)?)")));
        }

        // Sugestões de contraproposta só em ofertas de negociação explícita.
        double base=decimal(out.get("offerPrice"));
        if (negotiate && Double.isFinite(base) && base>0) {
            LinkedHashSet<String> suggestions=new LinkedHashSet<>();
            Matcher money=p("(?<!\\d)(?:R\\s*\\$\\s*)?(\\d{1,4}[.,]\\d{2})(?!\\d)").matcher(s);
            while (money.find()) {
                double n=decimal(money.group(1));
                String after=s.substring(money.end(),Math.min(s.length(),money.end()+6))
                    .replaceAll("\\s+","").toLowerCase(Locale.ROOT);
                if (after.startsWith("/km") || after.startsWith("/hora")) continue;
                if (Double.isFinite(n) && n>base*1.01 && n<=base*1.35) {
                    suggestions.add(number(money.group(1)));
                }
            }
            out.set("negotiations",String.join("; ",suggestions));
        }
        return out;
    }
}
