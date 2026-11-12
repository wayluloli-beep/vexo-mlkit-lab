package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Candidate locator using real ML Kit line rectangles. NOT a generic object
 * detector and NOT proof that the capture originated from the live 99 app.
 * It refuses to invent ROIs if the recognizable card structure is absent.
 * All OCR text is ephemeral in RAM; no logs, persistence, network or alerts.
 */
final class AutoCardOcrLocator {
    private static final Pattern PRICE = Pattern.compile("(?i)r\\s*\\$\\s*\\d{1,5}[.,]\\d{2}");
    private static final Pattern DISTANCE = Pattern.compile(
        "(?i)\\b\\d{1,3}\\s*min\\b.{0,35}\\d{1,4}(?:[.,]\\d+)?\\s*km\\b");

    static final class Line {
        final String text;
        final Box rect;
        Line(String text, Box rect) { this.text=text==null?"":text; this.rect=rect; }
    }

    static final class Result {
        final Box card, price, origin, destination;
        Result(Box card,Box price,Box origin,Box destination) {
            this.card=card;this.price=price;this.origin=origin;this.destination=destination;
        }

        // Child boxes are anchored to the card, not to fixed display coordinates.
        Box place(Box newParent, Box child) {
            int x=newParent.x+scale(child.x-card.x,newParent.width,card.width);
            int y=newParent.y+scale(child.y-card.y,newParent.height,card.height);
            int w=Math.max(1,scale(child.width,newParent.width,card.width));
            int h=Math.max(1,scale(child.height,newParent.height,card.height));
            return new Box(x,y,w,h);
        }
    }

    private static int scale(int value,int target,int source) {
        return (int)Math.round(value*target/(double)Math.max(1,source));
    }

    static Result locate(List<Line> source,int width,int height) {
        if(source==null || width<240 || height<320) return null;
        List<Line> lines=new ArrayList<>();
        for(Line line:source) if(line!=null && line.rect!=null
                && line.rect.width>0 && line.rect.height>0
                && line.rect.x>=0 && line.rect.y>=0
                && line.rect.x+line.rect.width<=width
                && line.rect.y+line.rect.height<=height) lines.add(line);
        Line service=null,accept=null;
        for(Line l:lines) {
            String s=norm(l.text);
            if(service==null && (s.contains("moto negocia") ||
                s.contains("99 moto") || s.contains("99pop") || s.contains("99 pop")))
                service=l;
            if(s.contains("aceitar") && (s.contains("r$") || s.contains("r $")))
                if(accept==null || l.rect.y>accept.rect.y)accept=l;
        }
        if(service==null || accept==null || accept.rect.y<=service.rect.y+service.rect.height)
            return null;
        Line price=null;
        List<Line> distances=new ArrayList<>();
        for(Line line:lines) {
            if(line.rect.y<=service.rect.y || line.rect.y>=accept.rect.y)continue;
            String s=norm(line.text);
            if(PRICE.matcher(s).find() &&
                    (price==null || line.rect.y<price.rect.y)) price=line;
            if(DISTANCE.matcher(s).find()) distances.add(line);
        }
        if(price==null || distances.size()<2)return null;
        distances.sort((a,b)->Integer.compare(a.rect.y,b.rect.y));
        Line origin=null,destination=null;
        for(Line line:distances) {
            if(line.rect.y<=price.rect.y)continue;
            if(origin==null)origin=line;
            else if(line.rect.y>=origin.rect.y+Math.max(4,origin.rect.height/2)) {
                destination=line;break;
            }
        }
        if(origin==null || destination==null || destination.rect.y>=accept.rect.y)return null;

        int left=Math.min(Math.min(service.rect.x,price.rect.x),
                   Math.min(Math.min(origin.rect.x,destination.rect.x),accept.rect.x));
        int right=Math.max(Math.max(service.rect.x+service.rect.width,
                          price.rect.x+price.rect.width),
                   Math.max(Math.max(origin.rect.x+origin.rect.width,
                          destination.rect.x+destination.rect.width),
                          accept.rect.x+accept.rect.width));
        int xPad=Math.max(12,width/24);
        int yPad=Math.max(12,height/85);
        int x0=Math.max(0,left-xPad),y0=Math.max(0,service.rect.y-yPad);
        int x1=Math.min(width,right+xPad),
            y1=Math.min(height,accept.rect.y+accept.rect.height+yPad);
        if(x1-x0<width/3 || y1-y0<height/7)return null;
        Box parent=new Box(x0,y0,x1-x0,y1-y0);
        return new Result(parent,padded(price.rect,width,height,8),
                padded(origin.rect,width,height,10),padded(destination.rect,width,height,10));
    }

    private static Box padded(Box box,int width,int height,int px) {
        int x=Math.max(0,box.x-px),y=Math.max(0,box.y-px);
        int endX=Math.min(width,box.x+box.width+px);
        int endY=Math.min(height,box.y+box.height+px);
        return new Box(x,y,endX-x,endY-y);
    }

    private static String norm(String text) {
        String n=Normalizer.normalize(text,Normalizer.Form.NFKD)
            .replaceAll("\\p{M}+","").toLowerCase(Locale.ROOT);
        return n.replaceAll("\\s+"," ").trim();
    }
}
