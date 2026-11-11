import java.nio.ByteBuffer;

/** Compara pixels na área observada e decide quando pedir OCR do quadro inteiro. */
final class FrameChangeProbe {
    record Region(int left, int top, int right, int bottom) {}

    enum Reason {
        FIRST_OR_MOVED_REGION, VISUAL_CHANGE, SECOND_READ, PERIODIC_CHECK, INVALID_FRAME, STABLE
    }

    private record Sample(int width, int height, Region region, long hash) {}

    record Check(Reason reason, Sample sample, long atMs) {
        boolean needsFullRead() {
            return reason != Reason.STABLE;
        }
    }

    private final long maxQuietMs;
    private Sample lastRead;
    private long lastReadAtMs;

    FrameChangeProbe(long maxQuietMs) {
        if (maxQuietMs <= 0) throw new IllegalArgumentException("intervalo inválido");
        this.maxQuietMs = maxQuietMs;
    }

    Check check(ByteBuffer rgba, int width, int height, int rowStride,
            Region region, long atMs, boolean needsSecondRead) {
        if (atMs < 0 || !fits(rgba, width, height, rowStride, region)) {
            return new Check(Reason.INVALID_FRAME, null, atMs);
        }
        Sample current = new Sample(width, height, region, hash(rgba, rowStride, region));
        Reason reason;
        if (needsSecondRead) {
            reason = Reason.SECOND_READ;
        } else if (lastRead == null || width != lastRead.width() || height != lastRead.height()
                || !region.equals(lastRead.region())) {
            reason = Reason.FIRST_OR_MOVED_REGION;
        } else if (current.hash() != lastRead.hash()) {
            reason = Reason.VISUAL_CHANGE;
        } else if (atMs < lastReadAtMs || atMs - lastReadAtMs >= maxQuietMs) {
            reason = Reason.PERIODIC_CHECK;
        } else {
            reason = Reason.STABLE;
        }
        return new Check(reason, current, atMs);
    }

    // O chamador só registra depois de obter a vaga de OCR do CaptureThrottle.
    void recordReadStarted(Check check) {
        if (!check.needsFullRead()) throw new IllegalArgumentException("quadro estável");
        lastRead = check.sample();
        lastReadAtMs = check.atMs();
    }

    void reset() {
        lastRead = null;
    }

    private static boolean fits(ByteBuffer rgba, int width, int height, int rowStride, Region r) {
        return rgba != null && width > 0 && height > 0 && rowStride >= (long) width * 4
            && r != null && r.left() >= 0 && r.top() >= 0 && r.right() <= width && r.bottom() <= height
            && r.left() < r.right() && r.top() < r.bottom()
            && (long) (r.bottom() - 1) * rowStride + (long) r.right() * 4 <= rgba.limit();
    }

    private static long hash(ByteBuffer rgba, int stride, Region r) {
        long hash = 0xcbf29ce484222325L;
        for (int y = r.top(); y < r.bottom(); y++) {
            int start = y * stride + r.left() * 4;
            int end = y * stride + r.right() * 4;
            for (int offset = start; offset < end; offset += 4) {
                hash = (hash ^ Integer.toUnsignedLong(rgba.getInt(offset))) * 0x100000001b3L;
            }
        }
        return hash;
    }
}
