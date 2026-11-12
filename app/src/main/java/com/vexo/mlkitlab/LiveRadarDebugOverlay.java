package com.vexo.mlkitlab;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.PixelFormat;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Optional read-only radar heads-up display for a consented MediaProjection.
 *
 * Blue rectangle = current VISUAL MOTION, not a detected ride.
 * Green rectangles = text blocks the ML Kit OCR saw in a fresh frame, NOT
 * proof of a live 99 offer. Shows no words, amounts, locations, identities.
 * FLAG_SECURE + FLAG_NOT_TOUCHABLE prevent screen recording/leaking UI and
 * accidental acceptance of the ride through this overlay.
 */
final class LiveRadarDebugOverlay {
    private final Context context;
    private final WindowManager wm;
    private RadarView view;
    private final int blue=0xff40bfff, green=0xff55ee99;
    private int width,height,fps,frames,ocrRead,changedCells;
    private boolean working,visualChanged,fullTransition;
    private FastCardVisualTracker.Box motionBox;
    private final List<Rect> ocrBoxes=new ArrayList<>();
    private int ocrWidth,ocrHeight;
    private long ocrSeenAt=-1;

    LiveRadarDebugOverlay(Context context) {
        this.context=context.getApplicationContext();
        wm=(WindowManager)this.context.getSystemService(Context.WINDOW_SERVICE);
    }

    void updateMotion(int sourceW,int sourceH,
                      LiveScreenMotionDetector.Observation obs,
                      int frames,int ocrRead,boolean ocrBusy,long nowMs) {
        if(obs==null || !obs.current) return;
        this.width=sourceW;this.height=sourceH;
        this.frames=frames;this.ocrRead=ocrRead;
        fps=obs.fps;working=ocrBusy;
        changedCells=obs.changedCells;
        visualChanged=obs.motion;
        fullTransition=obs.wholeScreenChanged;
        motionBox=obs.box;
        // Text outlines are only visible while still fresh; an old OCR box
        // must not follow a different app/screen after a visual transition.
        if(obs.motion || ocrSeenAt<0 || nowMs-ocrSeenAt>500) {
            ocrBoxes.clear();
            ocrSeenAt=-1;
        }
        if(!ensure())return;
        view.invalidate();
    }

    void textBlocks(List<Rect> boxes,int sourceW,int sourceH,long nowMs) {
        if(boxes==null || !ensure())return;
        ocrBoxes.clear();
        for(Rect r:boxes) {
            if(r==null || r.isEmpty() || ocrBoxes.size()>=12)continue;
            ocrBoxes.add(new Rect(r));
        }
        ocrWidth=sourceW;ocrHeight=sourceH;
        ocrSeenAt=nowMs;
        view.invalidate();
    }

    void clearText() {
        ocrBoxes.clear();ocrSeenAt=-1;
        if(view!=null)view.invalidate();
    }

    private boolean ensure() {
        if(wm==null || !VexoOfferOverlay.allowed(context)) {hide();return false;}
        if(view!=null)return true;
        view=new RadarView(context);
        WindowManager.LayoutParams lp=new WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE |
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE |
                WindowManager.LayoutParams.FLAG_SECURE |
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT);
        lp.gravity=Gravity.TOP|Gravity.START;
        lp.alpha=.65f;
        lp.setTitle("Vexo radar - somente marcadores e contadores, sem dados");
        try {wm.addView(view,lp);return true;}
        catch(RuntimeException err) {view=null;return false;}
    }

    void hide() {
        View old=view;view=null;
        motionBox=null;ocrBoxes.clear();ocrSeenAt=-1;
        if(old!=null && wm!=null)try {wm.removeView(old);}catch(RuntimeException ignored) {}
    }

    private final class RadarView extends View {
        private final Paint paint=new Paint(3);
        RadarView(Context c){super(c);setWillNotDraw(false);}
        @Override protected void onDraw(Canvas c) {
            super.onDraw(c);
            float density=getResources().getDisplayMetrics().density;
            float side=10*density,base=45*density;
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(0xc9152630);
            c.drawRoundRect(side,base,getWidth()*.68f,base+75*density,9*density,9*density,paint);
            paint.setTextSize(13*density);
            paint.setColor(Color.WHITE);
            c.drawText("VEXO • RADAR VISUAL",side+8*density,base+17*density,paint);
            paint.setTextSize(11*density);
            String mode=fullTransition?"TROCA DE TELA":
                visualChanged?"REGIÃO EM MOVIMENTO":"SEM MOVIMENTO NOVO";
            c.drawText("FPS recebido: "+fps+"  •  quadros: "+frames,
                side+8*density,base+34*density,paint);
            c.drawText(mode+"  •  OCR: "+(working?"OCUPADO":"AGUARDANDO"),
                side+8*density,base+49*density,paint);
            c.drawText("Blocos OCR: "+ocrRead+"  •  NÃO CONFIRMA 99 AO VIVO",
                side+8*density,base+64*density,paint);
            if(motionBox!=null && width>0 && height>0) {
                float sx=getWidth()/(float)width,sy=getHeight()/(float)height;
                paint.setColor(blue);paint.setStyle(Paint.Style.STROKE);
                paint.setStrokeWidth(2*density);
                c.drawRect(motionBox.x*sx,motionBox.y*sy,
                    (motionBox.x+motionBox.width)*sx,
                    (motionBox.y+motionBox.height)*sy,paint);
                paint.setStyle(Paint.Style.FILL);
            }
            if(ocrWidth>0 && ocrHeight>0) {
                float sx=getWidth()/(float)ocrWidth,sy=getHeight()/(float)ocrHeight;
                paint.setColor(green);paint.setStyle(Paint.Style.STROKE);
                paint.setStrokeWidth(2*density);
                for(Rect r:ocrBoxes) c.drawRect(r.left*sx,r.top*sy,r.right*sx,r.bottom*sy,paint);
                paint.setStyle(Paint.Style.FILL);
            }
        }
    }
}
