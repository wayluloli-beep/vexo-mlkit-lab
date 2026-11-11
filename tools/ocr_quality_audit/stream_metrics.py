"""Aggregate-only metrics for synthetic streaming traces; no OCR content or prices."""
from math import ceil

def percentile95(values):
    """Nearest-rank p95 in milliseconds; None for empty samples."""
    if not values:
        return None
    if any(type(x) is not int or x < 0 for x in values):
        raise ValueError("durations must be nonnegative integer milliseconds")
    ordered = sorted(values)
    return ordered[ceil(.95 * len(ordered)) - 1]

def summarize(events):
    """Summarize fictitious events; identity is provided by fixture, never OCR."""
    first_frame, first_detected, durations = {}, {}, []
    roi = 0
    for event in events:
        if event.kind == "frame" and event.group:
            first_frame.setdefault((event.epoch, event.group), event.seq)
        elif event.kind == "callback":
            if event.inference_ms < 0 or event.roi_passes < 0:
                raise ValueError("negative processing cost")
            durations.append(event.inference_ms)
            roi += event.roi_passes
            if event.context == "OFFER_CANDIDATE" and event.group:
                first_detected.setdefault((event.epoch, event.group), event.seq)
    # seq measures frame order, not wall-clock time.
    frame_lags = [seq - first_frame[key] for key, seq in first_detected.items()
                  if key in first_frame and seq >= first_frame[key]]
    return {
        "ocr_latency_p95_ms": percentile95(durations),
        "ocr_latency_samples": len(durations),
        "roi_passes_total": roi,
        "unique_detected_fixture_offers": len(first_detected),
        "first_detection_lag_frames_p95": percentile95(frame_lags),
        "first_detection_lag_samples": len(frame_lags),
    }

def profile_roi_budget(missing_rating=True, missing_rides=True, passes_per_region=2):
    """Old duplicate region OCR vs shared crop OCR; model only, not measured."""
    if type(passes_per_region) is not int or passes_per_region < 1:
        raise ValueError("invalid passes")
    fields = int(bool(missing_rating)) + int(bool(missing_rides))
    old = fields * passes_per_region
    shared = passes_per_region if fields else 0
    return {"old_calls": old, "shared_calls": shared, "saved_calls": old - shared}
