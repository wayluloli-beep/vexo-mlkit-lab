package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import com.vexo.mlkitlab.FastCardVisualTracker.Pixels;

/** Binds an asynchronous OCR result to the currently observed target pixels. */
final class TargetReadingState {
    private long revision;
    private long signature;
    private int observations;

    boolean observe(long currentSignature) {
        if (observations == 0 || signature != currentSignature) {
            revision++;
            signature = currentSignature;
            observations = 1;
            return true;
        }
        observations = 2;
        return false;
    }

    void clear() {
        revision++;
        observations = 0;
    }

    long revision() {
        return revision;
    }

    boolean ready() {
        return observations == 2;
    }

    boolean accepts(long resultRevision) {
        return ready() && revision == resultRevision;
    }

    static long signature(Pixels pixels, Box box) {
        // Read only inside the target, independent of its absolute position or the map.
        int columns = Math.min(112, box.width);
        int rows = Math.min(80, box.height);
        long hash = 0xcbf29ce484222325L;
        for (int row = 0; row < rows; row++) {
            int y = box.y + row * box.height / rows;
            for (int column = 0; column < columns; column++) {
                int x = box.x + column * box.width / columns;
                hash = (hash ^ (pixels.luminance(x, y) >> 3)) * 0x100000001b3L;
            }
        }
        return hash;
    }
}
