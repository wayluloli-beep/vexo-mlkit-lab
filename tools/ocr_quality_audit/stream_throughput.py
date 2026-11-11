"""Synthetic throughput/first-offer metrics for a MediaProjection event trace.

No screenshots, OCR text, locations, or user identifiers. This is NOT a
measurement of Android/99 performance. Times are supplied by fixtures.
"""
from statistics import median
from stream_audit import Event, audit_stream


def _percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    # nearest-rank, explicitly documented for small synthetic samples
    import math
    return values[max(0, math.ceil(len(values) * pct / 100) - 1)]


def summarize_trace(events):
    result = audit_stream(events)
    frames = {}
    active = None
    starts = {}
    offer_first = {}
    notification_first = {}
    ocr_durations = []
    roi_passes = 0
    for event in events:
        if not isinstance(event, Event):
            continue
        if event.kind == "start":
            active = event.epoch
        elif event.kind == "stop" and active == event.epoch:
            active = None
        elif event.epoch != active:
            continue
        elif event.kind == "frame" and event.at_ms is not None:
            frames[(event.epoch, event.seq)] = event.at_ms
            if event.context == "OFFER_CANDIDATE" and event.group:
                offer_first.setdefault((event.epoch, event.group), event.at_ms)
        elif event.kind == "inference_start" and event.at_ms is not None:
            starts[(event.epoch, event.seq)] = event.at_ms
        elif event.kind == "inference_end" and event.at_ms is not None:
            key = (event.epoch, event.seq)
            if key in starts:
                duration = event.at_ms - starts.pop(key)
                if duration >= 0:
                    ocr_durations.append(duration)
        elif event.kind == "callback":
            roi_passes += max(0, event.roi_passes)
            if event.context == "OFFER_CANDIDATE" and event.group:
                key = (event.epoch, event.group)
                if key not in offer_first and (event.epoch, event.seq) in frames:
                    offer_first[key] = frames[(event.epoch, event.seq)]
                if event.notified and not event.guard_blocked and event.at_ms is not None:
                    notification_first.setdefault(key, event.at_ms)
    latencies = [
        notification_first[key] - started
        for key, started in offer_first.items()
        if key in notification_first and notification_first[key] >= started
    ]
    timestamps = [e.at_ms for e in events if isinstance(e, Event) and e.at_ms is not None]
    span = max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 0
    counts = result["counts"]
    return {
        "frames": counts.get("frames", 0),
        "unique_offers": counts.get("unique_labeled_offers", 0),
        "notifications": counts.get("notifications", 0),
        "violations": result["violations"],
        "observed_span_ms": span,
        "frames_per_second": round(counts.get("frames", 0) * 1000 / span, 3) if span > 0 else None,
        "ocr_completed_timed": len(ocr_durations),
        "ocr_p50_ms": median(ocr_durations) if ocr_durations else None,
        "ocr_p95_ms": _percentile(ocr_durations, 95),
        "first_offer_alert_p50_ms": median(latencies) if latencies else None,
        "first_offer_alert_p95_ms": _percentile(latencies, 95),
        "offer_alerts_measured": len(latencies),
        "roi_passes": roi_passes,
        "roi_passes_per_alert": round(roi_passes / len(notification_first), 3) if notification_first else None,
        "pending_at_stop": counts.get("inferences_pending_at_stop", 0),
    }
