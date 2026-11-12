package com.vexo.reader;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
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
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Explicitly consented screen capture. ImageReader always takes the latest frame.
 * OCR is strictly one-in-flight, in a screen-height-relative crop.
 * Offers are observations, never accepted or completed trips.
 */
public final class ScreenReadService extends Service {
    public static final String ACTION_START = "com.vexo.reader.START";
    public static final String ACTION_STOP = "com.vexo.reader.STOP";
    public static final String EXTRA_GRANT_RESULT = "grantResult";
    public static final String EXTRA_GRANT_DATA = "grantData";
    private static final String CHANNEL_ID = "vexo_capture";
    private static final int NOTIFICATION_ID = 702;
    private static final long OCR_INTERVAL_MS = 700L;
    private static final long OCR_TTL_MS = 2300L;

    private final AtomicBoolean busy = new AtomicBoolean(false);
    private MediaProjection projection;
    private MediaProjection.Callback projectionCallback;
    private VirtualDisplay virtualDisplay;
    private ImageReader reader;
    private TextRecognizer recognizer;
    private HandlerThread captureThread;
    private Handler captureHandler;
    private RideDb db;

    private volatile boolean closing;
    private volatile int epoch;
    private int[] lastSamples;
    private long lastOcrAt;
    private long generation;
    private String candidateFingerprint = "";
    private int candidateCount;
    private String publishedFingerprint = "";
    private int publishedEpoch = -1;
    private int displayWidth, displayHeight, densityDpi;

