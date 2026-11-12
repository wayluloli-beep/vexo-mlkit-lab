package com.vexo.mlkitlab;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.content.res.Configuration;
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
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.Display;
import android.view.WindowManager;
import android.widget.Toast;

import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import com.vexo.mlkitlab.FastCardVisualTracker.Box;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

public final class ManualVisionService extends Service implements ManualVisionOverlay.Actions {
    static final String START = "com.vexo.mlkitlab.vision.START";
    static final String CONSENT = "projection_consent";
    private static final String STOP = "com.vexo.mlkitlab.vision.STOP";
    private static final String CHANNEL = "vexo_manual_capture";
    private static final int NOTIFICATION_ID = 813;
    private static final long TRACK_INTERVAL_MS = 75;
    private static final long NO_FRAME_MS = 1_500;

    private final Handler main = new Handler(Looper.getMainLooper());
    private final AtomicReference<DisplayState> latest = new AtomicReference<>();
    private final AtomicBoolean drawQueued = new AtomicBoolean();
    private final ManualTargetTracker tracker = new ManualTargetTracker();
    private final TargetReadingState reading = new TargetReadingState();

    // Main thread owns the overlay. The capture handler owns frames, tracker and OCR state.
    private ManualVisionOverlay overlay;
    private HandlerThread captureThread;
    private Handler capture;
    private volatile boolean running;
    private boolean shuttingDown;
    private volatile long requestedSelection;
    private volatile Geometry geometry;
    private long selection;

    private MediaProjection projection;
    private VirtualDisplay virtualDisplay;
    private ImageReader reader;
    private TextRecognizer recognizer;
    private boolean visible = true;
    private boolean aligned = true;
    private int contentWidth;
    private int contentHeight;
    private long frameNumber;
    private long lastFrameAt = -1;
    private long lastTrackAt = -1;
    private long verifiedFrame;
    private PendingSelection pending;
    private Box tracked;
    private boolean readEnabled;
    private boolean ocrBusy;
    private final StaticCardOcrRetry ocrRetry = new StaticCardOcrRetry();
    private String text = "";
    private String readStatus = "";

    private final MediaProjection.Callback projectionCallback = new MediaProjection.Callback() {
        @Override public void onStop() {
            running = false;
            main.post(ManualVisionService.this::stop);
        }

        @Override public void onCapturedContentResize(int width, int height) {
            if (!running) return;
            contentWidth = width;
            contentHeight = height;
            refreshGeometry();
        }

        @Override public void onCapturedContentVisibilityChanged(boolean isVisible) {
            if (!running || visible == isVisible) return;
            visible = isVisible;
            clearTarget();
            publish(isVisible ? idleMessage() : "Captura pausada");
        }
    };

    private final Runnable watchdog = new Runnable() {
        @Override public void run() {
            if (!running) return;
            long now = SystemClock.elapsedRealtime();
            if ((tracked != null && now - lastTrackAt > NO_FRAME_MS)
                    || (pending != null && now - pending.requestedAt > NO_FRAME_MS)) {
                clearTarget();
                publish("Sem imagem recente · marque de novo");
            }
            capture.postDelayed(this, 250);
        }
    };

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;
        if (STOP.equals(intent.getAction())) {
            stop();
            return START_NOT_STICKY;
        }
        if (!START.equals(intent.getAction()) || running || shuttingDown) return START_NOT_STICKY;

