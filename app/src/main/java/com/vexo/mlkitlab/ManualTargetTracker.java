package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import com.vexo.mlkitlab.FastCardVisualTracker.Pixels;

/** Follows one manually selected visual pattern using only current frame pixels. */
final class ManualTargetTracker {
    private static final int COLUMNS = 10;
    private static final int ROWS = 8;
    private static final int COARSE_COLUMNS = 8;
    private static final int COARSE_ROWS = 6;
    private static final int SEEDS_PER_SCALE = 3;
    private static final int MIN_SIDE = 24;
    private static final int MAX_ERROR = 18;
    private static final int[] SCALES = {100, 90, 110};

    private Sample[] template;
    private int[] coarseTemplate;
    private Box box;
    private int originalWidth;
    private int originalHeight;
    private int frameWidth;
    private int frameHeight;

    boolean select(Pixels pixels, Box region) {
        clear();
        if (region.width < MIN_SIDE || region.height < MIN_SIDE || !fits(pixels, region)) {
            return false;
        }
        originalWidth = region.width;
        originalHeight = region.height;
        int texture = 0;
        Sample[] samples = new Sample[COLUMNS * ROWS];
        for (int row = 0; row < ROWS; row++) {
            for (int column = 0; column < COLUMNS; column++) {
                Sample sample = selectSample(pixels, region, column, row);
                samples[row * COLUMNS + column] = sample;
                if (sample.weight > 1) texture++;
            }
        }
        if (texture < 4) return false;

        template = samples;
        coarseTemplate = new int[COARSE_COLUMNS * COARSE_ROWS];
        IntegralLuma anchor = new IntegralLuma(pixels, region.x, region.y,
            region.x + region.width, region.y + region.height);
        for (int row = 0; row < COARSE_ROWS; row++) {
            for (int column = 0; column < COARSE_COLUMNS; column++) {
                coarseTemplate[row * COARSE_COLUMNS + column] =
                    cellMean(anchor, region.x, region.y, region.width, region.height, column, row);
            }
        }
        box = region;
        frameWidth = pixels.width();
        frameHeight = pixels.height();
        return true;
    }

    Box track(Pixels pixels) {
        if (box == null || pixels.width() != frameWidth || pixels.height() != frameHeight) {
            clear();
            return null;
        }

        Shape current = new Shape(box.width, box.height);
        if (score(pixels, current, box.x, box.y) == 0) return box;

        int radius = Math.min(160, Math.max(36, (box.width + box.height) / 4));
        int step = 6;
        int marginX = radius + step + box.width / 10;
        int marginY = radius + step + box.height / 10;
        IntegralLuma neighborhood = new IntegralLuma(pixels, Math.max(0, box.x - marginX),
            Math.max(0, box.y - marginY), Math.min(pixels.width(), box.x + box.width + marginX),
            Math.min(pixels.height(), box.y + box.height + marginY));
        Match[] matches = new Match[SCALES.length * SEEDS_PER_SCALE];
        for (int index = 0; index < SCALES.length; index++) {
            int scale = SCALES[index];
            Shape shape = new Shape(box.width * scale / 100, box.height * scale / 100);
            int originX = box.x + (box.width - shape.width) / 2;
            int originY = box.y + (box.height - shape.height) / 2;
            Match[] seeds = coarseSearch(pixels, neighborhood, shape, originX, originY, radius, step);
            for (int i = 0; i < seeds.length; i++) {
                if (seeds[i] != null) matches[index * SEEDS_PER_SCALE + i] = refine(pixels, seeds[i], step);
            }
        }

        Match best = null;
        for (Match match : matches) {
            if (match != null && better(match, best)) best = match;
        }
        if (best == null || best.error > MAX_ERROR || ambiguous(best, matches)) {
            clear();
            return null;
        }
        box = new Box(best.x, best.y, best.shape.width, best.shape.height);
        return box;
    }

    void clear() {
        template = null;
        coarseTemplate = null;
        box = null;
    }

