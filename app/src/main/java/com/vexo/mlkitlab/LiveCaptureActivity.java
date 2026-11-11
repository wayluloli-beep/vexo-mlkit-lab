package com.vexo.mlkitlab;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.media.projection.MediaProjectionManager;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.view.Gravity;

/**
 * Entrada explícita para uma única sessão de compartilhamento de tela.
 * Não tenta contornar o diálogo nativo nem recuperar uma autorização anterior.
 */
public final class LiveCaptureActivity extends Activity {
    private static final int REQUEST_CAPTURE=401;
    private TextView info;
    private boolean asking=false;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(38,48,38,40);
        root.setBackgroundColor(0xff0b1018);
        TextView heading=new TextView(this);
        heading.setText("VEXO  •  Captura experimental");
        heading.setTextColor(Color.WHITE);
        heading.setTextSize(23);
        root.addView(heading);
        info=new TextView(this);
        info.setText("O Android vai pedir sua autorização. Se possível, selecione SOMENTE o aplicativo 99. Durante a sessão o Vexo lê pixels na memória, sem salvar imagens ou texto bruto. O motorista continua responsável por todas as decisões.");
        info.setTextColor(0xffb0c6d5);
        info.setTextSize(16);
        LinearLayout.LayoutParams infoLp=new LinearLayout.LayoutParams(-1,-2);
        infoLp.topMargin=28;
        root.addView(info,infoLp);

        Button start=new Button(this);
        start.setAllCaps(false);
        start.setText("Autorizar e iniciar leitura de tela");
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);
        lp.topMargin=30;
        root.addView(start,lp);
        start.setOnClickListener(v -> requestConsent());

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
        TextView caveat=new TextView(this);
        caveat.setText("Laboratório: nenhuma corrida é aceita/recusada. Uma leitura perfeita de um print não garante precisão em outras corridas. Se a tela estiver protegida pelo Android, não tentaremos contornar o bloqueio.");
        caveat.setTextColor(0xffffcf8b);
        caveat.setTextSize(14);
        LinearLayout.LayoutParams lp2=new LinearLayout.LayoutParams(-1,-2);
        lp2.topMargin=20;
        root.addView(caveat,lp2);
        setContentView(root);
    }

    private void requestConsent() {
        if(asking) return;
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
            info.setText("Autorização recebida. Sessão local solicitada. Volte à 99 pelo seletor de apps. Para parar, volte aqui ou use a notificação persistente do Vexo.");
        } catch(Exception e) {
            info.setText("Falha ao iniciar o serviço de captura; nenhuma permissão será guardada.");
        }
    }
}
