package com.vexo.mlkitlab;

import android.app.Activity;
import android.os.Bundle;
import android.os.SystemClock;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Visible experiment of modular adaptive region discovery and tracking.
 * Source is deliberately SYNTHETIC: NO MediaProjection, NO real 99, NO OCR,
 * NO camera or screenshot access, and no notification about an active ride.
 * Uses the same detector/tracker code that will later be integrated by Dev.
 */
public final class VisualRadarLabActivity extends Activity {
    private TextView status;
    private RadarView radar;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root=new LinearLayout(this);
        root.setBackgroundColor(0xff0c1522);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(12*getResources().getDisplayMetrics().density);
        root.setPadding(pad,pad,pad,pad);
        TextView title=new TextView(this);
        title.setText("VEXO • Radar modular");
        title.setTextSize(22);title.setTextColor(0xff7cf7ad);
        root.addView(title);
        TextView caption=new TextView(this);
        caption.setText("TESTE FICTÍCIO: região automática, movimento, troca de card e desaparecimento. Não é leitura de tela da 99.");
        caption.setTextColor(0xffdae0e8);
        caption.setTextSize(13);
        root.addView(caption);
        status=new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(15);
        status.setPadding(0,pad,0,pad);
        root.addView(status);
        radar=new RadarView();
        root.addView(radar,new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root);
    }

    @Override protected void onPause(){
        super.onPause();
        if(radar!=null)radar.stop();
    }
    @Override protected void onResume(){
        super.onResume();
        if(radar!=null)radar.restart();
    }

    private final class RadarView extends View {
        private final Paint p=new Paint(3);
        private final AdaptiveCardRegionDetector finder=new AdaptiveCardRegionDetector();
        private final FastCardVisualTracker tracker=new FastCardVisualTracker();
        private long startedAt, frames, lastStatusAt;
        private boolean started, running=true;

        RadarView(){super(VisualRadarLabActivity.this);}
        void stop(){running=false;finder.reset();tracker.reset();}
        void restart(){running=true;started=false;startedAt=0;frames=0;lastStatusAt=0;invalidate();}

        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            if(!running)return;
            final int w=getWidth(),h=getHeight();
            if(w<150||h<220){postInvalidateDelayed(33);return;}
            long now=SystemClock.elapsedRealtime();
            if(!started){started=true;startedAt=now;}
            long t=(now-startedAt)%9500;
            boolean card=t>=1000 && t<5900 || t>=6800 && t<8600;
            boolean second=t>=3800 && t<5900;
            int cw=Math.max(105,w*53/100),ch=Math.max(72,h*16/100);
            int cx=card?(second?w*24/100:w*20/100):0;
            int cy=card?(second?h*35/100:h*28/100):0;
            if(card && !second) {
                cx+=(int)(12*Math.sin((now-startedAt)/520.0));
                cy+=(int)(8*Math.sin((now-startedAt)/460.0));
            }
            SyntheticPixels pixels=new SyntheticPixels(w,h,cx,cy,cw,ch,card,second);
            if(!finder.isArmed()){
                finder.armOnVerifiedNonOffer(new SyntheticPixels(w,h,0,0,0,0,false,false));
                tracker.reset();
            }
            AdaptiveCardRegionDetector.Result region=finder.inspect(pixels,now);
            FastCardVisualTracker.Observation matched=null;
            if(tracker.isArmed()) matched=tracker.inspect(pixels,now);
            if(region.suspiciousRegion && card &&
               (matched==null||!matched.present)) {
                // Only in this explicitly fictional lab may the visual scene
                // itself act as ground truth. Android production MUST ask
                // classifier + verified screen context before arming tracker.
                tracker.armFromVerifiedCard(pixels,region.region);
                matched=tracker.inspect(pixels,now);
            }

            canvas.drawColor(0xff121d2d);
            p.setColor(0xff263a51);
            for(int yy=32;yy<h;yy+=40)canvas.drawLine(0,yy,w,yy,p);
            if(card) {
                p.setColor(Color.WHITE);
                canvas.drawRoundRect(new RectF(cx,cy,cx+cw,cy+ch),14,14,p);
                p.setColor(0xff15ae5d);
                p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3);
                canvas.drawRoundRect(new RectF(cx,cy,cx+cw,cy+ch),14,14,p);
                p.setStyle(Paint.Style.FILL);
                p.setColor(0xff102823);p.setTextSize(Math.max(15,cw/12));
                canvas.drawText(second?"OFERTA B (SIMULADA)":"OFERTA A (SIMULADA)",cx+12,cy+28,p);
                p.setTextSize(Math.max(23,cw/6));
                canvas.drawText(second?"R$ 35,00":"R$ 40,70",cx+12,cy+ch-18,p);
            }
            if(matched!=null&&matched.present){
                // A green outline is the TRACKER output; the blue dashed
                // rectangle below is just the initial automatic proposal.
                p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(5);p.setColor(0xff32ed83);
                canvas.drawRect(matched.x,matched.y,
                    matched.x+cw,matched.y+ch,p);
                p.setStyle(Paint.Style.FILL);
            }else if(region.suspiciousRegion && region.region!=null){
                p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3);p.setColor(0xff58c9ff);
                FastCardVisualTracker.Box b=region.region;
                canvas.drawRect(b.x,b.y,b.x+b.width,b.y+b.height,p);
                p.setStyle(Paint.Style.FILL);
            }
            frames++;
            if(now-lastStatusAt>250) {
                lastStatusAt=now;
                String label=matched!=null&&matched.present?"RASTREANDO":
                    region.suspiciousRegion?"DETECTOU REGIÃO":"PROCURANDO";
                status.setText(label+"  •  "+frames+" frames  •  "+
                    (region.changedSinceLastFrame?"mudança visual":"quadro estável")+
                    "\nSem OCR ou alerta da 99; mede somente o comportamento visual.");
            }
            postInvalidateDelayed(33); // request, NOT a promise of 30 actual FPS
        }
    }

    private static final class SyntheticPixels implements FastCardVisualTracker.Pixels {
        final int w,h,x,y,cw,ch;final boolean card,second;
        SyntheticPixels(int w,int h,int x,int y,int cw,int ch,boolean card,boolean second){
            this.w=w;this.h=h;this.x=x;this.y=y;this.cw=cw;this.ch=ch;
            this.card=card;this.second=second;
        }
        @Override public int width(){return w;}
        @Override public int height(){return h;}
        @Override public int luminance(int px,int py){
            if(!card||px<x||px>=x+cw||py<y||py>=y+ch)return 80;
            int dx=px-x,dy=py-y;
            if(dx<4||dy<4||dx>=cw-4||dy>=ch-4)return 45;
            // Synthetic text/line texture: stable relative to the moving card.
            if((dy/10)%3==0 || (dx/13+dy/9)%9==0)
                return second?86:45;
            return second?175:233;
        }
    }
}
