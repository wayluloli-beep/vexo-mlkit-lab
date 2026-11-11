package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import java.nio.ByteBuffer;
import org.junit.Test;

public class CaptureFrameRecheckTest {
    private static CaptureFrameRecheck.Fingerprint screen(int pixel) {
        ByteBuffer rgba=ByteBuffer.allocate(4);
        rgba.putInt(0,pixel);
        return CaptureFrameRecheck.fingerprint(rgba,1,1,4,4);
    }

    @Test public void freshFrameOrRecentlyRevalidatedLateFrameCanPublish() {
        CaptureFrameRecheck check=new CaptureFrameRecheck(100,1000,screen(7));
        assertTrue(check.canPublish(3100));
        assertFalse(check.canPublish(3101));
        assertTrue(check.shouldSample(4500));
        check.observe(4500,2000,screen(7));
        assertFalse(check.shouldSample(4550));
        assertTrue(check.canPublish(4800));
        assertFalse(check.canPublish(4801));
    }

    @Test public void lateFrameCannotUseChangedMissingOrRepeatedSource() {
        CaptureFrameRecheck check=new CaptureFrameRecheck(100,1000,screen(7));
        check.observe(4500,1000,screen(7));
        assertFalse(check.canPublish(4510));
        check.observe(4600,2000,screen(7));
        check.observe(4700,3000,screen(8));
        assertFalse(check.canPublish(4710));
        check.observe(4800,4000,null);
        assertFalse(check.canPublish(4810));
    }

    @Test public void rowPaddingDoesNotChangeVisiblePixels() {
        ByteBuffer rgba=ByteBuffer.allocate(12);
        rgba.putInt(0,11);
        rgba.putInt(8,22);
        CaptureFrameRecheck.Fingerprint before=CaptureFrameRecheck.fingerprint(rgba,1,2,8,4);
        rgba.putInt(4,99);
        assertTrue(before.sameAs(CaptureFrameRecheck.fingerprint(rgba,1,2,8,4)));
        rgba.putInt(8,23);
        assertFalse(before.sameAs(CaptureFrameRecheck.fingerprint(rgba,1,2,8,4)));
    }
}
