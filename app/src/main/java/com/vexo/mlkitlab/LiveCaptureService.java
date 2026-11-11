package com.vexo.mlkitlab;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.Context;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import com.google.android.gms.tasks.Task;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.nio.ByteBuffer;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Laboratório local MediaProjection. Nunca persiste pixels, tokens, OCR bruto,
 * endereços ou recortes, nem interage com botões da 99. O motorista decide.
 */
public final class LiveCaptureService extends Service {
    public static final String ACTION_START="com.vexo.mlkitlab.START_CAPTURE";
    public static final String ACTION_STOP="com.vexo.mlkitlab.STOP_CAPTURE";
    public static final String EXTRA_RESULT_CODE="consent_result_code";
    public static final String EXTRA_CONSENT_DATA="consent_data";
    private static final String CHANNEL="vexo_capture_status";
    private static final int NOTIFICATION_ID=812;
    private static final long FRAME_INTERVAL_MS=1400; // ~0.7 inferência/s no máximo

    private final AtomicLong epoch=new AtomicLong(0);
    // Serializa STOP e publicação de resultado: nenhuma notificação após onStop.
    private final Object sessionLock=new Object();
    private boolean cleanupDone=false; // usado apenas no thread principal
    private final Handler main=new Handler(Looper.getMainLooper());
    private HandlerThread captureThread;
    private Handler captureHandler;
    private MediaProjection projection;
    private VirtualDisplay virtualDisplay;
    private ImageReader imageReader;
    private TextRecognizer recognizer;
    private CaptureThrottle gate;
    private int width,height,densityDpi;
    private volatile boolean active=false;
    private volatile boolean stopping=false;
    private volatile boolean capturedVisible=true;
    private long seen=0,read=0;
    private final OfferEpisodeGate episodes=new OfferEpisodeGate();

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        if(nm!=null && Build.VERSION.SDK_INT>=26) {
            NotificationChannel channel=new NotificationChannel(CHANNEL,
                "Vexo — leitura autorizada de tela",NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Sessão de captura ativa com opção de parada");
            nm.createNotificationChannel(channel);
        }
    }

    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        if(intent==null) return START_NOT_STICKY;
        String action=intent.getAction();
        if(ACTION_STOP.equals(action)) {
            shutdown();
            return START_NOT_STICKY;
        }
        if(!ACTION_START.equals(action)) return START_NOT_STICKY;
        if(active || stopping) return START_NOT_STICKY;

        int result=intent.getIntExtra(EXTRA_RESULT_CODE,0);
        Intent consent;
        if(Build.VERSION.SDK_INT>=33) {
            consent=intent.getParcelableExtra(EXTRA_CONSENT_DATA,Intent.class);
        } else {
            consent=intent.getParcelableExtra(EXTRA_CONSENT_DATA);
        }
        if(result!=android.app.Activity.RESULT_OK || consent==null) {
            LiveCaptureState.end("Autorização de captura inválida.");
            stopSelf();
            return START_NOT_STICKY;
        }

        // Obrigatório promover a foreground APÓS consentimento, ANTES de getMediaProjection.
        try {
            if(Build.VERSION.SDK_INT>=29) {
                startForeground(NOTIFICATION_ID,notification(false),
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
            } else {
                startForeground(NOTIFICATION_ID,notification(false));
            }
            initiate(result,consent);
        } catch(Exception ex) {
            LiveCaptureState.end("Não foi possível iniciar o serviço de captura.");
            shutdown();
        }
        return START_NOT_STICKY; // nunca ressuscitar sessão/token após kill
    }

