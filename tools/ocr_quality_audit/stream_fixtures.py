"""Synthetic frame-event fixtures for the Vexo MediaProjection OCR audit.

All group names are arbitrary test IDs. They are *not* inferred from OCR,
prices, addresses or screenshots. Times are artificial milliseconds.
"""
from stream_audit import Event as E


def event(kind, epoch=1, seq=0, t=None, context="UNCERTAIN", group="", **kwargs):
    return E(kind, epoch, seq, context, group, at_ms=t, **kwargs)


def _sorted_events(events):
    precedence = {"start": 0, "frame": 1, "inference_start": 2,
                  "inference_end": 3, "callback": 4, "stop": 5}
    return sorted(events, key=lambda e: (e.at_ms, precedence[e.kind]))


def repeated_offer(frames=30, interval_ms=100, sample_interval_ms=1400):
    """One offer in 30 frames; at most one inference per 1400 ms."""
    events = [event("start", t=0)]
    last_sample = -sample_interval_ms
    stable_reads = 0
    last_notified_at = None
    for seq in range(frames):
        t = 100 + seq * interval_ms
        events.append(event("frame", seq=seq, t=t,
                            context="OFFER_CANDIDATE", group="fixture-A"))
        if t - last_sample < sample_interval_ms:
            continue
        last_sample = t
        stable_reads += 1
        callback_at = t + 120
        notify = stable_reads >= 2 and (last_notified_at is None or
                                         callback_at - last_notified_at >= 25000)
        if notify:
            last_notified_at = callback_at
        events.append(event("inference_start", seq=seq, t=t))
        events.append(event("inference_end", seq=seq, t=callback_at))
        events.append(event("callback", seq=seq, t=callback_at,
                            context="OFFER_CANDIDATE", group="fixture-A",
                            notified=notify, ui_applied=notify,
                            guard_blocked=False, inference_ms=120))
    events.append(event("stop", t=100 + frames * interval_ms + 300))
    return _sorted_events(events)


def map_offer_map():
    events = [event("start", t=0)]
    for seq in range(15):
        t = 100 + seq * 200
        live = 5 <= seq < 10
        group = "fixture-A" if live else ""
        context = "OFFER_CANDIDATE" if live else "NON_OFFER"
        events += [event("frame", seq=seq, t=t, context=context, group=group),
                   event("callback", seq=seq, t=t + 60, context=context,
                         group=group, notified=seq == 5,
                         ui_applied=seq == 5, inference_ms=60)]
    events.append(event("stop", t=3400))
    return _sorted_events(events)


def equal_numbers_distinct_offers():
    """No numeric data is included; two different fixture identities stay distinct."""
    return [event("start", t=0),
            event("frame", seq=0, t=100, context="OFFER_CANDIDATE", group="offer-X"),
            event("callback", seq=0, t=180, context="OFFER_CANDIDATE", group="offer-X",
                  notified=True, ui_applied=True, guard_blocked=False, inference_ms=80),
            event("frame", seq=1, t=500, context="OFFER_CANDIDATE", group="offer-Y"),
            event("callback", seq=1, t=590, context="OFFER_CANDIDATE", group="offer-Y",
                  notified=True, ui_applied=True, guard_blocked=False, inference_ms=90),
            event("stop", t=600)]


def stopped_with_late_callback(applied=False):
    return [event("start", t=0), event("frame", seq=0, t=100),
            event("inference_start", seq=0, t=101), event("stop", t=120),
            event("callback", seq=0, t=200, context="OFFER_CANDIDATE",
                  group="fixture-A", ui_applied=applied, notified=applied)]


def all_scenarios():
    return {"repeat_30_frames": repeated_offer(),
            "map_offer_map": map_offer_map(),
            "equal_values_distinct_offers": equal_numbers_distinct_offers(),
            "stop_callback_discarded": stopped_with_late_callback(False),
            "stop_callback_applied": stopped_with_late_callback(True),
            "long_stable_offer_realerts": repeated_offer(frames=350)}
