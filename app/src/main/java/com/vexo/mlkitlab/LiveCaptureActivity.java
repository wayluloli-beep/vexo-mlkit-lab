package com.vexo.mlkitlab;

import android.app.Activity;
import android.os.Build;
import android.Manifest;
import android.content.pm.PackageManager;
import android.content.Intent;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.media.projection.MediaProjectionManager;
import android.os.Bundle;
import android.provider.Settings;
import android.net.Uri;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.view.Gravity;

/**
 * Entrada explícita para uma única sessão de compartilhamento de tela.
 * Não tenta contornar o diálogo nativo nem recuperar uma autorização anterior.
 */
public final class LiveCaptureActivity extends Activity {
    private static final int REQUEST_CAPTURE=401;
    private TextView info, liveState;
    private Button overlayToggle;
    private boolean pendingOverlayPermission=false;
    private boolean asking=false;
    private boolean demoAfterConsent=false;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(38,48,38,40);
        root.setBackgroundColor(0xff0b1018);
        TextView heading=new TextView(this);
        heading.setText("VEXO  •  Captura experimental");
        heading.setTextColor(Color.WHITE);
        heading.setTextSize(23);
        root.addView(heading);
        // CTA fica acima dos textos longos e do status, acessível no
        // primeiro viewport de telas pequenas e nos testes UIAutomator.
        // Fluxo de laboratório explícito: após o próprio usuário autorizar,
        // abrir imediatamente o card FICTÍCIO. Evita gastar a primeira
        // inferência lenta do emulador na tela de controles do Vexo.
        Button demoConsent=new Button(this);
        demoConsent.setAllCaps(false);
        demoConsent.setText("Autorizar e testar oferta fictícia");
        root.addView(demoConsent);
        demoConsent.setOnClickListener(v -> requestConsent(true));

        // A janelinha é DESATIVADA por padrão. Não existe permissão
        // silenciosa: o próprio usuário precisa autorizar nas Configurações.
        overlayToggle=new Button(this);
        overlayToggle.setAllCaps(false);
        root.addView(overlayToggle);
        overlayToggle.setOnClickListener(v -> toggleOverlay());
        updateOverlayLabel();

        info=new TextView(this);
        info.setText("O Android pedirá sua autorização para compartilhar a tela. Para a OFERTA FICTÍCIA, escolha 'Tela inteira' ou o próprio Vexo (se disponível). Para um teste futuro na 99, escolha apenas a 99 quando o Android oferecer essa opção. Não compartilhe telas privadas nem teste enquanto dirige. A leitura fica no celular; o motorista decide as corridas.");
        info.setTextColor(0xffb0c6d5);
        info.setTextSize(16);
        LinearLayout.LayoutParams infoLp=new LinearLayout.LayoutParams(-1,-2);
        infoLp.topMargin=28;
        root.addView(info,infoLp);
        liveState=new TextView(this);
        liveState.setTextColor(0xff83e4c4);
        liveState.setTextSize(16);
        LinearLayout.LayoutParams statusLp=new LinearLayout.LayoutParams(-1,-2);
        statusLp.topMargin=20;
        root.addView(liveState,statusLp);

