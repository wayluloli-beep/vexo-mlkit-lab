package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import java.text.Normalizer;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The entire Vexo customer-facing contract: fare, pickup min/km, trip min/km,
 * passenger rating. Only ML Kit data attached to one visual card is accepted.
 * Never returns addresses, names, buttons, snapshots, FPS or mock telemetry.
 * It does NOT establish that the app underneath is the live 99 application.
 */
final class OfferMetricFields {
    private static final Pattern PRICE=Pattern.compile("(?i)r\\s*\\$\\s*(\\d{1,6}[.,]\\d{2})");
    private static final Pattern ROUTE=Pattern.compile(
        "(?i)\\b(\\d{1,3})\\s*min\\b.{0,35}?(\\d{1,4}(?:[.,]\\d+)?)\\s*km\\b");
    private static final Pattern RATING=Pattern.compile(
        "(?<!\\d)([0-4][.,]\\d{1,2}|5[.,]0{1,2})(?!\\d)");

    final String price,pickupMinutes,pickupKm,tripMinutes,tripKm,passengerRating;
    private OfferMetricFields(String price,String pickupMinutes,String pickupKm,
                              String tripMinutes,String tripKm,String passengerRating) {
        this.price=price;this.pickupMinutes=pickupMinutes;this.pickupKm=pickupKm;
        this.tripMinutes=tripMinutes;this.tripKm=tripKm;
        this.passengerRating=passengerRating;
    }

    static OfferMetricFields fromLines(List<AutoCardOcrLocator.Line> lines,
                                      AutoCardOcrLocator.Result card) {
        if(lines==null || card==null) return null;
        String price=null,pickupMinutes=null,pickupKm=null,tripMinutes=null,tripKm=null,rating=null;
        int priceDistance=Integer.MAX_VALUE;
        int pickupDistance=Integer.MAX_VALUE;
        int tripDistance=Integer.MAX_VALUE;
        for(AutoCardOcrLocator.Line line:lines) {
            if(line==null || line.rect==null)continue;
            String s=normalize(line.text);
            Matcher money=PRICE.matcher(s);
            if(money.find()) {
                int d=centerDistance(line.rect,card.price);
                if(d<priceDistance && d<=Math.max(85,card.price.width+card.price.height)) {
                    price="R$ "+pt(money.group(1));priceDistance=d;
                }
            }
            Matcher route=ROUTE.matcher(s);
            if(route.find()) {
                int ds=centerDistance(line.rect,card.origin);
                int dt=centerDistance(line.rect,card.destination);
                String m=route.group(1),km=pt(route.group(2));
                if(ds<=dt && ds<pickupDistance &&
                        ds<=Math.max(85,card.origin.width+card.origin.height)) {
                    pickupMinutes=m;pickupKm=km;pickupDistance=ds;
                } else if(dt<ds && dt<tripDistance &&
                        dt<=Math.max(85,card.destination.width+card.destination.height)) {
                    tripMinutes=m;tripKm=km;tripDistance=dt;
                }
            }
            if((s.contains("corridas")||s.contains("perfil premium")||
                s.contains("passageiro")) &&
                line.rect.y>=card.card.y && line.rect.y<
                    card.origin.y+card.origin.height) {
                Matcher found=RATING.matcher(s);
                if(found.find())rating=pt(found.group(1));
            }
        }
        // Never show a "confirmed" fare if route fields are missing.
        if(price==null || pickupMinutes==null || pickupKm==null ||
           tripMinutes==null || tripKm==null) return null;
        // Rating may be unreadable and is shown explicitly as unknown.
        return new OfferMetricFields(price,pickupMinutes,pickupKm,tripMinutes,tripKm,rating);
    }

    String display() {
        return price+"    ★ "+(passengerRating==null?"—":passengerRating)+"\n"+
            "Até passageiro: "+pickupMinutes+" min · "+pickupKm+" km\n"+
            "Viagem: "+tripMinutes+" min · "+tripKm+" km";
    }

    private static String pt(String number) {return number.replace('.',',');}

    private static int centerDistance(Box a,Box b) {
        int dy=(a.y+a.height/2)-(b.y+b.height/2);
        int dx=(a.x+a.width/2)-(b.x+b.width/2);
        return Math.abs(dx)+Math.abs(dy);
    }

    private static String normalize(String s) {
        return Normalizer.normalize(s==null?"":s,Normalizer.Form.NFKD)
            .replaceAll("\\p{M}+","").toLowerCase(Locale.ROOT).trim();
    }
}
