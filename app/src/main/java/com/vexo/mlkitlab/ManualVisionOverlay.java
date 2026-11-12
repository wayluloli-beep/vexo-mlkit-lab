package com.vexo.mlkitlab;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.hardware.input.InputManager;
import android.os.Build;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** The outline receives touch only during a user-initiated selection. */
final class ManualVisionOverlay {
    interface Actions {
        void beginSelection();
        void select(Rect box);
        void read(boolean enabled);
        void stop();
    }

    private final Context context;
    private final WindowManager windows;
    private final Actions actions;
    private final Outline outline;
    private final LinearLayout panel;
    private final TextView status;
    private final TextView reading;
    private final Button mark;
    private final Button read;
    private final WindowManager.LayoutParams outlineParams;
    private boolean selecting;
    private boolean readingEnabled;
    private int startX;
    private int startY;
    private Rect drag;
    private Rect tracked;

    ManualVisionOverlay(Context context, Actions actions) {
        this.context = context;
        this.actions = actions;
        windows = context.getSystemService(WindowManager.class);
        outline = new Outline(context);
        outline.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        outlineParams = params(-1, -1, WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
            | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE);
        outlineParams.gravity = Gravity.TOP | Gravity.LEFT;
        if (Build.VERSION.SDK_INT >= 30) {
            outlineParams.setFitInsetsTypes(0);
            outlineParams.layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS;
        } else if (Build.VERSION.SDK_INT >= 28) {
            outlineParams.layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        }
        outlineParams.alpha = 0.75f;
        if (Build.VERSION.SDK_INT >= 31) {
            InputManager input = context.getSystemService(InputManager.class);
            if (input != null) {
                outlineParams.alpha = Math.min(outlineParams.alpha,
                    input.getMaximumObscuringOpacityForTouch());
            }
        }

        panel = new LinearLayout(context);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(8), dp(6), dp(8), dp(6));
        GradientDrawable background = new GradientDrawable();
        background.setColor(0xf0182530);
        background.setCornerRadius(dp(12));
        panel.setBackground(background);
        reading = new TextView(context);
        reading.setTextSize(13);
        reading.setTextColor(0xffa7ffc6);
        reading.setMaxWidth(dp(232));
        reading.setMaxLines(3);
        reading.setVisibility(View.GONE);
        LinearLayout buttons = new LinearLayout(context);
        panel.addView(buttons);
        mark = button(buttons, "Marcar alvo", this::toggleSelection);
        read = button(buttons, "Ler", () -> {
            readingEnabled = !readingEnabled;
            readButtonLabel();
            reading.setText("");
            reading.setVisibility(View.GONE);
            actions.read(readingEnabled);
        });
        button(buttons, "Parar", actions::stop);
        status = new TextView(context);
        status.setTextSize(12);
        status.setTextColor(0xffe6f2fc);
        status.setText("Aguardando imagem");
        panel.addView(status);
        panel.addView(reading);
    }

    void attach() {
        windows.addView(outline, outlineParams);
        WindowManager.LayoutParams controls = params(-2, -2, 0);
        controls.gravity = Gravity.TOP | Gravity.RIGHT;
        controls.x = dp(6);
        controls.y = dp(8);
        windows.addView(panel, controls);
    }

    void render(Rect box, String message, String text, boolean visible) {
        if (!visible && selecting) endSelection(null);
        panel.setVisibility(visible ? View.VISIBLE : View.GONE);
        if (selecting) return;
        tracked = visible ? box : null;
        status.setText(message);
        reading.setText(text);
        reading.setVisibility(visible && readingEnabled && !text.isEmpty()
            ? View.VISIBLE : View.GONE);
        outline.invalidate();
    }

    void reset() {
        if (selecting) endSelection(null);
        render(null, "Marque um alvo", "", true);
    }

    void close() {
        remove(panel);
        remove(outline);
    }

    private void remove(View view) {
        if (view.getParent() != null) {
            try {
                windows.removeViewImmediate(view);
            } catch (IllegalArgumentException ignored) {
                // Android can remove an overlay itself when its permission is revoked.
            }
        }
    }

    private Button button(LinearLayout row, String label, Runnable click) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextColor(0xfff3f6fa);
        button.setAllCaps(false);
        button.setTextSize(13);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setMinHeight(0);
        button.setMinimumHeight(0);
        button.setPadding(dp(9), 0, dp(9), 0);
        button.setOnClickListener(view -> click.run());
        row.addView(button, new LinearLayout.LayoutParams(-2, dp(44)));
        return button;
    }

    private void readButtonLabel() {
        read.setText(readingEnabled ? "Leitura ligada" : "Ler");
    }

    private void toggleSelection() {
        if (selecting) {
            endSelection(null);
            return;
        }
        actions.beginSelection();
        selecting = true;
        tracked = null;
        drag = null;
        reading.setText("");
        reading.setVisibility(View.GONE);
        mark.setText("Cancelar");
        status.setText("Arraste em volta do alvo");
        setSelectionInput(true);
        outline.invalidate();
    }

    private void endSelection(Rect box) {
        selecting = false;
        drag = null;
        mark.setText("Marcar alvo");
        status.setText(box == null ? "Marque um alvo" : "Buscando o alvo marcado");
        setSelectionInput(false);
        outline.invalidate();
        actions.select(box);
    }

    private void setSelectionInput(boolean enabled) {
        int flag = WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
        outlineParams.flags = enabled ? outlineParams.flags & ~flag : outlineParams.flags | flag;
        if (outline.getParent() != null) {
            try {
                windows.updateViewLayout(outline, outlineParams);
            } catch (RuntimeException exception) {
                actions.stop();
            }
        }
    }

    private WindowManager.LayoutParams params(int width, int height, int flags) {
        return new WindowManager.LayoutParams(width, height,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            flags | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL, PixelFormat.TRANSLUCENT);
    }

    private int dp(float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    private final class Outline extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final int[] screenLocation = new int[2];

        Outline(Context context) {
            super(context);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(dp(3));
        }

        @Override protected void onDraw(Canvas canvas) {
            Rect box = selecting ? drag : tracked;
            if (box == null) return;
            getLocationOnScreen(screenLocation);
            int margin = dp(4);
            paint.setColor(selecting ? 0xff27c4d8 : 0xff31ed76);
            canvas.drawRect(box.left - screenLocation[0] - margin,
                box.top - screenLocation[1] - margin, box.right - screenLocation[0] + margin,
                box.bottom - screenLocation[1] + margin, paint);
        }

        @Override public boolean onTouchEvent(MotionEvent event) {
            if (!selecting) return false;
            int x = Math.round(event.getRawX());
            int y = Math.round(event.getRawY());
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    startX = x;
                    startY = y;
                    drag = new Rect(x, y, x, y);
                    return true;
                case MotionEvent.ACTION_MOVE:
                case MotionEvent.ACTION_UP:
                    drag = new Rect(Math.min(startX, x), Math.min(startY, y),
                        Math.max(startX, x), Math.max(startY, y));
                    invalidate();
                    if (event.getActionMasked() == MotionEvent.ACTION_UP) {
                        endSelection(drag.width() >= dp(18) && drag.height() >= dp(18) ? drag : null);
                    }
                    return true;
                case MotionEvent.ACTION_CANCEL:
                    endSelection(null);
                    return true;
                default:
                    return true;
            }
        }

        @Override public boolean performClick() {
            return super.performClick();
        }
    }
}
