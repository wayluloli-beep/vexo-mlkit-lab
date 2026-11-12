package com.vexo.mlkitlab;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.projection.MediaProjectionConfig;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class ManualVisionActivity extends Activity {
    private static final int CAPTURE_REQUEST = 10;
    private boolean waitingForOverlay;
    private TextView status;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        waitingForOverlay = state != null && state.getBoolean("waitingForOverlay");
        ScrollView screen = new ScrollView(this);
        screen.setFillViewport(true);
        screen.setBackgroundColor(0xff0d141b);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(24), dp(38), dp(24), dp(28));
        screen.addView(content, new ScrollView.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = label("VEXO", 36, 0xff23c6da);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        content.addView(title);
        TextView heading = label("Rastreio ao vivo", 22, 0xfff3f6fa);
        heading.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        content.addView(heading);

        status = label("Autorize a tela inteira. Abra a tela que quer testar e toque em "
            + "Marcar alvo no controle flutuante.", 16, 0xffbbcad7);
        status.setPadding(0, dp(12), 0, dp(24));
        content.addView(status);

        addButton(content, "Iniciar captura", 0xff27c4d8, 0xff061719, this::requestCapture);
        addButton(content, "Parar captura", 0xff273747, 0xfff3f6fa, () -> {
            stopService(new Intent(this, ManualVisionService.class));
            status.setText("Captura parada. Toque em Iniciar captura para começar de novo.");
        });
        setContentView(screen);
    }

    private TextView label(String text, int size, int color) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(size);
        label.setTextColor(color);
        return label;
    }

    private void addButton(LinearLayout content, String label, int color, int textColor,
                           Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(17);
        button.setTextColor(textColor);
        GradientDrawable background = new GradientDrawable();
        background.setColor(color);
        background.setCornerRadius(dp(14));
        button.setBackground(background);
        button.setOnClickListener(view -> action.run());
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(54));
        params.bottomMargin = dp(10);
        content.addView(button, params);
    }

    private void requestCapture() {
        if (Settings.canDrawOverlays(this)) {
            requestProjection();
            return;
        }
        status.setText("Permita que o Vexo apareça sobre outros apps para desenhar o retângulo.");
        try {
            waitingForOverlay = true;
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName())));
        } catch (android.content.ActivityNotFoundException exception) {
            waitingForOverlay = false;
            status.setText("Ative a sobreposição do Vexo nas configurações do Android.");
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (!waitingForOverlay) return;
        waitingForOverlay = false;
        if (Settings.canDrawOverlays(this)) requestProjection();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean("waitingForOverlay", waitingForOverlay);
        super.onSaveInstanceState(state);
    }

    private void requestProjection() {
        MediaProjectionManager manager = getSystemService(MediaProjectionManager.class);
        if (manager == null) {
            status.setText("Captura de tela indisponível neste aparelho.");
            return;
        }
        Intent consent = Build.VERSION.SDK_INT >= 34
            ? manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
            : manager.createScreenCaptureIntent();
        startActivityForResult(consent, CAPTURE_REQUEST);
    }

    @Override protected void onActivityResult(int request, int result, Intent consent) {
        super.onActivityResult(request, result, consent);
        if (request != CAPTURE_REQUEST) return;
        if (result != RESULT_OK || consent == null) {
            status.setText("Captura não autorizada.");
            return;
        }
        Intent start = new Intent(this, ManualVisionService.class)
            .setAction(ManualVisionService.START)
            .putExtra(ManualVisionService.CONSENT, consent);
        try {
            startForegroundService(start);
            status.setText("Abra a tela que quer testar. Use Marcar alvo para contornar um item.");
        } catch (RuntimeException exception) {
            status.setText("O Android não iniciou a captura. Tente autorizar novamente.");
        }
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
