package com.vexo.reader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.projection.MediaProjectionManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Native implementation of the VEXO LAB HUD, not a WebView or fake DOM reader. */
public final class MainActivity extends Activity {
    private static final int REQUEST_SCREEN = 7001;
    private static final int BG = 0xFF090B10;
    private static final int PANEL = 0xFF14181F;
    private static final int WHITE = 0xFFF4F7FC;
    private static final int MUTED = 0xFF9BA5B5;
    private static final int GREEN = 0xFF00EB79;
    private static final int CYAN = 0xFF06DDF2;
    private static final int ORANGE = 0xFFFFA024;

    private final Handler uiHandler = new Handler(Looper.getMainLooper());
    private RideDb db;
    private TextView status, frames, latency, roi, active, price, origin, destination, rating, count;
    private LinearLayout history;
    private long lastListedId = -1;
    private final Runnable refreshLoop = new Runnable() {
        @Override public void run() {
            refresh();
            uiHandler.postDelayed(this, 900);
        }
    };

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        db = new RideDb(this);
        buildScreen();
    }

    private void buildScreen() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout root = vertical();
        root.setPadding(dp(16), dp(16), dp(16), dp(28));
        scroll.addView(root);
        setContentView(scroll);

        TextView headline = text("VEXO LAB  [A7]  •  LEITOR DE ROI", 18, CYAN, true);
        root.addView(headline);
        TextView subhead = text("CAPTURA LOCAL  /  GOOGLE ML KIT", 11, MUTED, true);
        root.addView(subhead);
        space(root, 18);

        LinearLayout controls = horizontal();
        Button start = button("INICIAR LEITURA", GREEN, 0xFF082016);
        Button stop = button("PARAR", 0xFF3B414C, WHITE);
        controls.addView(start, new LinearLayout.LayoutParams(0, dp(50), 2));
        LinearLayout.LayoutParams stopP = new LinearLayout.LayoutParams(0, dp(50), 1);
        stopP.leftMargin = dp(8);
        controls.addView(stop, stopP);
        root.addView(controls);
        start.setOnClickListener(v -> askScreenConsent());
        stop.setOnClickListener(v -> {
            stopService(new Intent(this, ScreenReadService.class));
            ScreenState.active = false;
            ScreenState.invalidate("Captura interrompida pelo motorista");
            refresh();
        });

        TextView notice = text(
            "O Android pedirá autorização. Escolha a tela ou o aplicativo que quer ler. " +
            "A leitura não toca nos botões da 99 e não transforma oferta em corrida concluída.",
            12, MUTED, false);
        notice.setPadding(0, dp(12), 0, dp(14));
        root.addView(notice);

        LinearLayout monitor = vertical();
        monitor.setPadding(dp(14), dp(14), dp(14), dp(14));
        monitor.setBackground(box(PANEL, CYAN, 18, 1));
        root.addView(monitor);
        monitor.addView(text("MONITOR DE ROI  •  DIAGNÓSTICO REAL", 13, CYAN, true));
        space(monitor, 12);
        status = text("Captura desligada", 15, WHITE, true);
        monitor.addView(status);
        frames = text("FRAMES RECEBIDOS: —", 12, GREEN, false);
        monitor.addView(frames);
        latency = text("OCR CONCLUÍDOS: —", 12, ORANGE, false);
        monitor.addView(latency);
        roi = text("ROI: parte inferior da tela", 12, MUTED, false);
        monitor.addView(roi);
        space(root, 18);

        TextView section = text("TRACKING:  CARD / OFERTA", 13, CYAN, true);
        root.addView(section);
        space(root, 5);
        LinearLayout offer = vertical();
        offer.setPadding(dp(14), dp(17), dp(14), dp(17));
        offer.setBackground(box(0xFF103039, CYAN, 22, 2));
        root.addView(offer);

        active = text("AGUARDANDO CARD", 12, CYAN, true);
        offer.addView(active);
        space(offer, 8);
        offer.addView(text("ROI: PREÇO", 11, GREEN, true));
        price = text("R$ —", 37, WHITE, true);
        price.setPadding(dp(10), dp(4), dp(10), dp(4));
        price.setBackground(box(0xFF193A39, GREEN, 8, 2));
        offer.addView(price);
        space(offer, 10);
        rating = text("⭐ Nota: —", 13, MUTED, false);
        offer.addView(rating);
        space(offer, 16);

        offer.addView(text("ROI: ORIGEM  •  TEMPO / DISTÂNCIA / ENDEREÇO", 10, GREEN, true));
        origin = text("Aguardando OCR...", 15, WHITE, false);
        origin.setPadding(dp(9), dp(8), dp(9), dp(8));
        origin.setBackground(box(0xFF1A3036, GREEN, 9, 1));
        offer.addView(origin);
        space(offer, 10);
        offer.addView(text("ROI: DESTINO  •  TEMPO / DISTÂNCIA / ENDEREÇO", 10, GREEN, true));
        destination = text("Aguardando OCR...", 15, WHITE, false);
        destination.setPadding(dp(9), dp(8), dp(9), dp(8));
        destination.setBackground(box(0xFF1A3036, GREEN, 9, 1));
        offer.addView(destination);
        space(offer, 13);
        offer.addView(text("PRÉVIA. NÃO É UMA OFERTA VALIDADA PELA 99.", 10, ORANGE, true));

        space(root, 20);
        LinearLayout historyHeader = horizontal();
        count = text("OFERTAS OBSERVADAS • 0", 13, GREEN, true);
        historyHeader.addView(count, new LinearLayout.LayoutParams(0, dp(39), 1));
        Button clear = button("APAGAR", 0xFF353740, WHITE);
        historyHeader.addView(clear, new LinearLayout.LayoutParams(dp(105), dp(39)));
        root.addView(historyHeader);
        clear.setOnClickListener(v -> new AlertDialog.Builder(this)
            .setTitle("Apagar histórico local?")
            .setMessage("Isso exclui os dados de ofertas observadas deste aparelho.")
            .setNegativeButton("Cancelar", null)
            .setPositiveButton("Apagar", (d, which) -> {
                db.erase(); lastListedId = -1; refresh();
            }).show());

        history = vertical();
        root.addView(history);
        root.addView(text(
            "Privacidade: não há envio para servidor, acesso à Internet ou salvamento de imagens. " +
            "Somente ofertas estruturadas podem ficar no banco local até serem apagadas.",
            11, MUTED, false));
    }

    private void askScreenConsent() {
        MediaProjectionManager mgr = (MediaProjectionManager)
            getSystemService(MEDIA_PROJECTION_SERVICE);
        startActivityForResult(mgr.createScreenCaptureIntent(), REQUEST_SCREEN);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_SCREEN) return;
        if (resultCode != RESULT_OK || data == null) {
            ScreenState.invalidate("Autorização de captura cancelada");
            refresh();
            return;
        }
        Intent service = new Intent(this, ScreenReadService.class)
            .setAction(ScreenReadService.ACTION_START)
            .putExtra(ScreenReadService.EXTRA_GRANT_RESULT, resultCode)
            .putExtra(ScreenReadService.EXTRA_GRANT_DATA, data);
        startForegroundService(service);
    }

    private void refresh() {
        if (status == null) return;
        boolean receiving = ScreenState.active &&
            SystemClock.elapsedRealtime() - ScreenState.lastFrameAt <= 2000;
        status.setText(ScreenState.status + (ScreenState.active && !receiving
            ? "\nSEM FRAMES ATUAIS — confira qual tela foi autorizada" : ""));
        status.setTextColor(ScreenState.active ? GREEN : ORANGE);
        frames.setText("FRAMES RECEBIDOS: " + ScreenState.receivedFrames +
            (receiving ? "  ● CAPTURA ATIVA" : "  ○ SEM CAPTURA"));
        latency.setText("LEITURAS OCR CONCLUÍDAS: " + ScreenState.ocrCompleted +
            "  •  NÃO É LATÊNCIA MEDIDA");
        roi.setText(ScreenState.roiLabel);

        OfferRecord latest = ScreenState.freshPreview();
        active.setText(latest == null ? "SEM OFERTA ATUAL CONFIRMADA" : "TRACKING: CANDIDATO OBSERVADO");
        price.setText(latest == null ? "R$ —" : latest.price());
        rating.setText(latest == null || latest.rating.isEmpty()
            ? "⭐ Nota: não lida" : "⭐ Nota OCR: " + latest.rating);
        origin.setText(latest == null ? "Sem leitura atual" :
            latest.originMin + " min  •  " + OfferRecord.kilometers(latest.originTenthsKm) +
                "\n" + (latest.origin.isEmpty() ? "Endereço não lido" : latest.origin));
        destination.setText(latest == null ? "Sem leitura atual" :
            latest.destinationMin + " min  •  " +
                OfferRecord.kilometers(latest.destinationTenthsKm) + "\n" +
                (latest.destination.isEmpty() ? "Endereço não lido" : latest.destination));

        List<OfferRecord> items = db.recent(12);
        count.setText("OFERTAS OBSERVADAS • " + items.size() + (items.size() == 12 ? "+" : ""));
        long mostRecent = items.isEmpty() ? 0 : items.get(0).databaseId;
        if (lastListedId == mostRecent) return;
        lastListedId = mostRecent;
        history.removeAllViews();
        if (items.isEmpty()) {
            TextView empty = text("Nenhuma oferta registrada ainda.\nA leitura real começa após sua autorização.", 13, MUTED, false);
            empty.setPadding(0, dp(12), 0, dp(19));
            history.addView(empty);
            return;
        }
        SimpleDateFormat format = new SimpleDateFormat("dd/MM HH:mm:ss", Locale.forLanguageTag("pt-BR"));
        for (OfferRecord r : items) {
            LinearLayout card = vertical();
            card.setPadding(dp(12), dp(11), dp(12), dp(11));
            card.setBackground(box(PANEL, 0xFF2F5A55, 13, 1));
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
            params.bottomMargin = dp(8);
            history.addView(card, params);
            card.addView(text(r.price() + "   ·   " + format.format(new Date(r.seenAt)),
                16, GREEN, true));
            card.addView(text("ORIGEM: " + r.originMin + " min / " +
                OfferRecord.kilometers(r.originTenthsKm) + "  " + r.origin, 12, WHITE, false));
            card.addView(text("DESTINO: " + r.destinationMin + " min / " +
                OfferRecord.kilometers(r.destinationTenthsKm) + "  " + r.destination, 12, MUTED, false));
            card.addView(text("OFERTA CAPTURADA — NÃO CONFIRMA ACEITE OU FINALIZAÇÃO",
                10, ORANGE, true));
        }
    }

    private LinearLayout vertical() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }
    private LinearLayout horizontal() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(android.view.Gravity.CENTER_VERTICAL);
        return l;
    }
    private TextView text(String value, int size, int color, boolean isBold) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(size);
        v.setTextColor(color);
        v.setLineSpacing(dp(2), 1f);
        if (isBold) v.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        return v;
    }
    private Button button(String label, int background, int color) {
        Button b = new Button(this);
        b.setAllCaps(false);
        b.setText(label);
        b.setTextSize(12);
        b.setTextColor(color);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setBackground(box(background, background, 12, 0));
        return b;
    }
    private GradientDrawable box(int bg, int line, int radius, int width) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(bg);
        d.setCornerRadius(dp(radius));
        if (width > 0) d.setStroke(dp(width), line);
        return d;
    }
    private void space(LinearLayout parent, int height) {
        View v = new View(this);
        parent.addView(v, new LinearLayout.LayoutParams(1, dp(height)));
    }
    private int dp(float v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }
    @Override protected void onResume() {
        super.onResume();
        ScreenState.ownUiVisible = true;
        uiHandler.removeCallbacks(refreshLoop);
        uiHandler.post(refreshLoop);
    }
    @Override protected void onPause() {
        ScreenState.ownUiVisible = false;
        uiHandler.removeCallbacks(refreshLoop);
        super.onPause();
    }
    @Override protected void onDestroy() {
        uiHandler.removeCallbacks(refreshLoop);
        db.close();
        super.onDestroy();
    }
}
