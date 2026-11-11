import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.Locale;

/** Casos sintéticos e medição local. Sem Android, ML Kit ou gravação de tela. */
public final class VisionProbeDemo {
    private static final int WIDTH = 1080;
    private static final int HEIGHT = 2400;
    private static final int STRIDE = WIDTH * 4 + 16;
    private static final int WARMUP = 80;
    private static final int SAMPLES = 300;
    private static final FrameChangeProbe.Region HALF =
        new FrameChangeProbe.Region(0, HEIGHT / 2, WIDTH, HEIGHT);
    private static final FrameChangeProbe.Region CARD =
        new FrameChangeProbe.Region(60, 1620, 1020, 2140);
    private static int cases;

    private static FrameChangeProbe.Check check(FrameChangeProbe probe, ByteBuffer frame,
            FrameChangeProbe.Region region, long nowMs, boolean confirmation) {
        return probe.check(frame, WIDTH, HEIGHT, STRIDE, region, nowMs, confirmation);
    }

    private static void expect(String scenario, FrameChangeProbe.Check actual, FrameChangeProbe.Reason expected) {
        if (actual.reason() != expected) throw new AssertionError(scenario + ": " + actual.reason());
        cases++;
    }

    private static void testBehavior(ByteBuffer frame) {
        FrameChangeProbe probe = new FrameChangeProbe(700);
        FrameChangeProbe.Check initial = check(probe, frame, HALF, 0, false);
        expect("primeiro quadro", initial, FrameChangeProbe.Reason.FIRST_OR_MOVED_REGION);
        probe.recordReadStarted(initial);
        frame.putInt(100 * STRIDE + 120 * 4, 1);
        expect("mapa muda acima da metade", check(probe, frame, HALF, 100, false), FrameChangeProbe.Reason.STABLE);
        frame.putInt(1700 * STRIDE + 200 * 4, 1);
        expect("card aparece na metade", check(probe, frame, HALF, 200, false), FrameChangeProbe.Reason.VISUAL_CHANGE);

        FrameChangeProbe.Check located = check(probe, frame, CARD, 200, false);
        expect("área do card localizada", located, FrameChangeProbe.Reason.FIRST_OR_MOVED_REGION);
        probe.recordReadStarted(located);
        frame.putInt(1300 * STRIDE + 120 * 4, 2);
        expect("mapa muda na metade, fora do card", check(probe, frame, CARD, 300, false), FrameChangeProbe.Reason.STABLE);
        expect("segundo quadro, mesmos pixels", check(probe, frame, CARD, 400, true), FrameChangeProbe.Reason.SECOND_READ);
        expect("leitura de segurança", check(probe, frame, CARD, 900, false), FrameChangeProbe.Reason.PERIODIC_CHECK);

        frame.putInt(1700 * STRIDE + 200 * 4, 3);
        expect("um pixel muda no card", check(probe, frame, CARD, 500, false), FrameChangeProbe.Reason.VISUAL_CHANGE);
        expect("OCR ocupado, mudança continua pendente", check(probe, frame, CARD, 600, false), FrameChangeProbe.Reason.VISUAL_CHANGE);
        probe.recordReadStarted(check(probe, frame, CARD, 650, false));
        expect("mudança já enviada ao OCR", check(probe, frame, CARD, 700, false), FrameChangeProbe.Reason.STABLE);

        frame.putInt(1700 * STRIDE + 200 * 4, 0);
        expect("card desaparece", check(probe, frame, CARD, 800, false), FrameChangeProbe.Reason.VISUAL_CHANGE);
        FrameChangeProbe.Region moved = new FrameChangeProbe.Region(60, 1420, 1020, 1940);
        expect("card mudou de posição", check(probe, frame, moved, 900, false), FrameChangeProbe.Reason.FIRST_OR_MOVED_REGION);
        expect("quadro incompleto", check(probe, ByteBuffer.allocate(4), CARD, 900, false), FrameChangeProbe.Reason.INVALID_FRAME);
        probe.reset();
        expect("nova sessão", check(probe, frame, CARD, 0, false), FrameChangeProbe.Reason.FIRST_OR_MOVED_REGION);
    }

    private static double measure(String label, ByteBuffer frame, FrameChangeProbe.Region region) {
        FrameChangeProbe probe = new FrameChangeProbe(700);
        probe.recordReadStarted(check(probe, frame, region, 0, false));
        for (int i = 0; i < WARMUP; i++) check(probe, frame, region, 100, false);
        long[] times = new long[SAMPLES];
        for (int i = 0; i < times.length; i++) {
            long start = System.nanoTime();
            FrameChangeProbe.Check result = check(probe, frame, region, 100, false);
            times[i] = System.nanoTime() - start;
            if (result.needsFullRead()) throw new AssertionError("quadro de medição mudou");
        }
        Arrays.sort(times);
        double p50 = times[(int) Math.ceil(times.length * 0.50) - 1] / 1_000_000.0;
        double p95 = times[(int) Math.ceil(times.length * 0.95) - 1] / 1_000_000.0;
        System.out.printf(Locale.ROOT, "%s (%dx%d): n=%d p50=%.3f ms p95=%.3f ms%n",
            label, region.right() - region.left(), region.bottom() - region.top(), times.length, p50, p95);
        return p95;
    }

    public static void main(String[] args) {
        ByteBuffer synthetic = ByteBuffer.allocateDirect(STRIDE * HEIGHT);
        testBehavior(synthetic);
        System.out.println(cases + " cenários sintéticos passaram.");
        double half = measure("Metade da tela", synthetic, HALF);
        double card = measure("Área do card", synthetic, CARD);
        if (half >= 100 || card >= 100) throw new AssertionError("p95 local do detector >= 100 ms");
    }
}
