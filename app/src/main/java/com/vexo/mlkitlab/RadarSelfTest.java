package com.vexo.mlkitlab;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Diagnostic self-test run by the owner INSIDE the installed APK.
 * Fully fabricated luminance data. Never opens MediaProjection, Gallery,
 * real driver data or OCR; never claims 99 compatibility or precision.
 */
public final class RadarSelfTest {
    private RadarSelfTest() {}

    private interface Check { boolean verify(); }

    private static final class Scene implements FastCardVisualTracker.Pixels {
        final int x,y,w,h,shade;
        Scene(int x,int y,int w,int h,int shade) {
            this.x=x;this.y=y;this.w=w;this.h=h;this.shade=shade;
        }
        @Override public int width(){return 400;}
        @Override public int height(){return 700;}
        @Override public int luminance(int px,int py) {
            return px>=x && px<x+w && py>=y && py<y+h ? shade : 80;
        }
    }

    private static final class Textured implements FastCardVisualTracker.Pixels {
        final int x,y; final boolean showing;
        Textured(int x,int y,boolean showing) {
            this.x=x;this.y=y;this.showing=showing;
        }
        @Override public int width(){return 400;}
        @Override public int height(){return 700;}
        @Override public int luminance(int px,int py) {
            if(!showing || px<x || py<y || px>=x+140 || py>=y+110) return 80;
            int xx=px-x,yy=py-y;
            return (xx*31+yy*17+(xx/5)*(yy/7)*13)&255;
        }
    }

    public static final class Report {
        public final int passed, total;
        public final String display, json;
        Report(int passed,int total,String display,String json) {
            this.passed=passed;this.total=total;
            this.display=display;this.json=json;
        }
    }

    private static final class Runner {
        final JSONArray checks=new JSONArray();
        final StringBuilder display=new StringBuilder();
        int total, passed;
        void check(String key,Check test) {
            boolean ok=false;
            try {ok=test.verify();} catch(RuntimeException ignored) {ok=false;}
            total++;
            if(ok)passed++;
            try {
                JSONObject result=new JSONObject();
                result.put("name",key);
                result.put("result",ok?"PASS":"FAIL");
                checks.put(result);
            } catch(Exception ignored) {}
            display.append(ok?"✓ ":"✗ ").append(key).append("\n");
        }
    }

    public static Report run() {
        Runner r=new Runner();
        r.check("detector encontra card sem posição fixa",() -> {
            AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
            boolean baseline=d.armOnVerifiedNonOffer(new Scene(0,0,0,0,80));
            AdaptiveCardRegionDetector.Result a=d.inspect(
                new Scene(100,220,170,100,230),33);
            return baseline && a.suspiciousRegion && a.region!=null &&
                Math.abs(a.region.x-100)<=24 && Math.abs(a.region.y-220)<=24;
        });
        r.check("troca A para B sem mapa",() -> {
            AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
            d.armOnVerifiedNonOffer(new Scene(0,0,0,0,80));
            AdaptiveCardRegionDetector.Result a=d.inspect(
                new Scene(100,220,170,100,230),33);
            AdaptiveCardRegionDetector.Result b=d.inspect(
                new Scene(100,220,170,100,155),66);
            return a.suspiciousRegion && b.suspiciousRegion &&
                   b.changedSinceLastFrame;
        });
        r.check("desaparecimento em um frame",() -> {
            AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
            d.armOnVerifiedNonOffer(new Scene(0,0,0,0,80));
            d.inspect(new Scene(100,220,170,100,230),33);
            return !d.inspect(new Scene(0,0,0,0,80),66).suspiciousRegion;
        });
        r.check("rastreador acompanha deslocamento",() -> {
            FastCardVisualTracker t=new FastCardVisualTracker();
            boolean armed=t.armFromVerifiedCard(new Textured(75,180,true),
                new FastCardVisualTracker.Box(75,180,140,110));
            boolean first=t.inspect(new Textured(75,180,true),33).present;
            FastCardVisualTracker.Observation moved=t.inspect(
                new Textured(82,186,true),66);
            return armed && first && moved.present &&
                moved.x==82 && moved.y==186;
        });
        r.check("rastreador apaga ao sumir",() -> {
            FastCardVisualTracker t=new FastCardVisualTracker();
            t.armFromVerifiedCard(new Textured(75,180,true),
                new FastCardVisualTracker.Box(75,180,140,110));
            t.inspect(new Textured(75,180,true),33);
            FastCardVisualTracker.Observation gone=t.inspect(
                new Textured(75,180,false),66);
            return gone.disappeared && !gone.present;
        });
        r.check("OCR não acumula fila de frames",() -> {
            FastOcrScheduler s=new FastOcrScheduler(120);
            long ticket=s.maybeStart(true,0);
            return ticket>0 && s.maybeStart(true,33)==-1 &&
                s.maybeStart(true,66)==-1 && s.complete(ticket) &&
                s.maybeStart(true,132)>ticket;
        });
        r.check("STOP invalida leitura atrasada",() -> {
            FastOcrScheduler s=new FastOcrScheduler(120);
            long old=s.maybeStart(true,0);
            s.reset();
            long next=s.maybeStart(true,0);
            return !s.complete(old) && s.isCurrent(next);
        });
        r.check("mudança de orientação limpa ROI",() -> {
            AdaptiveCardRegionDetector d=new AdaptiveCardRegionDetector();
            d.armOnVerifiedNonOffer(new Scene(0,0,0,0,80));
            FastCardVisualTracker.Pixels landscape=new FastCardVisualTracker.Pixels() {
                public int width(){return 700;}
                public int height(){return 400;}
                public int luminance(int x,int y){return 80;}
            };
            return d.inspect(landscape,33).frameDimensionsChanged && !d.isArmed();
        });
        JSONObject result=new JSONObject();
        String json;
        try {
            result.put("schema","vexo-radar-self-test-v1");
            result.put("mode","SIMULATION_ONLY");
            result.put("passed",r.passed);
            result.put("total",r.total);
            result.put("checks",r.checks);
            result.put("noImageOrOcrTextExported",true);
            json=result.toString(2);
        } catch(Exception ignored) {
            json="{\"schema\":\"vexo-radar-self-test-v1\",\"error\":\"ENCODING\"}";
        }
        String title="Teste local fictício: "+r.passed+"/"+r.total+
            "\nNão mede FPS, precisão OCR ou leitura real da 99.\n\n";
        return new Report(r.passed,r.total,title+r.display.toString(),json);
    }
}
