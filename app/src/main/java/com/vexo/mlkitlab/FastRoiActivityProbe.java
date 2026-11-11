package com.vexo.mlkitlab;

import java.util.Arrays;

/**
 * A cheap FIRST-STAGE trigger for a configured card region.
 *
 * Arming requires a verified NON-OFFER baseline in the same MediaProjection
 * session. Changes are merely OCR wake-up candidates, NOT active ride offers.
 * Unlike a full-card tracker, this can notice an unknown card appearing
 * before the first OCR has classified it.
 *
 * Fixed ROI coordinates are a laboratory/layout setting, never inferred
 * solely from financial strings. No pixel image or text is persisted.
 */
public final class FastRoiActivityProbe {
    private static final int COLS=12, ROWS=8, SAMPLES=COLS*ROWS;
    private static final int MIN_CHANGE_MEAN=25;
    private final int[] reference=new int[SAMPLES];
    private final int[] previous=new int[SAMPLES];
    private FastCardVisualTracker.Box roi;
    private long lastAt=-1;
    private boolean armed=false, active=false;

    public static final class Signal {
        public final boolean changed;
        public final boolean risingEdge;
        public final boolean returnedToBaseline;
        public final boolean changedSincePrevious;
        public final int meanDifference;
        Signal(boolean changed,boolean risingEdge,
               boolean returnedToBaseline,boolean changedSincePrevious,int meanDifference) {
            this.changed=changed;
            this.risingEdge=risingEdge;
            this.returnedToBaseline=returnedToBaseline;
            this.changedSincePrevious=changedSincePrevious;
            this.meanDifference=meanDifference;
        }
    }

    public synchronized boolean armOnVerifiedNonOffer(
            FastCardVisualTracker.Pixels pixels,FastCardVisualTracker.Box box) {
        reset();
        if(pixels==null || box==null || box.x<0 || box.y<0 ||
           box.width<24 || box.height<24 ||
           ((long)box.x+box.width)>pixels.width() ||
           ((long)box.y+box.height)>pixels.height()) return false;
        roi=box;
        int index=0;
        for(int row=0;row<ROWS;row++) for(int col=0;col<COLS;col++) {
            int value=sample(pixels,col,row);
            if(value<0 || value>255) {reset();return false;}
            reference[index]=value;
            previous[index++]=value;
        }
        armed=true;
        return true;
    }

    public synchronized Signal inspect(
            FastCardVisualTracker.Pixels pixels,long monotonicMs) {
        // A delayed frame is not evidence that the ROI returned to baseline.
        // Keep the latest state and avoid a spurious next-frame rising edge.
        if(monotonicMs>=0 && monotonicMs<lastAt)
            return new Signal(active,false,false,false,0);
        if(!armed || pixels==null || monotonicMs<0 ||
           pixels.width()<((long)roi.x+roi.width) ||
           pixels.height()<((long)roi.y+roi.height)) {
            boolean old=active;
            active=false;
            return new Signal(false,false,old,false,255);
        }
        lastAt=monotonicMs;
        int sum=0,deltaSinceLastFrame=0,k=0;
        for(int row=0;row<ROWS;row++) for(int col=0;col<COLS;col++) {
            int value=sample(pixels,col,row);
            if(value<0 || value>255) {
                boolean old=active;
                active=false;
                return new Signal(false,false,old,false,255);
            }
            sum+=Math.abs(reference[k]-value);
            deltaSinceLastFrame+=Math.abs(previous[k]-value);
            previous[k++]=value;
        }
        int diff=sum/SAMPLES;
        boolean movedOrChanged=deltaSinceLastFrame/SAMPLES>=MIN_CHANGE_MEAN;
        boolean changed=diff>=MIN_CHANGE_MEAN;
        boolean rise=changed&&!active;
        boolean returned=!changed&&active;
        active=changed;
        return new Signal(changed,rise,returned,movedOrChanged,diff);
    }

    private int sample(FastCardVisualTracker.Pixels p,int col,int row) {
        int px=roi.x+1+((roi.width-2)*col)/(COLS-1);
        int py=roi.y+1+((roi.height-2)*row)/(ROWS-1);
        return p.luminance(px,py);
    }

    public synchronized void reset() {
        Arrays.fill(reference,0);
        Arrays.fill(previous,0);
        armed=false;active=false;roi=null;lastAt=-1;
    }

    public synchronized boolean isArmed(){return armed;}
}