    private Notification notification(boolean offerDetected) {
        Intent launch=new Intent(this,LiveCaptureActivity.class);
        PendingIntent open=PendingIntent.getActivity(this,0,launch,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Intent quit=new Intent(this,LiveCaptureService.class).setAction(ACTION_STOP);
        PendingIntent stop=PendingIntent.getService(this,1,quit,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b=Build.VERSION.SDK_INT>=26?
            new Notification.Builder(this,CHANNEL):new Notification.Builder(this);
        return b.setContentTitle(offerDetected?"Vexo: confira uma possível oferta":"Vexo: leitura de tela ativa")
            .setContentText(offerDetected?"Abra o Vexo para conferir. Não há aceitação automática.":
                "Processando somente na memória. Toque para parar.")
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(open)
            .addAction(new Notification.Action.Builder(
                android.R.drawable.ic_media_pause,"PARAR",stop).build())
            .build();
    }

    private void initiate(int resultCode,Intent consent) {
        if(active) return;
        long session=epoch.incrementAndGet();
        stopping=false;
        capturedVisible=true;
        seen=0;read=0;episodes.reset();
        gate=new CaptureThrottle(FRAME_INTERVAL_MS);
        captureThread=new HandlerThread("vexo-frame-processor");
        captureThread.start();
        captureHandler=new Handler(captureThread.getLooper());
        recognizer=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        WindowManager wm=(WindowManager)getSystemService(WINDOW_SERVICE);
        DisplayMetrics dm=getResources().getDisplayMetrics();
        densityDpi=Math.max(1,dm.densityDpi);
        int requestedWidth,requestedHeight;
        if(Build.VERSION.SDK_INT>=30 && wm!=null) {
            Rect bounds=wm.getMaximumWindowMetrics().getBounds();
            requestedWidth=bounds.width();
            requestedHeight=bounds.height();
        } else {
            requestedWidth=dm.widthPixels;
            requestedHeight=dm.heightPixels;
        }
        int[] fitted=CaptureDimensions.fit(requestedWidth,requestedHeight);
        width=fitted[0];height=fitted[1];

        MediaProjectionManager mgr=(MediaProjectionManager)
            getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        if(mgr==null) throw new IllegalStateException("MediaProjection indisponível");
        // Token de sessão consumido UMA ÚNICA vez. Não guardar em SharedPreferences.
        projection=mgr.getMediaProjection(resultCode,consent);
        if(projection==null) throw new IllegalStateException("Nenhuma projeção disponível");

        projection.registerCallback(new MediaProjection.Callback() {
            @Override public void onStop() {
                // Importante: callback roda fora da main. Invalidar a sessão
                // AGORA, não esperar a mensagem de cleanup na fila principal.
                invalidateStoppedSession(session);
            }
            @Override public void onCapturedContentResize(int w,int h) {
                if(Build.VERSION.SDK_INT>=34 && w>0 && h>0) {
                    Handler hnd=captureHandler;
                    if(hnd!=null) hnd.post(() -> resize(session,w,h));
                }
            }
            @Override public void onCapturedContentVisibilityChanged(boolean visible) {
                if(Build.VERSION.SDK_INT>=34) {
                    capturedVisible=visible;
                    LiveCaptureState.capturedContentVisibility(visible);
                }
            }
        },captureHandler);

        imageReader=ImageReader.newInstance(width,height,PixelFormat.RGBA_8888,3);
        imageReader.setOnImageAvailableListener(reader -> consumeFrame(reader,session),captureHandler);
        // Exatamente UMA createVirtualDisplay por novo consentimento, inclusive rotação.
        virtualDisplay=projection.createVirtualDisplay("Vexo local consented capture",
            width,height,densityDpi,DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader.getSurface(),null,captureHandler);
        if(virtualDisplay==null) throw new IllegalStateException("Display virtual indisponível");
        synchronized(sessionLock) {
            if(stopping || epoch.get()!=session)
                throw new IllegalStateException("Projeção encerrada antes do primeiro frame");
            active=true;
            // Não anunciar 'captura ativa' antes do display existir de fato.
            LiveCaptureState.begin();
        }
    }

    private void invalidateStoppedSession(long session) {
        synchronized(sessionLock) {
            if(epoch.get()!=session) return;
            stopping=true;
            active=false;
            capturedVisible=false;
            epoch.incrementAndGet(); // callback OCR da sessão antiga é inválido
            episodes.reset();
            LiveCaptureState.end("Captura encerrada pelo Android.");
        }
        main.post(this::shutdown); // cleanup é idempotente, independente do guard
    }

    private void resize(long session,int w,int h) {
        if(!active || epoch.get()!=session || virtualDisplay==null) return;
        if(w==width && h==height) return;
        ImageReader replacement=null;
        try {
            int[] fitted=CaptureDimensions.fit(w,h);
            w=fitted[0];h=fitted[1];
            if(w==width && h==height) return;
            replacement=ImageReader.newInstance(w,h,PixelFormat.RGBA_8888,3);
            final ImageReader newReader=replacement;
            newReader.setOnImageAvailableListener(r -> consumeFrame(r,session),captureHandler);
            virtualDisplay.resize(w,h,densityDpi);
            virtualDisplay.setSurface(newReader.getSurface()); // sem segunda createVirtualDisplay
            ImageReader old=imageReader;
            imageReader=newReader;
            replacement=null; // ownership do novo reader foi transferido
            width=w;height=h;
            if(old!=null) old.close();
            episodes.reset();
        } catch(Exception ex) {
            // Se resize/setSurface falhar antes de transferir ownership,
            // liberar o reader provisório que shutdown() ainda não conhece.
            if(replacement!=null) {
                try { replacement.close(); } catch(Exception ignored) {}
            }
            invalidateStoppedSession(session);
        }
    }

    private void consumeFrame(ImageReader reader,long session) {
        Image image=null;
        Bitmap pixels=null;
        boolean started=false;
        final CaptureThrottle localGate=gate;
        try {
            image=reader.acquireLatestImage(); // joga fora imagens antigas
            if(image==null || !active || stopping ||
                epoch.get()!=session || localGate==null) return;
            seen++;
            LiveCaptureState.frameReceived(); // contar pixels chegando antes da pausa
            if(!capturedVisible) return;
            started=localGate.begin(SystemClock.elapsedRealtime());
            if(!started) return; // só uma inferência em andamento
            pixels=extract(image);
        } catch(Exception ex) {
            if(started && localGate!=null) localGate.finish();
            if(pixels!=null) pixels.recycle();
            return;
        } finally {
            if(image!=null) image.close(); // cada frame liberação garantida
        }
        if(pixels==null) {
            if(started) localGate.finish();
            return;
        }
        final Bitmap frame=pixels;
        if(epoch.get()!=session || !active) {
            localGate.finish();frame.recycle();return;
        }
        final long startedAt=SystemClock.elapsedRealtime();
        try {
            LiveCaptureState.ocrAttempted();
            Task<Text> task=recognizer.process(InputImage.fromBitmap(frame,0));
            task.addOnCompleteListener(done -> {
                try {
                    if(active && !stopping && epoch.get()==session) {
                        LiveCaptureState.ocrLatency(
                            Math.max(0, SystemClock.elapsedRealtime()-startedAt));
                    }
                    if(done.isSuccessful() && active && !stopping &&
                        epoch.get()==session && capturedVisible) {
                        read++;
                        LiveCaptureState.ocrCompleted();
                        evaluate(done.getResult().getText(),session);
                    } else if(!done.isSuccessful() && active &&
                        !stopping && epoch.get()==session) {
                        LiveCaptureState.ocrFailed();
                    }
                } finally {
                    frame.recycle();
                    localGate.finish(); // gate por SESSÃO; callback antigo não libera o novo
                }
            });
        } catch(Exception ex) {
            if(active && !stopping && epoch.get()==session)
                LiveCaptureState.ocrLatency(
                    Math.max(0,SystemClock.elapsedRealtime()-startedAt));
            LiveCaptureState.ocrFailed();
            frame.recycle();
            localGate.finish();
        }
    }

    private static Bitmap extract(Image image) {
        if(image.getPlanes().length==0) return null;
        Image.Plane plane=image.getPlanes()[0];
        ByteBuffer buffer=plane.getBuffer().duplicate();
        buffer.rewind();
        int stride=plane.getRowStride();
        int pixelStride=plane.getPixelStride();
        int w=image.getWidth(),h=image.getHeight();
        if(pixelStride!=4 || w<=0 || h<=0 || stride<4*w) return null;
        int paddedW=stride/pixelStride;
        if(paddedW<w || paddedW>8192 || h>8192) return null;
        Bitmap full=Bitmap.createBitmap(paddedW,h,Bitmap.Config.ARGB_8888);
        Bitmap result=null;
        boolean ready=false;
        try {
            full.copyPixelsFromBuffer(buffer);
            result=Bitmap.createBitmap(full,0,0,w,h);
            // Bitmap.createBitmap pode retornar A MESMA instância quando não
            // existe padding. Não reciclar o bitmap que o ML Kit vai usar.
            if(w>1080) {
                int newH=Math.max(1,Math.round(h*(1080f/w)));
                Bitmap scaled=Bitmap.createScaledBitmap(result,1080,newH,true);
                if(scaled!=result) {
                    if(result!=full) result.recycle();
                    result=scaled;
                }
            }
            ready=true;
            return result;
        } finally {
            // Uma exceção durante createScaledBitmap não pode reter o crop.
            // Em sucesso, result permanece vivo até a conclusão do ML Kit.
            if(!ready && result!=null && result!=full) result.recycle();
            if(!ready || full!=result) full.recycle();
        }
    }

    private boolean sessionAlive(long session) {
        return active && !stopping && capturedVisible && epoch.get()==session;
    }

    /**
     * Só mapa/histórico/post CONFIRMADOS encerram episódio.
     * Overlay, OCR parcial ou FinancialGuard inseguro: ocultar sugestão
     * financeira, mas não criar falsamente uma segunda oferta.
     */
    private void markFrameUnusable(long session,boolean definitelyNoOffer) {
        synchronized(sessionLock) {
            if(!sessionAlive(session)) return;
            boolean closed;
            if(definitelyNoOffer) closed=episodes.nonOffer();
            else {
                episodes.uncertain();
                closed=true; // esconder o último valor para não parecer atual
            }
            if(closed) {
                LiveCaptureState.clearCandidate();
                NotificationManager nm=(NotificationManager)getSystemService(
                    NOTIFICATION_SERVICE);
                if(nm!=null) nm.notify(NOTIFICATION_ID,notification(false));
            }
        }
    }

    private void evaluate(String text,long session) {
        ScreenContextClassifier.Kind context=
            ScreenContextClassifier.classify(text==null?"":text);
        if(context!=ScreenContextClassifier.Kind.OFFER_CANDIDATE ||
            text==null || !text.contains("99")) {
            boolean definitelyNoOffer=
                context==ScreenContextClassifier.Kind.MAP_WITHOUT_OFFER ||
                context==ScreenContextClassifier.Kind.COMPLETED_TRIP ||
                context==ScreenContextClassifier.Kind.ARCHIVED_OFFER_SCREENSHOT ||
                context==ScreenContextClassifier.Kind.SOCIAL_POST_WITH_SCREENSHOT;
            LiveCaptureState.rejectedContext(!definitelyNoOffer);
            markFrameUnusable(session,definitelyNoOffer);
            return;
        }
        LiveCaptureState.classifiedOffer();
        OfferParser.Offer offer=OfferParser.parse(text);
        if(!FinancialGuard.assess(offer).canCalculate) {
            LiveCaptureState.rejectedFinance();
            markFrameUnusable(session,false);
            return;
        }
        String price=offer.get("offerPrice");
        String trip=offer.get("tripKm");
        String duration=offer.get("tripMin");
        String pickup=offer.get("pickupKm");
        if(price.isEmpty()||trip.isEmpty()||duration.isEmpty()||pickup.isEmpty()) {
            LiveCaptureState.rejectedFinance();
            markFrameUnusable(session,false);
            return;
        }
        String fingerprint=String.join("|",offer.get("offerType"),price,trip,
            duration,pickup,offer.get("pickupMin")); // apenas RAM
        // A interrupção e a publicação usam o MESMO lock para impedir que
        // uma conclusão atrasada publique depois do STOP.
        synchronized(sessionLock) {
            if(!sessionAlive(session)) return;
            // O mesmo card pode ficar 30+ frames visível: alertar UMA vez.
            // Quando mapa/outro contexto aparece por dois frames, um novo card
            // com os mesmos valores também pode ser notificado.
            boolean newEpisode=episodes.observe(fingerprint);
            if(!sessionAlive(session)) return;
            String summary="Preço R$"+price+" • viagem "+trip+
                " km / "+duration+" min (confira na tela)";
            if(!newEpisode) {
                LiveCaptureState.awaitingConfirmation();
                if(episodes.consumeRestoredSummary()) {
                    // Restauração é apenas UI. Nunca emitir notificação de
                    // nova oferta após dois frames estáveis da mesma corrida.
                    LiveCaptureState.restoreCandidate(summary);
                }
                return;
            }
            LiveCaptureState.candidate(summary);
            // Notificação sem valores, nomes ou endereços do passageiro.
            NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
            if(nm!=null) nm.notify(NOTIFICATION_ID,notification(true));
        }
    }

    private void shutdown() {
        if(cleanupDone) return; // cleanup na thread principal, uma vez por Service
        cleanupDone=true;
        synchronized(sessionLock) {
            stopping=true;
            active=false;
            capturedVisible=false;
            epoch.incrementAndGet(); // bloqueia callbacks antes de liberar recursos
            episodes.reset();
            LiveCaptureState.end("Captura parada. Uma nova sessão exige autorização.");
        }
        final CaptureThrottle prev=gate;
        gate=null;
        if(prev!=null) prev.reset();
        try { if(virtualDisplay!=null) virtualDisplay.release(); } catch(Exception ignored) {}
        virtualDisplay=null;
        try {
            if(imageReader!=null) {
                imageReader.setOnImageAvailableListener(null,null);
                imageReader.close();
            }
        } catch(Exception ignored) {}
        imageReader=null;
        MediaProjection previous=projection;
        projection=null;
        if(previous!=null) {
            try {previous.stop();} catch(Exception ignored) {}
        }
        if(recognizer!=null) {
            try {recognizer.close();} catch(Exception ignored) {}
        }
        recognizer=null;
        if(captureThread!=null) {
            captureThread.quitSafely();
            captureThread=null;
        }
        captureHandler=null;
        if(Build.VERSION.SDK_INT>=24) stopForeground(STOP_FOREGROUND_REMOVE);
        else stopForeground(true);
        stopSelf();
    }

    @Override public void onDestroy() {
        shutdown();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
