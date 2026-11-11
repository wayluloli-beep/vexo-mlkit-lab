package com.vexo.mlkitlab;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Card da 99 inspirado na referência enviada pelo proprietário:
 * fundo branco, cantos e borda verdes, quatro barras, números grandes
 * e rodapé laranja com 99 e tempo/distância total.
 *
 * A janela só recebe dados numéricos já validados: nunca texto OCR bruto.
 * Sem botões, sem Accessibility e sem tocar na 99.
 */
final class VexoOfferOverlay {
    static final String PREFS="vexo_live_display";
    static final String OPT_IN="floating_window_enabled";

    private static final int GREEN=0xff2fc866;
    private static final int GRAY=0xff9d9d9d;
    private static final int DARK=0xff131313;

    private final Context context;
    private final WindowManager wm;
    private View window;
    private LinearLayout metricsContainer;
    private TextView waiting, perKm, perHour, rating, profit, time, distance;

    VexoOfferOverlay(Context context) {
        this.context=context.getApplicationContext();
        wm=(WindowManager)this.context.getSystemService(Context.WINDOW_SERVICE);
    }

    static boolean optedIn(Context context) {
        return context.getSharedPreferences(PREFS,Context.MODE_PRIVATE)
            .getBoolean(OPT_IN,false);
    }

    static void setOptIn(Context context,boolean enabled) {
        SharedPreferences prefs=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
        prefs.edit().putBoolean(OPT_IN,enabled).apply();
    }

    static boolean allowed(Context context) {
        return Build.VERSION.SDK_INT>=26 &&
            optedIn(context) && Settings.canDrawOverlays(context);
    }

    private int dp(float n) {
        return (int)(n*context.getResources().getDisplayMetrics().density+0.5f);
    }

    private GradientDrawable round(int color,int radius) {
        GradientDrawable g=new GradientDrawable();
        g.setColor(color);g.setCornerRadius(dp(radius));
        return g;
    }

    private TextView text(String text,float sp,int color,boolean bold) {
        TextView t=new TextView(context);
        t.setText(text);t.setTextColor(color);t.setTextSize(sp);
        if(bold) t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        t.setIncludeFontPadding(false);
        return t;
    }

    private LinearLayout metricRow(LinearLayout parent,String initial,String suffix,boolean disabled) {
        LinearLayout row=new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams rowParams=new LinearLayout.LayoutParams(-1,dp(41));
        parent.addView(row,rowParams);
        View marker=new View(context);
        marker.setBackground(round(disabled?0xffd2d2d2:GREEN,4));
        LinearLayout.LayoutParams markParams=new LinearLayout.LayoutParams(dp(5),dp(27));
        markParams.rightMargin=dp(9);
        row.addView(marker,markParams);

        LinearLayout values=new LinearLayout(context);
        values.setOrientation(LinearLayout.HORIZONTAL);
        values.setGravity(Gravity.BASELINE);
        row.addView(values);
        TextView big=text(initial,25,DARK,true);
        values.addView(big);
        TextView unit=text(suffix,14,GRAY,false);
        LinearLayout.LayoutParams up=new LinearLayout.LayoutParams(-2,-2);
        up.leftMargin=dp(3);
        values.addView(unit,up);
        // Campos instanciados em ordem, sem guardar valores sensíveis no disco.
        if(perKm==null) perKm=big;
        else if(perHour==null) perHour=big;
        else if(rating==null) rating=big;
        else profit=big;
        return row;
    }

    private boolean ensureWindow() {
        if(!allowed(context) || wm==null) {hide();return false;}
        if(window!=null) return true;

        LinearLayout root=new LinearLayout(context);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(11),dp(8),dp(11),dp(9));
        GradientDrawable bg=round(Color.WHITE,15);
        bg.setStroke(dp(3),GREEN);
        root.setBackground(bg);
        root.setMinimumWidth(dp(205));
        root.setElevation(dp(3));

        waiting=text("VEXO • aguardando oferta",12,0xff238e52,true);
        root.addView(waiting,new LinearLayout.LayoutParams(-2,dp(29)));

        metricsContainer=new LinearLayout(context);
        metricsContainer.setOrientation(LinearLayout.VERTICAL);
        metricsContainer.setVisibility(View.GONE);
        root.addView(metricsContainer);
        metricRow(metricsContainer,"—","/km",false);
        metricRow(metricsContainer,"—","/hr",false);
        metricRow(metricsContainer,"—","★",false);
        metricRow(metricsContainer,"—","lucro",true);

        LinearLayout footer=new LinearLayout(context);
        footer.setOrientation(LinearLayout.HORIZONTAL);
        footer.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams footerParams=new LinearLayout.LayoutParams(-1,dp(40));
        footerParams.topMargin=dp(3);
        metricsContainer.addView(footer,footerParams);

        TextView orange=text("99",17,0xff260c00,true);
        orange.setGravity(Gravity.CENTER);
        orange.setBackground(round(0xffff9a3b,5));
        LinearLayout.LayoutParams op=new LinearLayout.LayoutParams(dp(34),dp(31));
        op.rightMargin=dp(8);
        footer.addView(orange,op);
        time=text("—",16,DARK,true);
        footer.addView(time);
        TextView sep=text("  ·  ",15,GRAY,true);
        footer.addView(sep);
        distance=text("—",16,DARK,true);
        footer.addView(distance);

        WindowManager.LayoutParams params=new WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE |
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE |
                WindowManager.LayoutParams.FLAG_SECURE |
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT);
        params.gravity=Gravity.TOP|Gravity.END;
        params.x=dp(9);params.y=dp(75);
        // Android 12+ limita janelas não confiáveis ao passar toques.
        params.alpha=0.76f;
        params.setTitle("Vexo - indicadores de oferta, sem botoes");
        try {
            wm.addView(root,params);
            window=root;
            return true;
        } catch(RuntimeException ignored) {
            window=null;metricsContainer=null;waiting=null;
            perKm=null;perHour=null;rating=null;profit=null;time=null;distance=null;
            return false;
        }
    }

    void searching() {
        if(!ensureWindow()) return;
        waiting.setVisibility(View.VISIBLE);
        metricsContainer.setVisibility(View.GONE);
    }

    void offer(VexoOverlaySummary.Metrics numbers) {
        if(numbers==null || !numbers.valid) {searching();return;}
        if(!ensureWindow()) return;
        waiting.setVisibility(View.GONE);
        metricsContainer.setVisibility(View.VISIBLE);
        perKm.setText(numbers.perKm);
        perHour.setText(numbers.perHour);
        rating.setText(numbers.rating);
        profit.setText(numbers.profit); // “—”: lucro precisa de custo configurado
        time.setText(numbers.totalTime);
        distance.setText(numbers.totalKm);
    }

    void hide() {
        View old=window;
        window=null;metricsContainer=null;waiting=null;
        perKm=null;perHour=null;rating=null;profit=null;time=null;distance=null;
        if(old!=null && wm!=null) {
            try { wm.removeView(old); } catch(RuntimeException ignored) {}
        }
    }
}
