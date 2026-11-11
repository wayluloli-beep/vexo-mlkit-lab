package com.vexo.mlkitlab;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.PixelFormat;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Janela flutuante de leitura, de adesão voluntária.
 *
 * - Nunca captura conteúdo nem interage com apps de terceiros.
 * - Nenhum gesto/clique: FLAG_NOT_TOUCHABLE, alpha baixo para permitir
 *   toques atravessando a janela em Android 12+.
 * - FLAG_SECURE protege o próprio resumo contra recaptura pelo MediaProjection.
 * - Mostra somente resumo sintético numérico gerado após duas leituras válidas.
 * - O controlador é usado exclusivamente na thread principal do Android.
 */
final class VexoOfferOverlay {
    static final String PREFS="vexo_live_display";
    static final String OPT_IN="floating_window_enabled";

    private final Context context;
    private final WindowManager wm;
    private View window;
    private TextView title;
    private TextView body;

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

    private int dp(int value) {
        return (int)(value*context.getResources().getDisplayMetrics().density+0.5f);
    }

    private boolean ensureWindow() {
        if(!allowed(context) || wm==null) {
            hide();
            return false;
        }
        if(window!=null) return true;

        LinearLayout root=new LinearLayout(context);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(11),dp(7),dp(11),dp(7));
        GradientDrawable bg=new GradientDrawable();
        bg.setColor(0xff101c28);
        bg.setCornerRadius(dp(13));
        bg.setStroke(dp(1),0xff397a91);
        root.setBackground(bg);
        root.setElevation(dp(3));
        root.setMinimumWidth(dp(160));

        title=new TextView(context);
        title.setTextColor(0xff70ead3);
        title.setTextSize(12);
        title.setTypeface(null,1);
        title.setText("VEXO • LENDO A TELA");
        root.addView(title);

        body=new TextView(context);
        body.setTextColor(Color.WHITE);
        body.setTextSize(12);
        body.setMaxWidth(dp(230));
        body.setMaxLines(3);
        body.setText("Aguardando uma oferta confirmada");
        root.addView(body);

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
        params.x=dp(9);
        params.y=dp(70);
        // Android 12+: janela não confiável só permite passar toques
        // com opacidade do window abaixo do limite de obstrução.
        params.alpha=0.65f;
        params.setTitle("Vexo - informacao sem controle de corrida");
        try {
            wm.addView(root,params);
            window=root;
            return true;
        } catch(RuntimeException ignored) {
            window=null;title=null;body=null;
            return false;
        }
    }

    void searching() {
        if(!ensureWindow()) return;
        title.setText("VEXO • CAPTURA ATIVA");
        body.setText("Aguardando oferta segura");
    }

    void offer(String verifiedSummary) {
        if(!ensureWindow()) return;
        title.setText("VEXO • POSSÍVEL OFERTA");
        // O chamador passa apenas preço, distância e duração já verificados.
        body.setText(verifiedSummary==null?"Confira no app 99":
            verifiedSummary.substring(0,Math.min(verifiedSummary.length(),115)));
    }

    void hide() {
        View v=window;
        window=null;title=null;body=null;
        if(v!=null && wm!=null) {
            try { wm.removeView(v); } catch(RuntimeException ignored) {}
        }
    }
}
