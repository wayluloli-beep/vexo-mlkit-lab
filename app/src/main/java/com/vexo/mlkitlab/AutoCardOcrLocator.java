package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Visual card CANDIDATE derived exclusively from ML Kit line bounding boxes.
 *
 * IMPORTANT: never use these candidates as proof of an active 99 offer.
 * A screenshot shown in Photos can produce identical pixels and OCR. This
 * detector drives only the user's opt-in LAB overlay, not financial alerts.
 * Text and pixels stay in RAM, with no log, saved screenshot or network path.
 */
final class AutoCardOcrLocator {
    private static final Pattern PRICE = Pattern.compile(
        "(?i)r\\s*\\$\\s*\\d{1,6}(?:[.,]\\d{2})\\b");
    private static final Pattern DISTANCE = Pattern.compile(
        "(?i)\\b\\d{1,3}\\s*min\\b.{0,35}?\\d{1,4}(?:[.,]\\d+)?\\s*km\\b");

    static final class Line {
        final String text;
        final Box rect;
        Line(String text, Box rect) {
            this.text=text==null?"":text;
            this.rect=rect;
        }
    }

    static final class Result {
        final Box card,price,origin,destination;
        /** Always means VISUAL candidate; NEVER proof of live 99 application. */
        final boolean visualOnly=true;
        Result(Box card,Box price,Box origin,Box destination) {
            this.card=card;this.price=price;this.origin=origin;
            this.destination=destination;
        }

        // Child boxes are relative to the observed parent, never screen-fixed.
        Box place(Box newParent,Box child) {
            int x=newParent.x+scale(child.x-card.x,newParent.width,card.width);
            int y=newParent.y+scale(child.y-card.y,newParent.height,card.height);
            int w=Math.max(1,scale(child.width,newParent.width,card.width));
            int h=Math.max(1,scale(child.height,newParent.height,card.height));
            return new Box(x,y,w,h);
        }
    }

    private static int scale(int value,int to,int from) {
        return (int)Math.round(value*to/(double)Math.max(1,from));
    }

    static Result locate(List<Line> source,int width,int height) {
        if(source==null || width<240 || height<320)return null;
        List<Line> lines=new ArrayList<>();
        for(Line l:source)if(valid(l,width,height))lines.add(l);
        if(lines.size()<4)return null;
        lines.sort(Comparator.comparingInt(l->l.rect.y));
        List<Line> routes=new ArrayList<>();
        List<Line> prices=new ArrayList<>();
        for(Line l:lines) {
            String s=norm(l.text);
            if(DISTANCE.matcher(s).find())routes.add(l);
            if(PRICE.matcher(s).find() && !s.contains("aceitar"))prices.add(l);
        }
        if(routes.size()<2 || prices.isEmpty())return null;

        // Require TWO DISTINCT ordered journey rows, not a single advert.
        for(int a=0;a<routes.size();a++)for(int b=a+1;b<routes.size();b++) {
            Line from=routes.get(a),to=routes.get(b);
            int gap=to.rect.y-from.rect.y;
            if(gap<Math.max(8,from.rect.height/2) ||
                gap>height/3 ||
                Math.abs(from.rect.x-to.rect.x)>width/3)continue;

            Line price=bestPrice(prices,from);
            if(price==null)continue;

            // A header, payment marker, trip/rating marker or accept CTA
            // supports a ride-shaped layout. The screen may be a GALLERY.
            Line firstContext=null;
            int hints=0;
            int minY=Math.max(0,price.rect.y-height/5);
            int maxY=Math.min(height,to.rect.y+height/9);
            for(Line line:lines) {
                String s=norm(line.text);
                if(line.rect.y<minY || line.rect.y>maxY ||
                    Math.abs(line.rect.x-price.rect.x)>width/2)continue;
                if(isRideContext(s)) {
                    hints++;
                    if(firstContext==null ||
                       line.rect.y<firstContext.rect.y)firstContext=line;
                }
            }
            if(hints==0)continue;

            // Generate an APPROXIMATE parent from the observed content
            // rather than requiring the words Moto Negocia and Aceitar.
            int top=Math.min(price.rect.y,firstContext.rect.y);
            int bottom=to.rect.y+to.rect.height;
            int left=Math.min(Math.min(price.rect.x,from.rect.x),to.rect.x);
            int right=Math.max(Math.max(price.rect.x+price.rect.width,
                             from.rect.x+from.rect.width),to.rect.x+to.rect.width);
            int contextualBottom=Math.min(height,bottom+height/13);
            for(Line line:lines) {
                if(line.rect.y<top || line.rect.y>contextualBottom ||
                   Math.abs(line.rect.x-price.rect.x)>width/4)continue;
                left=Math.min(left,line.rect.x);
                right=Math.max(right,line.rect.x+line.rect.width);
                if(line.rect.y<=to.rect.y+height/20)
                    bottom=Math.max(bottom,line.rect.y+line.rect.height);
            }
            int padX=Math.max(12,width/32),padY=Math.max(12,height/85);
            int x0=Math.max(0,left-padX),y0=Math.max(0,top-padY);
            int x1=Math.min(width,right+padX);
            int y1=Math.min(height,bottom+padY);

            // Many ride cards span most of a phone's width even though the
            // recognizer sees only short price/route lines on the left.
            if(left<width/5 && right<width*4/5) {
                x0=Math.min(x0,Math.max(0,width/30));
                x1=Math.max(x1,Math.min(width,width*29/30));
            }
            if(x1-x0<width/3 || y1-y0<height/9)continue;
            return new Result(new Box(x0,y0,x1-x0,y1-y0),
                padded(price.rect,width,height,8),
                padded(from.rect,width,height,10),
                padded(to.rect,width,height,10));
        }
        return null;
    }

    private static Line bestPrice(List<Line> prices,Line firstRoute) {
        Line best=null;
        for(Line p:prices) {
            if(p.rect.y+p.rect.height>=firstRoute.rect.y ||
               p.rect.y<firstRoute.rect.y-600)continue;
            if(Math.abs(p.rect.x-firstRoute.rect.x)>400)continue;
            if(best==null || p.rect.height>best.rect.height ||
               (p.rect.height==best.rect.height && p.rect.y<best.rect.y))
                best=p;
        }
        return best;
    }

    private static boolean isRideContext(String s) {
        return s.contains("moto negocia") ||
            s.contains("99 moto") || s.contains("99 pop") ||
            s.contains("pgto") || s.contains("pagamento no app") ||
            s.contains("pago no app") || s.contains("tarifa base") ||
            s.contains("corridas") || s.contains("perfil premium") ||
            s.contains("cartao verif") ||
            (s.contains("aceitar") && s.contains("r$"));
    }

    private static boolean valid(Line l,int w,int h) {
        return l!=null && l.rect!=null && l.rect.width>0 &&
            l.rect.height>0 && l.rect.x>=0 && l.rect.y>=0 &&
            (long)l.rect.x+l.rect.width<=w &&
            (long)l.rect.y+l.rect.height<=h;
    }

    private static Box padded(Box b,int w,int h,int pad) {
        int x=Math.max(0,b.x-pad),y=Math.max(0,b.y-pad);
        return new Box(x,y,Math.min(w,b.x+b.width+pad)-x,
            Math.min(h,b.y+b.height+pad)-y);
    }

    private static String norm(String text) {
        String value=Normalizer.normalize(text,Normalizer.Form.NFKD)
            .replaceAll("\\p{M}+","").toLowerCase(Locale.ROOT);
        return value.replaceAll("\\s+"," ").trim();
    }
}