    @Override public void onCreate() {
        super.onCreate();
        db = new RideDb(getApplicationContext());
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.createNotificationChannel(new NotificationChannel(
            CHANNEL_ID, "Leitura de tela Vexo", NotificationManager.IMPORTANCE_LOW));
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!ACTION_START.equals(intent.getAction())) return START_NOT_STICKY;
        if (projection != null) return START_NOT_STICKY;
        int grantResult = intent.getIntExtra(EXTRA_GRANT_RESULT, 0);
        Intent grant = intent.getParcelableExtra(EXTRA_GRANT_DATA);
        if (grant == null || grantResult != android.app.Activity.RESULT_OK) {
            ScreenState.invalidate("Permissão de captura não concedida");
            stopSelf();
            return START_NOT_STICKY;
        }
        // The foreground service must start before getMediaProjection on Android 14+.
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, makeNotification(),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(NOTIFICATION_ID, makeNotification());
        }
        try {
            closing = false;
            generation = SystemClock.elapsedRealtimeNanos();
            epoch = 0;
            candidateCount = 0;
            publishedEpoch = -1;
            lastSamples = null;
            candidateFingerprint = "";
            publishedFingerprint = "";
            lastOcrAt = 0;
            ScreenState.receivedFrames = 0;
            ScreenState.ocrCompleted = 0;
            ScreenState.lastFrameAt = 0;
            ScreenState.active = true;
            ScreenState.invalidate("Aguardando pixels da tela autorizada");
            recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            captureThread = new HandlerThread("VexoCaptureFrames");
            captureThread.start();
            captureHandler = new Handler(captureThread.getLooper());
            WindowManager wm = (WindowManager) getSystemService(WINDOW_SERVICE);
            DisplayMetrics metrics = new DisplayMetrics();
            wm.getDefaultDisplay().getRealMetrics(metrics);
            displayWidth = metrics.widthPixels;
            displayHeight = metrics.heightPixels;
            densityDpi = metrics.densityDpi;
            MediaProjectionManager pm = (MediaProjectionManager)
                getSystemService(MEDIA_PROJECTION_SERVICE);
            projection = pm.getMediaProjection(grantResult, grant);
            projectionCallback = new MediaProjection.Callback() {
                @Override public void onStop() {
                    ScreenState.invalidate("Android encerrou a captura");
                    stopSelf();
                }
                @Override public void onCapturedContentResize(int width, int height) {
                    if (width > 0 && height > 0 && captureHandler != null) {
                        captureHandler.post(() -> resizeCapture(width, height));
                    }
                }
                @Override public void onCapturedContentVisibilityChanged(boolean isVisible) {
                    if (!isVisible) ScreenState.invalidate("Tela-alvo oculta: oferta invalidada");
                }
            };
            projection.registerCallback(projectionCallback, captureHandler);
            createCapture(displayWidth, displayHeight);
            ScreenState.status = "Capturando. Abra o aplicativo autorizado.";
        } catch (Exception e) {
            ScreenState.invalidate("Falha ao iniciar captura: " + e.getClass().getSimpleName());
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    private Notification makeNotification() {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent openPending = PendingIntent.getActivity(
            this, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Intent stop = new Intent(this, ScreenReadService.class).setAction(ACTION_STOP);
        PendingIntent stopPending = PendingIntent.getService(this, 1, stop,
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setContentTitle("Vexo Reader — captura autorizada")
            .setContentText("Leitura OCR local em andamento. Toque para voltar.")
            .setContentIntent(openPending)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_media_pause, "Parar captura", stopPending)
            .build();
    }

    private void createCapture(int width, int height) {
        if (closing || projection == null || width < 64 || height < 64) return;
        displayWidth = width;
        displayHeight = height;
        reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2);
        reader.setOnImageAvailableListener(this::onFrame, captureHandler);
        virtualDisplay = projection.createVirtualDisplay("VexoReaderConsentCapture",
            width, height, densityDpi, DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            reader.getSurface(), null, captureHandler);
    }

    private void resizeCapture(int width, int height) {
        if (closing || virtualDisplay == null || (width == displayWidth && height == displayHeight)) return;
        // Reconfigure the SAME VirtualDisplay: Android 14+ forbids a second
        // createVirtualDisplay() with a previously used consent token.
        ImageReader old = reader;
        if (old != null) old.setOnImageAvailableListener(null, null);
        reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2);
        reader.setOnImageAvailableListener(this::onFrame, captureHandler);
        virtualDisplay.resize(width, height, densityDpi);
        virtualDisplay.setSurface(reader.getSurface());
        if (old != null) old.close();
        displayWidth = width;
        displayHeight = height;
        epoch++;
        lastSamples = null;
        candidateCount = 0;
        ScreenState.invalidate("Geometria alterada. Revalidando o card");
    }

    private void onFrame(ImageReader source) {
        Image image = null;
        try {
            image = source.acquireLatestImage();
            if (image == null || closing || !ScreenState.active) return;
            long now = SystemClock.elapsedRealtime();
            ScreenState.lastFrameAt = now;
            ScreenState.receivedFrames++;
            int[] samples = sampleLuma(image);
            if (lastSamples != null && significantChange(lastSamples, samples)) {
                epoch++;
                candidateCount = 0;
                candidateFingerprint = "";
                ScreenState.invalidate("Mudança visual detectada: aguardando nova leitura");
            }
            lastSamples = samples;
            if (now - lastOcrAt < OCR_INTERVAL_MS || !busy.compareAndSet(false, true)) return;
            lastOcrAt = now;
            final long capturedAt = now;
            final int frameEpoch = epoch;
            final long captureGeneration = generation;
            final Bitmap crop = copyLowerRegion(image);
            if (crop == null) {
                busy.set(false);
                return;
            }
            recognizer.process(InputImage.fromBitmap(crop, 0))
                .addOnSuccessListener(result -> {
                    if (closing || !ScreenState.active || captureGeneration != generation ||
                        frameEpoch != epoch ||
                        SystemClock.elapsedRealtime() - capturedAt > OCR_TTL_MS) return;
                    ScreenState.ocrCompleted++;
                    OfferRecord r = OfferParser.parse(result.getText(), System.currentTimeMillis());
                    ScreenState.lastReadingAt = SystemClock.elapsedRealtime();
                    if (!r.hasMinimumFields()) {
                        candidateCount = 0;
                        candidateFingerprint = "";
                        ScreenState.preview = null;
                        ScreenState.status = "OCR ativo · dados incompletos ou não é uma oferta";
                        return;
                    }
                    String signature = r.fingerprint();
                    if (signature.equals(candidateFingerprint)) candidateCount++;
                    else {
                        candidateFingerprint = signature;
                        candidateCount = 1;
                    }
                    // A single OCR pass is never persisted as a valid observed offer.
                    ScreenState.preview = r;
                    if (candidateCount < 2) {
                        ScreenState.status = "Oferta candidata · aguardando segunda leitura";
                        return;
                    }
                    if (!signature.equals(publishedFingerprint) || publishedEpoch != epoch) {
                        db.insert(r);
                        publishedFingerprint = signature;
                        publishedEpoch = epoch;
                    }
                    ScreenState.status = "Oferta observada (não significa corrida aceita)";
                })
                .addOnFailureListener(e -> {
                    if (!closing && frameEpoch == epoch) {
                        ScreenState.invalidate("Erro de OCR · nova tentativa no próximo ciclo");
                    }
                })
                .addOnCompleteListener(task -> {
                    crop.recycle();
                    busy.set(false);
                });
        } catch (Exception e) {
            busy.set(false);
            if (!closing) ScreenState.invalidate("Falha de frame: " + e.getClass().getSimpleName());
        } finally {
            if (image != null) image.close();
        }
    }

    /** 32x24 brightness grid over the lower part: cheap transition evidence, not KLT. */
    private static int[] sampleLuma(Image image) {
        Image.Plane plane = image.getPlanes()[0];
        ByteBuffer buffer = plane.getBuffer();
        int stride = plane.getRowStride();
        int pixelStride = plane.getPixelStride();
        int[] values = new int[32 * 24];
        int w = image.getWidth(), h = image.getHeight();
        for (int y = 0; y < 24; y++) {
            int py = Math.min(h - 1, h * (15 + y * 85 / 24) / 100);
            for (int x = 0; x < 32; x++) {
                int px = Math.min(w - 1, (x * w + w / 2) / 32);
                int index = py * stride + px * pixelStride;
                if (index + 2 < buffer.limit()) {
                    int r = buffer.get(index) & 0xFF;
                    int g = buffer.get(index + 1) & 0xFF;
                    int b = buffer.get(index + 2) & 0xFF;
                    values[y * 32 + x] = (r * 3 + g * 6 + b) / 10;
                }
            }
        }
        return values;
    }

    private static boolean significantChange(int[] previous, int[] current) {
        int changed = 0;
        for (int i = 0; i < previous.length; i++)
            if (Math.abs(previous[i] - current[i]) > 30) changed++;
        return changed >= 45;
    }

    /** The first pass examines 85% of screen height; no fixed pixel coordinates. */
    private static Bitmap copyLowerRegion(Image image) {
        Image.Plane plane = image.getPlanes()[0];
        int width = image.getWidth(), height = image.getHeight();
        int stride = plane.getRowStride(), pixelStride = plane.getPixelStride();
        if (pixelStride != 4 || width < 64 || height < 64 || stride % 4 != 0) return null;
        int paddedWidth = stride / 4;
        Bitmap padded = Bitmap.createBitmap(paddedWidth, height, Bitmap.Config.ARGB_8888);
        ByteBuffer buffer = plane.getBuffer();
        buffer.rewind();
        padded.copyPixelsFromBuffer(buffer);
        int top = Math.min(height - 1, Math.max(0, height * 15 / 100));
        Bitmap roi = Bitmap.createBitmap(padded, 0, top, width, height - top);
        padded.recycle();
        return roi;
    }

    @Override public void onDestroy() {
        closing = true;
        generation++;
        epoch++;
        ScreenState.active = false;
        ScreenState.invalidate("Captura desligada · leituras antigas descartadas");
        if (reader != null) {
            reader.setOnImageAvailableListener(null, null);
            reader.close();
            reader = null;
        }
        if (virtualDisplay != null) {
            virtualDisplay.release();
            virtualDisplay = null;
        }
        if (projection != null) {
            if (projectionCallback != null) projection.unregisterCallback(projectionCallback);
            projection.stop();
            projection = null;
        }
        if (recognizer != null) { recognizer.close(); recognizer = null; }
        if (captureThread != null) { captureThread.quitSafely(); captureThread = null; }
        if (db != null) { db.close(); db = null; }
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
