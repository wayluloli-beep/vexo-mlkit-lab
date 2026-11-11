"""Synthetic model: event-driven ImageReader + one-in-flight OCR throttle.

Shows why N received frames do not imply >=2 OCR attempts. It does NOT
measure the Android service, and never accesses pixels or OCR content.
"""


def replay_capture_frames(frame_times_ms, *, ocr_ms, minimum_interval_ms=1400):
    if type(ocr_ms) is not int or ocr_ms < 0:
        raise ValueError("invalid synthetic OCR duration")
    if type(minimum_interval_ms) is not int or minimum_interval_ms < 250:
        raise ValueError("invalid synthetic throttle interval")
    previous_frame = -1
    last_start = None
    busy_until = None
    starts = []
    rejected_busy = 0
    rejected_interval = 0
    for t in frame_times_ms:
        if type(t) is not int or t < 0 or t < previous_frame:
            raise ValueError("frames require nondecreasing nonnegative synthetic timestamps")
        previous_frame = t
        if busy_until is not None and t < busy_until:
            rejected_busy += 1
            continue
        if last_start is not None and t - last_start < minimum_interval_ms:
            rejected_interval += 1
            continue
        starts.append(t)
        last_start = t
        busy_until = t + ocr_ms
    return {
        "framesInFixture": len(frame_times_ms),
        "ocrStartsPossible": len(starts),
        "framesSkippedWhileOcrBusy": rejected_busy,
        "framesSkippedByRateLimit": rejected_interval,
        "twoIndependentOcrStartsPossible": len(starts) >= 2,
        "scope": "synthetic scheduling model; NOT device performance or OCR accuracy",
    }