    private static Sample selectSample(Pixels pixels, Box region, int column, int row) {
        int bestContrast = -1;
        int bestX = 0;
        int bestY = 0;
        int bestValue = 0;
        int spread = smoothingRadius(region.width, region.height);
        for (int subY = 0; subY < 4; subY++) {
            for (int subX = 0; subX < 4; subX++) {
                int x = inset((column * 4 + subX) * region.width / (COLUMNS * 4), region.width);
                int y = inset((row * 4 + subY) * region.height / (ROWS * 4), region.height);
                int sx = region.x + x;
                int sy = region.y + y;
                int middle = pixels.luminance(sx, sy);
                int left = pixels.luminance(sx - spread, sy);
                int right = pixels.luminance(sx + spread, sy);
                int top = pixels.luminance(sx, sy - spread);
                int bottom = pixels.luminance(sx, sy + spread);
                int high = Math.max(middle, Math.max(Math.max(left, right), Math.max(top, bottom)));
                int low = Math.min(middle, Math.min(Math.min(left, right), Math.min(top, bottom)));
                if (high - low > bestContrast) {
                    bestContrast = high - low;
                    bestX = x;
                    bestY = y;
                    bestValue = (middle * 4 + left + right + top + bottom) / 8;
                }
            }
        }
        return new Sample(bestX, bestY, bestValue, bestContrast >= 26 ? 3 : 1);
    }

    private Match[] coarseSearch(Pixels pixels, IntegralLuma integral, Shape shape,
                                 int x, int y, int radius, int step) {
        Match[] seeds = new Match[SEEDS_PER_SCALE];
        int limit = radius / step;
        for (int row = -limit; row <= limit; row++) {
            for (int column = -limit; column <= limit; column++) {
                int nextX = x + column * step;
                int nextY = y + row * step;
                if (nextX < 0 || nextY < 0 || nextX + shape.width > pixels.width()
                        || nextY + shape.height > pixels.height()) continue;
                int error = 0;
                for (int r = 0; r < COARSE_ROWS; r++) {
                    for (int c = 0; c < COARSE_COLUMNS; c++) {
                        int mean = cellMean(integral, nextX, nextY, shape.width, shape.height, c, r);
                        error += Math.abs(mean - coarseTemplate[r * COARSE_COLUMNS + c]);
                    }
                }
                keepSeed(seeds, shape, nextX, nextY, error, step);
            }
        }
        return seeds;
    }

    private static void keepSeed(Match[] seeds, Shape shape, int x, int y, int error, int step) {
        int worst = 0;
        for (int i = 0; i < seeds.length; i++) {
            Match seed = seeds[i];
            if (seed != null && Math.abs(seed.x - x) <= step && Math.abs(seed.y - y) <= step) {
                if (error < seed.error) seeds[i] = new Match(shape, x, y, error);
                return;
            }
            if (seed == null || (seeds[worst] != null && seed.error > seeds[worst].error)) worst = i;
        }
        if (seeds[worst] == null || error < seeds[worst].error) {
            seeds[worst] = new Match(shape, x, y, error);
        }
    }

    private static int cellMean(IntegralLuma integral, int x, int y, int w, int h,
                                int column, int row) {
        return integral.mean(x + w * column / COARSE_COLUMNS, y + h * row / COARSE_ROWS,
            x + w * (column + 1) / COARSE_COLUMNS, y + h * (row + 1) / COARSE_ROWS);
    }

    private Match refine(Pixels pixels, Match seed, int step) {
        Match best = new Match(seed.shape, seed.x, seed.y,
            score(pixels, seed.shape, seed.x, seed.y));
        for (int y = seed.y - step; y <= seed.y + step; y++) {
            for (int x = seed.x - step; x <= seed.x + step; x++) {
                int error = score(pixels, seed.shape, x, y);
                if (error < best.error) best = new Match(seed.shape, x, y, error);
            }
        }
        return best;
    }

    private boolean better(Match candidate, Match best) {
        if (best == null || candidate.error != best.error) {
            return best == null || candidate.error < best.error;
        }
        return centerDistance(candidate, box) < centerDistance(best, box);
    }

    private static boolean ambiguous(Match best, Match[] matches) {
        int separation = Math.max(12, Math.min(best.shape.width, best.shape.height) / 3);
        Box region = new Box(best.x, best.y, best.shape.width, best.shape.height);
        for (Match other : matches) {
            if (other != null && other.error <= best.error + 2
                    && centerDistance(other, region) >= separation * 2) return true;
        }
        return false;
    }