        if(Build.VERSION.SDK_INT>=33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=
                PackageManager.PERMISSION_GRANTED) {
            TextView notice=new TextView(this);
            notice.setText("Para usar o botão PARAR pela notificação, permita avisos do Vexo. Se negar, ainda pode interromper pelo app ou pelo Android.");
            notice.setTextColor(0xffffcf8b);
            notice.setTextSize(14);
            root.addView(notice);
            Button allowNotice=new Button(this);
            allowNotice.setAllCaps(false);
            allowNotice.setText("Habilitar aviso com botão PARAR (opcional)");
            root.addView(allowNotice);
            allowNotice.setOnClickListener(v ->
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},403));
        }

        Button start=new Button(this);
        start.setAllCaps(false);
        start.setText("Autorizar e iniciar leitura de tela");
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);
        lp.topMargin=30;
        root.addView(start,lp);
        start.setOnClickListener(v -> requestConsent(false));

        Button stop=new Button(this);
        stop.setAllCaps(false);
        stop.setText("Parar captura agora");
        root.addView(stop);
        stop.setOnClickListener(v -> {
            Intent stopIntent=new Intent(this,LiveCaptureService.class);
            stopIntent.setAction(LiveCaptureService.ACTION_STOP);
            startService(stopIntent);
            info.setText("Solicitação de parada enviada. Para reiniciar é necessária uma nova autorização.");
        });
        Button demo=new Button(this);
        demo.setAllCaps(false);
        demo.setText("Abrir oferta fictícia para conferir captura");
        root.addView(demo);
        demo.setOnClickListener(v ->
            startActivity(new Intent(this,DemoOfferActivity.class)));

        Button refresh=new Button(this);
        refresh.setAllCaps(false);
        refresh.setText("Atualizar resultado da captura");
        root.addView(refresh);
        refresh.setOnClickListener(v -> liveState.setText(LiveCaptureState.snapshot()));

        Button copyReport=new Button(this);
        copyReport.setAllCaps(false);
        copyReport.setText("Copiar diagnóstico da captura para análise");
        root.addView(copyReport);
        copyReport.setOnClickListener(v -> {
            ClipboardManager clipboard=(ClipboardManager)
                getSystemService(Context.CLIPBOARD_SERVICE);
            if(clipboard==null) {
                info.setText("Área de transferência indisponível neste aparelho.");
                return;
            }
            clipboard.setPrimaryClip(ClipData.newPlainText(
                "Diagnóstico Vexo — sem dados de corridas",
                LiveCaptureState.safeDiagnosticReport()));
            info.setText("Diagnóstico copiado. Cole o JSON no ChatGPT. " +
                "Ele contém apenas contadores de captura/OCR e não contém prints ou dados da corrida.");
        });

        TextView caveat=new TextView(this);
        caveat.setText("Laboratório: nenhuma corrida é aceita/recusada. Uma leitura perfeita de um print não garante precisão em outras corridas. Se a tela estiver protegida pelo Android, não tentaremos contornar o bloqueio.");
        caveat.setTextColor(0xffffcf8b);
        caveat.setTextSize(14);
        LinearLayout.LayoutParams lp2=new LinearLayout.LayoutParams(-1,-2);
        lp2.topMargin=20;
        root.addView(caveat,lp2);
        scroll.addView(root);
        setContentView(scroll);
    }

    @Override protected void onResume() {
        super.onResume();
        if(pendingOverlayPermission) {
            pendingOverlayPermission=false;
            if(Build.VERSION.SDK_INT>=26 && Settings.canDrawOverlays(this)) {
                VexoOfferOverlay.setOptIn(this,true);
                if(info!=null) info.setText(
                    "Janelinha ativada! Ela mostra status da captura e " +
                    "oferta segura quando você iniciar uma nova sessão.");
            }
        }
        updateOverlayLabel();
        if(liveState!=null) liveState.setText(LiveCaptureState.snapshot());
    }

    private void updateOverlayLabel() {
        if(overlayToggle==null) return;
        boolean on=VexoOfferOverlay.allowed(this);
        overlayToggle.setText(on?
            "Desativar janelinha sobre outros apps":
            "Ativar janelinha flutuante (opcional)");
    }

    private void toggleOverlay() {
        if(VexoOfferOverlay.allowed(this)) {
            VexoOfferOverlay.setOptIn(this,false);
            info.setText("Janelinha desativada. Para remover se ainda estiver " +
                "na tela, pare a captura ou volte ao Vexo.");
            updateOverlayLabel();
            return;
        }
        if(Build.VERSION.SDK_INT<26) {
            info.setText("Janelinha experimental requer Android 8 ou superior.");
            return;
        }
        if(Settings.canDrawOverlays(this)) {
            VexoOfferOverlay.setOptIn(this,true);
            info.setText("Janelinha ativada. Inicie a captura normalmente.");
            updateOverlayLabel();
            return;
        }
        pendingOverlayPermission=true;
        info.setText("O Android vai abrir a permissão 'Aparecer sobre outros apps'. " +
            "Autorize o Vexo e volte aqui. Sem essa permissão a captura continua, " +
            "mas sem janelinha.");
        try {
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:"+getPackageName())));
        } catch(Exception ex) {
            pendingOverlayPermission=false;
            info.setText("Não foi possível abrir a configuração da janelinha.");
        }
    }

    private void requestConsent(boolean launchDemo) {
        if(asking) return;
        demoAfterConsent=launchDemo;
        MediaProjectionManager mgr=(MediaProjectionManager)getSystemService(MEDIA_PROJECTION_SERVICE);
        if(mgr==null) {
            info.setText("MediaProjection indisponível neste aparelho.");
            return;
        }
        asking=true;
        try {
            startActivityForResult(mgr.createScreenCaptureIntent(),REQUEST_CAPTURE);
        } catch(Exception e) {
            asking=false;
            info.setText("Não foi possível abrir a autorização do Android.");
        }
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode!=REQUEST_CAPTURE) return;
        asking=false;
        boolean launchDemo=demoAfterConsent;
        demoAfterConsent=false;
        if(resultCode!=RESULT_OK || data==null) {
            info.setText("Permissão de captura não concedida. Nenhuma leitura foi iniciada.");
            return;
        }
        Intent service=new Intent(this,LiveCaptureService.class);
        service.setAction(LiveCaptureService.ACTION_START);
        service.putExtra(LiveCaptureService.EXTRA_RESULT_CODE,resultCode);
        service.putExtra(LiveCaptureService.EXTRA_CONSENT_DATA,data);
        try {
            androidx.core.content.ContextCompat.startForegroundService(this,service);
            info.setText("Sessão solicitada. Para parar, volte aqui ou use a notificação do Vexo.");
            if(launchDemo) {
                // Teste local, não abre nem controla 99/Uber e não reutiliza token.
                startActivity(new Intent(this,DemoOfferActivity.class));
            }
        } catch(Exception e) {
            info.setText("Falha ao iniciar o serviço de captura; nenhuma permissão será guardada.");
        }
    }
}