        try {
            enterForeground();
            Intent consent = Build.VERSION.SDK_INT >= 33
                ? intent.getParcelableExtra(CONSENT, Intent.class)
                : intent.getParcelableExtra(CONSENT);
            if (consent == null || !Settings.canDrawOverlays(this)) {
                throw new IllegalStateException("missing consent");
            }
            Display display = getSystemService(DisplayManager.class).getDisplay(Display.DEFAULT_DISPLAY);
            Context displayContext = createDisplayContext(display);
            Context windowContext = Build.VERSION.SDK_INT >= 30
                ? displayContext.createWindowContext(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, null)
                : displayContext;
            overlay = new ManualVisionOverlay(windowContext, this);
            overlay.attach();
            captureThread = new HandlerThread("vexo-visual-capture");
            captureThread.start();
            capture = new Handler(captureThread.getLooper());
            running = true;
            capture.post(() -> openProjection(consent));
        } catch (RuntimeException exception) {
            failCapture();
        }
        return START_NOT_STICKY;
    }

    private void enterForeground() {
        NotificationManager notifications = getSystemService(NotificationManager.class);
        notifications.createNotificationChannel(new NotificationChannel(
            CHANNEL, "Vexo · captura de tela", NotificationManager.IMPORTANCE_LOW));
        Intent stop = new Intent(this, ManualVisionService.class).setAction(STOP);
        PendingIntent stopAction = PendingIntent.getService(this, 0, stop, PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, CHANNEL)
            .setContentTitle("Vexo · captura de tela ativa")
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setOngoing(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause,
                "Parar", stopAction).build())
            .build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void openProjection(Intent consent) {
        if (!running) return;
        try {
            MediaProjectionManager manager = getSystemService(MediaProjectionManager.class);
            projection = manager.getMediaProjection(Activity.RESULT_OK, consent);
            if (projection == null) throw new IllegalStateException("projection unavailable");
            projection.registerCallback(projectionCallback, capture);
            Geometry initial = currentGeometry();
            reader = newReader(initial);
            virtualDisplay = projection.createVirtualDisplay("Vexo captura autorizada",
                initial.width, initial.height, initial.density, DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader.getSurface(), null, capture);
            if (virtualDisplay == null) throw new IllegalStateException("display unavailable");
            geometry = initial;
            capture.post(watchdog);
        } catch (RuntimeException exception) {
            failCapture();
        }
    }

    private Geometry currentGeometry() {
        DisplayMetrics metrics = new DisplayMetrics();
        Display display = getSystemService(DisplayManager.class).getDisplay(Display.DEFAULT_DISPLAY);
        display.getRealMetrics(metrics);
        return new Geometry(metrics.widthPixels, metrics.heightPixels, metrics.densityDpi);
    }

    private ImageReader newReader(Geometry size) {
        ImageReader imageReader = ImageReader.newInstance(size.width, size.height, PixelFormat.RGBA_8888, 3);
        imageReader.setOnImageAvailableListener(this::onImage, capture);
        return imageReader;
    }

    @Override public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        if (!running) return;
        long request = ++requestedSelection;
        overlay.reset();
        capture.post(() -> {
            if (!running || requestedSelection != request) return;
            selection = request;
            clearTarget();
            refreshGeometry();
            publish(idleMessage());
        });
    }

    private void refreshGeometry() {
        if (virtualDisplay == null) return;
        try {
            Geometry next = currentGeometry();
            boolean fits = contentWidth == 0
                || (next.screenWidth == contentWidth && next.screenHeight == contentHeight);
            if (!fits) {
                aligned = false;
                clearTarget();
                publish(idleMessage());
                return;
            }
            boolean wasAligned = aligned;
            aligned = true;
            if (geometry.sameDisplay(next)) {
                if (!wasAligned) publish(idleMessage());
                return;
            }
            clearTarget();
            ImageReader replacement = newReader(next);
            try {
                virtualDisplay.resize(next.width, next.height, next.density);
                virtualDisplay.setSurface(replacement.getSurface());
            } catch (RuntimeException exception) {
                replacement.close();
                throw exception;
            }
            ImageReader previous = reader;
            reader = replacement;
            geometry = next;
            lastFrameAt = -1;
            previous.close();
            publish(idleMessage());
        } catch (RuntimeException exception) {
            failCapture();
        }
    }

    @Override public void beginSelection() {
        if (!running) return;
        long request = ++requestedSelection;
        capture.post(() -> {
            if (!running || request != requestedSelection) return;
            selection = request;
            clearTarget();
            publish(idleMessage());
        });
    }

    @Override public void select(Rect screenBox) {
        if (!running) return;
        Geometry selectedGeometry = geometry;
        long request = requestedSelection;
        capture.post(() -> {
            if (!running || selection != request || request != requestedSelection) return;
            if (screenBox == null || !visible || !aligned || selectedGeometry == null
                    || selectedGeometry != geometry) {
                publish(idleMessage());
                return;
            }
            pending = new PendingSelection(selectedGeometry.toFrame(screenBox), SystemClock.elapsedRealtime());
            publish("Buscando o alvo marcado");
        });
    }

    @Override public void read(boolean enabled) {
        if (!running) return;
        capture.post(() -> {
            if (!running) return;
            readEnabled = enabled;
            clearReading();
            publish(tracked == null ? idleMessage() : "Rastreando");
        });
    }

    private void onImage(ImageReader source) {
        if (!running || source != reader) return;
        OcrInput request = null;
        try (Image image = source.acquireLatestImage()) {
            if (image == null || !visible || !aligned) return;
            long now = SystemClock.elapsedRealtime();
            if (lastFrameAt < 0 && tracked == null && pending == null) publish(idleMessage());
            lastFrameAt = now;
            frameNumber++;
            if (selection != requestedSelection || (tracked == null && pending == null)) return;
            if (pending == null && now - lastTrackAt < TRACK_INTERVAL_MS) return;

            Image.Plane plane = image.getPlanes()[0];
            RgbaLumaPixels pixels = new RgbaLumaPixels(plane.getBuffer(),
                image.getWidth(), image.getHeight(), plane.getRowStride(), plane.getPixelStride());
            if (pending != null) {
                Box selected = pending.box;
                pending = null;
                if (!tracker.select(pixels, selected)) {
                    clearTarget();
                    publish("Marque uma área com mais detalhes");
                    return;
                }
                tracked = selected;
            } else {
                tracked = tracker.track(pixels, geometry.dipInFrame(4), geometry.dipInFrame(3));
                if (tracked == null) {
                    clearTarget();
                    publish("Alvo perdido · marque de novo");
                    return;
                }
            }
            lastTrackAt = now;
            verifiedFrame = frameNumber;
            if (readEnabled) {
                if (reading.observe(TargetReadingState.signature(pixels, tracked))) {
                    text = "";
                    readStatus = "Rastreando · conferindo alvo";
                }
                if (reading.ready() && !ocrBusy && ocrRetry.mayStart(reading.revision(), now)) {
                    ocrRetry.started(reading.revision(), now);
                    request = new OcrInput(crop(plane, tracked), selection, attemptedRevision, frameNumber, now);
                    readStatus = "Rastreando · lendo…";
                }
            }
            publish(readStatus.isEmpty() ? "Rastreando" : readStatus);
        } catch (RuntimeException exception) {
            clearTarget();
            publish("Imagem indisponível · marque de novo");
        }
        if (request != null) {
            if (running && selection == requestedSelection) startOcr(request);
            else request.bitmap.recycle();
        }
    }

    private static Bitmap crop(Image.Plane plane, Box box) {
        int step = Math.max(1, (int) Math.ceil(Math.sqrt((long) box.width * box.height / 2_500_000.0)));
        int width = (box.width + step - 1) / step;
        int height = (box.height + step - 1) / step;
        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        ByteBuffer source = plane.getBuffer().duplicate().order(ByteOrder.LITTLE_ENDIAN);
        int[] row = new int[width];
        for (int y = 0; y < height; y++) {
            int start = (box.y + y * step) * plane.getRowStride() + box.x * 4;
            for (int x = 0; x < width; x++) {
                int rgba = source.getInt(start + x * step * 4);
                row[x] = 0xff000000 | ((rgba & 0xff) << 16) | (rgba & 0xff00) | ((rgba >>> 16) & 0xff);
            }
            bitmap.setPixels(row, 0, width, 0, y, width, 1);
        }
        return bitmap;
    }

    private void startOcr(OcrInput input) {
        ocrBusy = true;
        try {
            if (recognizer == null) recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            recognizer.process(InputImage.fromBitmap(input.bitmap, 0))
                .addOnCompleteListener(main::post, result -> {
                    input.bitmap.recycle();
                    if (running) {
                        capture.post(() -> finishOcr(input, result.isSuccessful()
                            ? result.getResult().getText() : null));
                    }
                });
        } catch (RuntimeException exception) {
            input.bitmap.recycle();
            finishOcr(input, null);
        }
    }

    private void finishOcr(OcrInput input, String result) {
        ocrBusy = false;
        if (!running || !visible || !aligned || !readEnabled || tracked == null
                || selection != requestedSelection || selection != input.selection
                || !reading.accepts(input.revision) || verifiedFrame < input.frame
                || lastTrackAt < input.capturedAt
                || SystemClock.elapsedRealtime() - lastTrackAt > NO_FRAME_MS) return;
        String cleaned = result == null ? "" : result.trim();
        long now = SystemClock.elapsedRealtime();
        if (cleaned.isEmpty()) {
            ocrRetry.finished(input.revision,now,false);
            text = ""; // never manufacture OCR text on failure
            readStatus = ocrRetry.exhausted(input.revision)
                ? "OCR não confirmou · toque em Ler para tentar de novo"
                : "OCR instável · nova tentativa limitada";
        } else {
            ocrRetry.finished(input.revision,now,true);
            text = cleaned;
            if (text.length() > 160) text = text.substring(0, 160) + "…";
            readStatus = "Rastreando · texto lido";
        }
        publish(readStatus);
    }

    private String idleMessage() {
        return aligned ? "Marque um alvo" : "Reinicie e compartilhe a tela inteira";
    }

    private void clearTarget() {
        pending = null;
        tracked = null;
        tracker.clear();
        lastTrackAt = -1;
        clearReading();
    }

    private void clearReading() {
        reading.clear();
        ocrRetry.reset();
        text = "";
        readStatus = "";
    }

    private void publish(String message) {
        if (!running) return;
        Rect rectangle = tracked == null ? null : geometry.toScreen(tracked);
        latest.set(new DisplayState(selection, rectangle, message, text, visible));
        if (drawQueued.compareAndSet(false, true)) main.post(this::renderLatest);
    }

    private void renderLatest() {
        drawQueued.set(false);
        DisplayState state = latest.get();
        if (running && overlay != null && state != null && state.selection == requestedSelection) {
            overlay.render(state.box, state.message, state.text, state.visible);
        }
    }

    private void failCapture() {
        running = false;
        main.post(() -> {
            if (shuttingDown) return;
            Toast.makeText(this, "O Android não iniciou ou encerrou a captura.", Toast.LENGTH_LONG).show();
            stop();
        });
    }

    @Override public void stop() {
        closeSession();
        stopSelf();
    }

    private void closeSession() {
        if (shuttingDown) return;
        shuttingDown = true;
        running = false;
        latest.set(null);
        if (overlay != null) {
            overlay.close();
            overlay = null;
        }
        if (capture != null) {
            capture.removeCallbacks(watchdog);
            capture.post(this::releaseCapture);
            captureThread.quitSafely();
        }
        stopForeground(STOP_FOREGROUND_REMOVE);
    }

    private void releaseCapture() {
        clearTarget();
        if (virtualDisplay != null) virtualDisplay.release();
        if (reader != null) reader.close();
        if (projection != null) {
            projection.unregisterCallback(projectionCallback);
            projection.stop();
        }
        if (recognizer != null) recognizer.close();
    }

    @Override public void onDestroy() {
        closeSession();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) {
        return null;
    }

    private static final class Geometry {
        final int screenWidth;
        final int screenHeight;
        final int density;
        final int width;
        final int height;

        Geometry(int screenWidth, int screenHeight, int density) {
            this.screenWidth = screenWidth;
            this.screenHeight = screenHeight;
            this.density = density;
            int[] fitted = CaptureDimensions.fit(screenWidth, screenHeight);
            width = fitted[0];
            height = fitted[1];
        }

        boolean sameDisplay(Geometry other) {
            return screenWidth == other.screenWidth && screenHeight == other.screenHeight
                && density == other.density;
        }

        Box toFrame(Rect screen) {
            int left = coordinate(screen.left, screenWidth, width);
            int top = coordinate(screen.top, screenHeight, height);
            return new Box(left, top, coordinate(screen.right, screenWidth, width) - left,
                coordinate(screen.bottom, screenHeight, height) - top);
        }

        Rect toScreen(Box frame) {
            return new Rect(coordinate(frame.x, width, screenWidth), coordinate(frame.y, height, screenHeight),
                coordinate(frame.x + frame.width, width, screenWidth),
                coordinate(frame.y + frame.height, height, screenHeight));
        }

        int dipInFrame(int dp) {
            return Math.max(1, Math.round(dp * (density / 160f) * width / screenWidth));
        }

        private static int coordinate(int value, int from, int to) {
            return (int) (((long) Math.max(0, Math.min(from, value)) * to + from / 2) / from);
        }
    }

    private static final class PendingSelection {
        final Box box;
        final long requestedAt;

        PendingSelection(Box box, long requestedAt) {
            this.box = box;
            this.requestedAt = requestedAt;
        }
    }

    private static final class OcrInput {
        final Bitmap bitmap;
        final long selection;
        final long revision;
        final long frame;
        final long capturedAt;

        OcrInput(Bitmap bitmap, long selection, long revision, long frame, long capturedAt) {
            this.bitmap = bitmap;
            this.selection = selection;
            this.revision = revision;
            this.frame = frame;
            this.capturedAt = capturedAt;
        }
    }

    private static final class DisplayState {
        final long selection;
        final Rect box;
        final String message;
        final String text;
        final boolean visible;

        DisplayState(long selection, Rect box, String message, String text, boolean visible) {
            this.selection = selection;
            this.box = box;
            this.message = message;
            this.text = text;
            this.visible = visible;
        }
    }
}