    private static int centerDistance(Match match, Box region) {
        return Math.abs(2 * (match.x - region.x) + match.shape.width - region.width)
            + Math.abs(2 * (match.y - region.y) + match.shape.height - region.height);
    }

    private int score(Pixels pixels, Shape shape, int left, int top) {
        if (left < 0 || top < 0 || left + shape.width > pixels.width()
                || top + shape.height > pixels.height()) return 255;
        int sum = 0;
        int weights = 0;
        int radius = shape.radius;
        for (int i = 0; i < template.length; i++) {
            Sample sample = template[i];
            int x = left + shape.x[i];
            int y = top + shape.y[i];
            int value = (pixels.luminance(x, y) * 4 + pixels.luminance(x - radius, y)
                + pixels.luminance(x + radius, y) + pixels.luminance(x, y - radius)
                + pixels.luminance(x, y + radius)) / 8;
            sum += Math.abs(value - sample.value) * sample.weight;
            weights += sample.weight;
        }
        return (sum + weights / 2) / weights;
    }

    private static boolean fits(Pixels pixels, Box region) {
        return region.x >= 0 && region.y >= 0 && region.x + region.width <= pixels.width()
            && region.y + region.height <= pixels.height();
    }

    private static int smoothingRadius(int width, int height) {
        return Math.min(3, Math.max(1, Math.min(width, height) / 96));
    }

    private static int inset(int value, int limit) {
        return Math.max(3, Math.min(limit - 4, value));
    }

    /** Integral image over the small search neighborhood, sampled once per frame. */
    private static final class IntegralLuma {
        private static final int STEP = 4;
        private final int x;
        private final int y;
        private final int columns;
        private final int rows;
        private final int stride;
        private final int[] sums;

        IntegralLuma(Pixels pixels, int x, int y, int right, int bottom) {
            this.x = x;
            this.y = y;
            columns = (right - x + STEP - 1) / STEP;
            rows = (bottom - y + STEP - 1) / STEP;
            stride = columns + 1;
            sums = new int[stride * (rows + 1)];
            for (int row = 1; row <= rows; row++) {
                int scan = 0;
                int py = Math.min(bottom - 1, y + (row - 1) * STEP + STEP / 2);
                for (int col = 1; col <= columns; col++) {
                    int px = Math.min(right - 1, x + (col - 1) * STEP + STEP / 2);
                    scan += pixels.luminance(px, py);
                    sums[row * stride + col] = sums[(row - 1) * stride + col] + scan;
                }
            }
        }

        int mean(int left, int top, int right, int bottom) {
            int x0 = Math.min(columns - 1, Math.max(0, (left - x + STEP / 2) / STEP));
            int x1 = Math.min(columns, Math.max(x0 + 1, (right - x + STEP / 2) / STEP));
            int y0 = Math.min(rows - 1, Math.max(0, (top - y + STEP / 2) / STEP));
            int y1 = Math.min(rows, Math.max(y0 + 1, (bottom - y + STEP / 2) / STEP));
            int total = sums[y1 * stride + x1] - sums[y0 * stride + x1]
                - sums[y1 * stride + x0] + sums[y0 * stride + x0];
            return total / ((x1 - x0) * (y1 - y0));
        }
    }

    private final class Shape {
        final int width;
        final int height;
        final int radius;
        final int[] x = new int[template.length];
        final int[] y = new int[template.length];

        Shape(int width, int height) {
            this.width = Math.max(MIN_SIDE, width);
            this.height = Math.max(MIN_SIDE, height);
            radius = smoothingRadius(this.width, this.height);
            for (int i = 0; i < template.length; i++) {
                x[i] = inset((template[i].x * this.width + originalWidth / 2) / originalWidth,
                    this.width);
                y[i] = inset((template[i].y * this.height + originalHeight / 2) / originalHeight,
                    this.height);
            }
        }
    }

    private static final class Sample {
        final int x;
        final int y;
        final int value;
        final int weight;

        Sample(int x, int y, int value, int weight) {
            this.x = x;
            this.y = y;
            this.value = value;
            this.weight = weight;
        }
    }

    private static final class Match {
        final Shape shape;
        final int x;
        final int y;
        final int error;

        Match(Shape shape, int x, int y, int error) {
            this.shape = shape;
            this.x = x;
            this.y = y;
            this.error = error;
        }
    }
}
