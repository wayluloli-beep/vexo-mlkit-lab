package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import com.vexo.mlkitlab.FastCardVisualTracker.Pixels;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class ManualTargetTrackerTest {
    private static final Box SELECTED = new Box(63, 241, 182, 124);

    @Test public void followsTheMarkedItemWhileTheBackgroundMoves() {
        ManualTargetTracker tracker = new ManualTargetTracker();
        assertTrue(tracker.select(frame(SELECTED, 0, 1), SELECTED));
        assertNear(SELECTED, tracker.track(frame(SELECTED, 35, 1), 0, 0), 1);
        Box first = new Box(74, 182, 182, 124);
        assertNear(first, tracker.track(frame(first, 84, 1), 0, 0), 2);
        Box second = new Box(69, 119, 182, 124);
        assertNear(second, tracker.track(frame(second, 39, 1), 0, 0), 2);
        assertNear(first, tracker.track(frame(first, 6, 1), 0, 0), 2);
    }

    @Test public void followsAChangeInSizeAndPosition() {
        ManualTargetTracker tracker = new ManualTargetTracker();
        assertTrue(tracker.select(frame(SELECTED, 0, 1), SELECTED));
        Box larger = new Box(45, 218, 200, 136);
        assertNear(larger, tracker.track(frame(larger, 31, 1), 0, 0), 3);
    }

    @Test public void clearsWhenTheTargetLeavesAndRequiresAManualSelection() {
        ManualTargetTracker tracker = new ManualTargetTracker();
        assertTrue(tracker.select(frame(SELECTED, 0, 1), SELECTED));
        assertNull(tracker.track(frame(null, 15, 1), 0, 0));
        assertNull(tracker.track(frame(SELECTED, 18, 1), 0, 0));
    }

    @Test public void aSimilarItemInTheSamePlaceDoesNotInheritTheOutline() {
        ManualTargetTracker tracker = new ManualTargetTracker();
        assertTrue(tracker.select(frame(SELECTED, 0, 1), SELECTED));
        assertNull(tracker.track(frame(SELECTED, 0, 2), 0, 0));
    }

    @Test public void smallChangesInSeveralFieldsAreNotJustMotion() {
        ManualTargetTracker tracker = new ManualTargetTracker();
        assertTrue(tracker.select(frame(SELECTED, 0, 1), SELECTED));
        assertNull(tracker.track(frame(SELECTED, 0, 3), 0, 0));
    }

    @Test public void flatSelectionAndChangedFrameGeometryCannotKeepTheBox() {
        ManualTargetTracker tracker = new ManualTargetTracker();
        assertFalse(tracker.select(new Fixture(340, 490, null, -1, 1), SELECTED));
        assertTrue(tracker.select(frame(SELECTED, 0, 1), SELECTED));
        assertNull(tracker.track(new Fixture(490, 340, null, 0, 1), 0, 0));
    }

    @Test public void delayedOcrIsRejectedAfterSamePositionContentChangesOrDisappears() {
        TargetReadingState reading = new TargetReadingState();
        long initial = TargetReadingState.signature(frame(SELECTED, 0, 1), SELECTED);
        Box moved = new Box(63, 202, SELECTED.width, SELECTED.height);
        assertEquals(initial, TargetReadingState.signature(frame(moved, 24, 1), moved));
        assertTrue(reading.observe(initial));
        assertFalse(reading.ready());
        assertFalse(reading.observe(initial));
        long request = reading.revision();
        assertTrue(reading.accepts(request));

        long replacement = TargetReadingState.signature(frame(SELECTED, 29, 2), SELECTED);
        assertTrue(reading.observe(replacement));
        assertFalse(reading.accepts(request));
        reading.observe(replacement);
        assertTrue(reading.accepts(reading.revision()));
        assertFalse(reading.accepts(request));
        long last = reading.revision();
        reading.clear();
        assertFalse(reading.accepts(last));
    }

    private static Pixels frame(Box box, int background, int content) {
        return new Fixture(340, 490, box, background, content);
    }

    private static void assertNear(Box expected, Box actual, int tolerance) {
        assertNotNull(actual);
        String result = "got " + actual.x + "," + actual.y + " " + actual.width + "x" + actual.height;
        assertTrue(result, Math.abs(expected.x - actual.x) <= tolerance);
        assertTrue(result, Math.abs(expected.y - actual.y) <= tolerance);
        assertTrue(result, Math.abs(expected.width - actual.width) <= tolerance);
        assertTrue(result, Math.abs(expected.height - actual.height) <= tolerance);
    }

    private static final class Fixture implements Pixels {
        private final int width;
        private final int height;
        private final Box box;
        private final int background;
        private final int content;

        Fixture(int width, int height, Box box, int background, int content) {
            this.width = width;
            this.height = height;
            this.box = box;
            this.background = background;
            this.content = content;
        }

        @Override public int width() { return width; }
        @Override public int height() { return height; }

        @Override public int luminance(int x, int y) {
            if (x < 0 || y < 0 || x >= width || y >= height) throw new IndexOutOfBoundsException();
            if (box == null || x < box.x || y < box.y
                    || x >= box.x + box.width || y >= box.y + box.height) {
                return background < 0 ? 140 : ((x + background) / 17 + y / 23) % 3 * 24 + 123;
            }
            int sx = (x - box.x) * 182 / box.width;
            int sy = (y - box.y) * 124 / box.height;
            if (sx < 6 || sy < 6 || sx >= 176 || sy >= 118) return 52;
            if (content == 3 && sy >= 41 && sy < 47 && sx >= 24 && sx <= 145 && sx % 37 < 6) return 42;
            if (sy >= 89 && sy <= 109 && sx >= 16 && sx <= 165) return 92;
            if (sy >= 15 && sy <= 37 && sx >= 17 && sx <= 77) {
                return (sx / 6 + (content == 2 ? 2 : 1)) % 3 == 0 ? 32 : 225;
            }
            if (sy >= 52 && sy <= 75 && (sx + sy / 5) % 18 <= 5) return 78;
            return 231;
        }
    }
}
