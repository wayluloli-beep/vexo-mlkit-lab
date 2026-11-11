package com.vexo.mlkitlab;

/** Pure Java ROI geometry. Does not interpret offers or authorize alerts. */
public final class OcrRoiPlanner {
    private OcrRoiPlanner() {}
    public static final class Roi {
        public final int x,y,width,height;
        public Roi(int x,int y,int width,int height) {
            this.x=x;this.y=y;this.width=width;this.height=height;
        }
    }
    /** Expand an untrusted visual bounding box, clipping safely to frame bounds.
     * Returns null on invalid input; caller should abstain, never fabricate fields.
     */
    public static Roi expand(int frameW,int frameH,int x,int y,int w,int h) {
        if(frameW<=0 || frameH<=0 || w<=0 || h<=0 || x<0 || y<0) return null;
        if((long)x+w>frameW || (long)y+h>frameH) return null;
        int padX=Math.max(12,(int)Math.ceil(w*0.10));
        int padY=Math.max(16,(int)Math.ceil(h*0.15));
        int left=Math.max(0,x-padX),top=Math.max(0,y-padY);
        int right=(int)Math.min(frameW,(long)x+w+padX);
        int bottom=(int)Math.min(frameH,(long)y+h+padY);
        return new Roi(left,top,right-left,bottom-top);
    }
    /** ROI from tracker is only a crop proposal, never proof of a live 99 card. */
    public static boolean worthwhile(int frameW,int frameH,Roi roi) {
        return roi!=null && (long)roi.width*roi.height < (long)frameW*frameH*85/100;
    }
}
