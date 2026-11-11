package com.vexo.mlkitlab;

/**
 * Stage 0: automatic, bounded-resolution search for NEW changing rectangles.
 * No hard-coded screen coordinates, no pixels uploaded, no OCR required.
 *
 * The baseline MUST be confirmed to be a non-offer screen by the owner/caller.
 * A changed rectangle is ONLY a proposal to investigate with OCR; gallery,
 * maps, animations and ads can all produce a proposal. It is never permission
 * to notify the driver about a live offer.
 *
 * The detector samples <= 72x128 points (no bitmap allocation), flood-fills
 * neighboring changed cells, and returns the largest reasonably rectangular
 * component. Dimensions/rotation invalidates baseline and tracking.
 */
public final class AdaptiveCardRegionDetector {
    private static final int MAX_COLS=72, MAX_ROWS=128;
    private static final int PIXEL_DELTA=36;
    private static final int MIN_COMPONENT_CELLS=9;
    private static final int MIN_MEAN_NEW_CHANGE=20;
    private int width, height, cols, rows, count;
    private int[] baseline, previous, current, queue;
    private byte[] changed, visited;
    private boolean armed;
    private long lastAt=-1;

    public static final class Result {
        public final boolean baselineReady;
        public final boolean suspiciousRegion;
        public final boolean changedSinceLastFrame;
        public final boolean frameDimensionsChanged;
        public final int candidatesExamined;
        public final int changedCells;
        public final FastCardVisualTracker.Box region;
        Result(boolean ready,boolean suspicious,boolean changedNow,boolean resized,
               int components,int changes,FastCardVisualTracker.Box box){
            baselineReady=ready;suspiciousRegion=suspicious;
            changedSinceLastFrame=changedNow;
            frameDimensionsChanged=resized;candidatesExamined=components;
            changedCells=changes;region=box;
        }
    }

    /** Explicit re-baseline: never learn a card as "no offer" automatically. */
    public synchronized boolean armOnVerifiedNonOffer(FastCardVisualTracker.Pixels pixels) {
        reset();
        if(pixels==null || pixels.width()<120 || pixels.height()<120) return false;
        width=pixels.width();height=pixels.height();
        cols=Math.max(20,Math.min(MAX_COLS,width/12));
        rows=Math.max(20,Math.min(MAX_ROWS,height/12));
        count=cols*rows;
        baseline=new int[count];previous=new int[count];current=new int[count];
        changed=new byte[count];visited=new byte[count];queue=new int[count];
        for(int i=0;i<count;i++) {
            int value=sample(pixels,i%cols,i/cols);
            if(value<0 || value>255){reset();return false;}
            baseline[i]=value;previous[i]=value;
        }
        armed=true;
        return true;
    }

    public synchronized Result inspect(FastCardVisualTracker.Pixels pixels,long atMs) {
        if(!armed) return new Result(false,false,false,false,0,0,null);
        if(pixels==null || pixels.width()!=width || pixels.height()!=height) {
            reset(); return new Result(false,false,false,true,0,0,null);
        }
        if(atMs<0 || atMs<lastAt) return new Result(true,false,false,false,0,0,null);
        lastAt=atMs;
        int changes=0, changedSinceLast=0;
        for(int i=0;i<count;i++) {
            int val=sample(pixels,i%cols,i/cols);
            if(val<0 || val>255) {reset();return new Result(false,false,false,true,0,0,null);}
            current[i]=val;
            changed[i]=(byte)(Math.abs(val-baseline[i])>=PIXEL_DELTA?1:0);
            changes+=changed[i];
            changedSinceLast+=Math.abs(val-previous[i]);
            previous[i]=val;
            visited[i]=0;
        }
        // Entire-screen transitions (e.g. switching apps) are not card IDs.
        if(changes>count*80/100)
            return new Result(true,false,changedSinceLast/count>=MIN_MEAN_NEW_CHANGE,false,0,changes,null);

        long bestScore=-1;
        int bx=0,by=0,bw=0,bh=0,components=0;
        for(int root=0;root<count;root++) {
            if(changed[root]==0 || visited[root]!=0) continue;
            int first=0,last=0, minX=cols,minY=rows,maxX=0,maxY=0,area=0;
            visited[root]=1;
            queue[last++]=root;
            while(first<last) {
                int idx=queue[first++],gx=idx%cols,gy=idx/cols;
                area++;
                minX=Math.min(minX,gx);maxX=Math.max(maxX,gx);
                minY=Math.min(minY,gy);maxY=Math.max(maxY,gy);
                for(int yy=Math.max(0,gy-1);yy<=Math.min(rows-1,gy+1);yy++)
                    for(int xx=Math.max(0,gx-1);xx<=Math.min(cols-1,gx+1);xx++) {
                        int other=yy*cols+xx;
                        if(visited[other]==0 && changed[other]!=0){
                            visited[other]=1; queue[last++]=other;
                        }
                    }
            }
            components++;
            int cellsW=maxX-minX+1,cellsH=maxY-minY+1;
            int bboxCells=cellsW*cellsH;
            if(area<MIN_COMPONENT_CELLS || area*4<bboxCells) continue;
            int x0=minX*width/cols,y0=minY*height/rows;
            int x1=Math.min(width,(maxX+1)*width/cols);
            int y1=Math.min(height,(maxY+1)*height/rows);
            int rw=x1-x0,rh=y1-y0;
            if(rw<width*15/100 || rh<height*4/100 ||
               rw>width*95/100 || rh>height*75/100) continue;
            double aspect=rw/(double)Math.max(1,rh);
            if(aspect<.55 || aspect>9.0) continue;
            // Prefer large regions whose interior actually changed,
            // not sparse lines or individual text glyphs.
            long score=((long)area*1000/bboxCells)*area;
            if(score>bestScore){
                bestScore=score;bx=x0;by=y0;bw=rw;bh=rh;
            }
        }
        FastCardVisualTracker.Box box=null;
        if(bestScore>=0) {
            int marginX=Math.max(2,bw/25),marginY=Math.max(2,bh/20);
            int x0=Math.max(0,bx-marginX),y0=Math.max(0,by-marginY);
            int x1=Math.min(width,bx+bw+marginX),y1=Math.min(height,by+bh+marginY);
            box=new FastCardVisualTracker.Box(x0,y0,x1-x0,y1-y0);
        }
        return new Result(true,box!=null,changedSinceLast/count>=MIN_MEAN_NEW_CHANGE,
                          false,components,changes,box);
    }

    private int sample(FastCardVisualTracker.Pixels pixels,int col,int row) {
        int sx=Math.min(width-1,((col*2+1)*width)/(cols*2));
        int sy=Math.min(height-1,((row*2+1)*height)/(rows*2));
        return pixels.luminance(sx,sy);
    }

    public synchronized void reset() {
        armed=false;lastAt=-1;width=0;height=0;cols=0;rows=0;count=0;
        baseline=null;previous=null;current=null;changed=null;visited=null;queue=null;
    }
    public synchronized boolean isArmed(){return armed;}
}
