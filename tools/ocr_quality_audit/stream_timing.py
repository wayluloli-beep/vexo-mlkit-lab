"""Timing audit for *synthetic* screen-capture sessions; no content or identities.

Ground truth for a frame is a test fixture annotation, not an OCR inference.
Missing timestamps remain unknown rather than being treated as fast detections.
"""
from math import ceil


def _p95(values):
    """Nearest-rank 95th percentile, in milliseconds; None for no samples."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[ceil(len(ordered) * 0.95) - 1]


def timing_metrics(events):
    active = None
    active_frame_times = {}
    frame_truth_first = {}
    candidate_first = {}
    alert_first = {}
    inference_samples = []
    invalid_durations = 0
    missing_timestamps = 0
    for e in events:
        if e.kind == "start":
            if active is None:
                active = e.epoch
                active_frame_times = {}
            continue
        if e.kind == "stop":
            if active == e.epoch:
                active = None
            continue
        if e.epoch != active:
            continue
        if e.kind == "frame":
            if e.at_ms is not None:
                active_frame_times[e.seq] = e.at_ms
            if e.context == "OFFER_CANDIDATE" and e.group:
                key = (e.epoch, e.group)
                if e.at_ms is None:
                    missing_timestamps += 1
                else:
                    frame_truth_first.setdefault(key, e.at_ms)
        if e.kind == "callback":
            if e.inference_ms > 0:
                inference_samples.append(e.inference_ms)
            if e.context != "OFFER_CANDIDATE" or not e.group:
                continue
            key = (e.epoch, e.group)
            if key not in frame_truth_first:
                continue
            if e.at_ms is None or e.seq not in active_frame_times:
                missing_timestamps += 1
                continue
            delay = e.at_ms - frame_truth_first[key]
            if delay < 0 or e.at_ms < active_frame_times[e.seq]:
                invalid_durations += 1
                continue
            candidate_first.setdefault(key, delay)
            if e.notified:
                alert_first.setdefault(key, delay)
    candidate_times = list(candidate_first.values())
    alert_times = list(alert_first.values())
    return {
        "fixtureOffersWithTimedFirstFrame": len(frame_truth_first),
        "offersWithFirstCandidate": len(candidate_first),
        "offersNeverDetectedInTrace": len(set(frame_truth_first) - set(candidate_first)),
        "firstCandidateLatencyP95Ms": _p95(candidate_times),
        "firstCandidateLatencyMinMs": min(candidate_times) if candidate_times else None,
        "offersWithFirstAlert": len(alert_first),
        "firstAlertLatencyP95Ms": _p95(alert_times),
        "inferenceSamples": len(inference_samples),
        "ocrInferenceP95Ms": _p95(inference_samples),
        "invalidNegativeDurations": invalid_durations,
        "missingTimingEvidence": missing_timestamps,
        "scope": "synthetic fixture timing only; no real 99 offer detection or device latency",
    }
