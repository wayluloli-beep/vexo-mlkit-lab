"""Synthetic monotonic frame freshness model. Never ingest OCR text or screenshots."""
from dataclasses import dataclass
from collections import Counter

@dataclass(frozen=True)
class Event:
    acquired_ms: int
    started_ms: int
    completed_ms: int
    stopped_ms: int | None = None

def classify(e: Event, ttl_ms: int = 3000) -> str:
    if not isinstance(e, Event) or type(ttl_ms) is not int or ttl_ms <= 0:
        raise ValueError("invalid event")
    ts=(e.acquired_ms,e.started_ms,e.completed_ms)
    if any(type(t) is not int or t < 0 for t in ts) or not ts[0]<=ts[1]<=ts[2]:
        raise ValueError("invalid monotonic times")
    if e.stopped_ms is not None:
        if type(e.stopped_ms) is not int or e.stopped_ms < 0:
            raise ValueError("invalid stop")
        if e.completed_ms >= e.stopped_ms:
            return "AFTER_STOP"
    return "STALE" if e.completed_ms-e.acquired_ms > ttl_ms else "FRESH"

def audit(events: list[Event], ttl_ms: int = 3000) -> dict:
    if not isinstance(events,list) or len(events)>10000:
        raise ValueError("invalid events")
    statuses=Counter(classify(e,ttl_ms) for e in events)
    durations=sorted(e.completed_ms-e.started_ms for e in events)
    ages=sorted(e.completed_ms-e.acquired_ms for e in events)
    def pct(xs,p):
        return xs[(len(xs)*p+99)//100-1] if xs else None
    return {"completed":len(events),"fresh":statuses["FRESH"],
            "stale":statuses["STALE"],"afterStop":statuses["AFTER_STOP"],
            "ocrP50Ms":pct(durations,50),"ocrP95Ms":pct(durations,95),
            "frameAgeP95Ms":pct(ages,95),
            "classificationEligible":statuses["FRESH"],
            "scope":"fictional event timings; not Android or 99 evidence"}
