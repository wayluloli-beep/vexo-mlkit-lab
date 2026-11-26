package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import com.vexo.mlkitlab.FastCardVisualTracker.Pixels;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.Core;
import org.opencv.core.CvType;
import org.opencv.core.Mat;
import org.opencv.imgproc.Imgproc;
import java.util.Locale;

/** Shadow benchmark only. A pixel match is not proof of a live offer. */
final class OpenCvProbe {
    private Mat template;
    private int step, width, height;
    private Boolean loaded;

    boolean arm(Pixels p,Box box) {
        clear();
        if(box==null || box.width<24 || box.height<24) return false;
        try {
            if(loaded==null) loaded=OpenCVLoader.initLocal();
            if(!loaded) return false;
            step=Math.max(1,(Math.max(box.width,box.height)+127)/128);
            width=box.width/step; height=box.height/step;
            if(width<8||height<8) return false;
            template=sample(p,box.x,box.y,width,height);
            Core.MinMaxLocResult mm=Core.minMaxLoc(template);
            if(mm.maxVal-mm.minVal<25){clear();return false;}
            return true;
        } catch(RuntimeException|LinkageError e){clear();return false;}
    }

    Match inspect(Pixels p,Box last) {
        long t=android.os.SystemClock.elapsedRealtimeNanos();
        if(template==null||last==null) return new Match(Double.NaN,null,0);
        Mat search=null,result=null;
        try {
            int margin=Math.min(160,Math.max(36,(last.width+last.height)/4));
            int x=Math.max(0,last.x-margin),y=Math.max(0,last.y-margin);
            int right=Math.min(p.width(),last.x+last.width+margin);
            int bottom=Math.min(p.height(),last.y+last.height+margin);
            int cols=(right-x)/step,rows=(bottom-y)/step;
            if(cols<width||rows<height) return new Match(Double.NaN,null,0);
            search=sample(p,x,y,cols,rows);result=new Mat();
            Imgproc.matchTemplate(search,template,result,Imgproc.TM_CCOEFF_NORMED);
            Core.MinMaxLocResult mm=Core.minMaxLoc(result);
            Box hit=Double.isFinite(mm.maxVal)&&mm.maxVal>=0.77
                ?new Box(x+(int)mm.maxLoc.x*step,y+(int)mm.maxLoc.y*step,width*step,height*step):null;
            return new Match(mm.maxVal,hit,(android.os.SystemClock.elapsedRealtimeNanos()-t)/1e6);
        } catch(RuntimeException|LinkageError e){return new Match(Double.NaN,null,0);}
        finally{if(search!=null)search.release();if(result!=null)result.release();}
    }

    private Mat sample(Pixels p,int x,int y,int cols,int rows) {
        byte[] bytes=new byte[cols*rows];
        for(int r=0;r<rows;r++)for(int c=0;c<cols;c++)
            bytes[r*cols+c]=(byte)p.luminance(x+c*step,y+r*step);
        Mat m=new Mat(rows,cols,CvType.CV_8UC1);
        m.put(0,0,bytes);return m;
    }
    void clear(){if(template!=null){template.release();template=null;}}
    static final class Match {
        final double score,ms;final Box hit;
        Match(double s,Box b,double m){score=s;hit=b;ms=m;}
        String describe(Box baseline){
            if(!Double.isFinite(score))return "CV: indisponível";
            boolean agrees=false;
            if(hit!=null&&baseline!=null){
                int x=Math.max(0,Math.min(hit.x+hit.width,baseline.x+baseline.width)-Math.max(hit.x,baseline.x));
                int y=Math.max(0,Math.min(hit.y+hit.height,baseline.y+baseline.height)-Math.max(hit.y,baseline.y));
                double inter=(double)x*y,union=(double)hit.width*hit.height+(double)baseline.width*baseline.height-inter;
                agrees=union>0&&inter/union>=0.75;
            }
            return String.format(Locale.ROOT,"CV %.2f · %.1f ms · %s",score,ms,agrees?"acordo":hit!=null?"divergência":"sem match");
        }
    }
}
