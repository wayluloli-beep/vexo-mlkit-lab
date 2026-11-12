package com.vexo.mlkitlab;

/**
 * LIVE visual motion observer, separate from OCR and notification deduplication.
 * Inspects each captured ImageReader frame while the Image is open.
 *
 * A highlighted box is a VISUAL CHANGE, never proof of an offer or app 99.
 * Does NOT track a stationary card without additional confirmed ROI signals.
 * All sampled luminances and rectangles are RAM-only and erased on STOP.
 */
public final class LiveScreenMotionDetector {
    private static final int MAX_COLUMNS=54, MAX_ROWS=96;
    private static final int PIXEL_DELTA=34;
    private static final int MIN_CHANGED_CELLS=12;
    private static final int MIN_COMPONENT_CELLS=10;
    private int width,height,cols,rows,size;
    private byte[] previous,changed,visited;
    private int[] queue;
    private long lastTimeMs=-1,windowStartMs=-1;
    private int windowFrames=0, measuredFps=0;

    public static final class Observation {
        public final boolean current;
        public final boolean resized;
        public final boolean motion;
        public final boolean wholeScreenChanged;
        public final int fps;
        public final int changedCells;
        public final int gridCells;
        public final FastCardVisualTracker.Box box;

        Observation(boolean current,boolean resized,boolean motion,
                    boolean full,int fps,int changedCells,int gridCells,
                    FastCardVisualTracker.Box box) {
            this.current=current;this.resized=resized;this.motion=motion;
            this.wholeScreenChanged=full;this.fps=fps;
            this.changedCells=changedCells;this.gridCells=gridCells;this.box=box;
        }
    }

    public synchronized Observation inspect(FastCardVisualTracker.Pixels pixels,long atMs) {
        if(pixels==null || atMs<0 || pixels.width()<120 || pixels.height()<120)
            return new Observation(false,false,false,false,measuredFps,0,size,null);
        if(lastTimeMs>=0 && atMs<lastTimeMs)
            return new Observation(false,false,false,false,measuredFps,0,size,null);
        boolean resize=width!=pixels.width() || height!=pixels.height();
        if(previous==null || resize) {
            init(pixels);
            if(windowStartMs<0)windowStartMs=atMs;
            lastTimeMs=atMs;
            return new Observation(true,resize,false,false,measuredFps,0,size,null);
        }
        int changedCount=0;
        for(int i=0;i<size;i++) {
            int lum=sample(pixels,i%cols,i/cols);
            int old=previous[i]&255;
            previous[i]=(byte)lum;
            byte hit=(byte)(Math.abs(lum-old)>=PIXEL_DELTA?1:0);
            changed[i]=hit;
            visited[i]=0;
            changedCount+=hit;
        }
        lastTimeMs=atMs;
        windowFrames++;
        long delta=atMs-windowStartMs;
        if(delta>=1000) {
            measuredFps=(int)Math.round(windowFrames*1000.0/delta);
            windowStartMs=atMs;
            windowFrames=0;
        }
        if(changedCount<MIN_CHANGED_CELLS)
            return new Observation(true,false,false,false,measuredFps,changedCount,size,null);
        if(changedCount>size*60/100)
            return new Observation(true,false,true,true,measuredFps,changedCount,size,null);

        int winnerX=0,winnerY=0,winnerW=0,winnerH=0,bestCount=0;
        for(int start=0;start<size;start++) {
            if(changed[start]==0 || visited[start]!=0)continue;
            int first=0,last=0;
            int minX=cols,minY=rows,maxX=-1,maxY=-1;
            visited[start]=1;queue[last++]=start;
            while(first<last) {
                int index=queue[first++],x=index%cols,y=index/cols;
                minX=Math.min(minX,x);minY=Math.min(minY,y);
                maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);
                for(int cy=Math.max(0,y-1);cy<=Math.min(rows-1,y+1);cy++)
                    for(int cx=Math.max(0,x-1);cx<=Math.min(cols-1,x+1);cx++) {
                        int next=cy*cols+cx;
                        if(changed[next]!=0 && visited[next]==0) {
                            visited[next]=1;queue[last++]=next;
                        }
                    }
            }
            if(last<MIN_COMPONENT_CELLS || last<=bestCount)continue;
            bestCount=last;
            winnerX=minX;winnerY=minY;
            winnerW=maxX-minX+1;winnerH=maxY-minY+1;
        }
        if(bestCount<MIN_COMPONENT_CELLS)
            return new Observation(true,false,true,false,measuredFps,changedCount,size,null);
        int x0=Math.max(0,winnerX*width/cols - width/80);
        int y0=Math.max(0,winnerY*height/rows - height/80);
        int x1=Math.min(width,(winnerX+winnerW)*width/cols + width/80);
        int y1=Math.min(height,(winnerY+winnerH)*height/rows + height/80);
        FastCardVisualTracker.Box candidate=
            new FastCardVisualTracker.Box(x0,y0,x1-x0,y1-y0);
        return new Observation(true,false,true,false,measuredFps,changedCount,size,candidate);
    }

    private void init(FastCardVisualTracker.Pixels pixels) {
        width=pixels.width();height=pixels.height();
        cols=Math.max(20,Math.min(MAX_COLUMNS,width/14));
        rows=Math.max(20,Math.min(MAX_ROWS,height/14));
        size=cols*rows;
        previous=new byte[size];
        changed=new byte[size];
        visited=new byte[size];
        queue=new int[size];
        for(int i=0;i<size;i++)
            previous[i]=(byte)sample(pixels,i%cols,i/cols);
        windowStartMs=-1;windowFrames=0;measuredFps=0;
    }

    private int sample(FastCardVisualTracker.Pixels p,int col,int row) {
        int x=(int)(((long)(2*col+1)*width)/(2*cols));
        int y=(int)(((long)(2*row+1)*height)/(2*rows));
        return p.luminance(Math.min(width-1,x),Math.min(height-1,y));
    }

    public synchronized void reset() {
        width=height=cols=rows=size=0;
        previous=null;changed=null;visited=null;queue=null;
        lastTimeMs=-1;windowStartMs=-1;windowFrames=0;measuredFps=0;
    }
}
