"""Synthetic end-to-end frame/OCR/offer episode accounting, no user data."""
from dataclasses import dataclass
from collections import Counter
from stale_frame_gate_audit import Event, classify
from pr37_offer_rearm_audit import Pr37GateMirror

@dataclass(frozen=True)
class Frame:
    acquired_ms: int
    started_ms: int
    completed_ms: int
    context: str
    visual_episode: str = ""
    fingerprint: str = ""
    financial_ok: bool = False
    stopped_ms: int | None = None

def inspect(frames, ttl_ms=3000):
    if not isinstance(frames, list) or len(frames)>10000:
        raise ValueError("invalid frames")
    gate=Pr37GateMirror()
    counts=Counter()
    seen=set()
    alerted=set()
    attempts=Counter()
    first_seen={}
    first_alert={}
    last=-1
    for f in frames:
        if not isinstance(f, Frame) or f.acquired_ms < last:
            raise ValueError("unsorted frames")
        last=f.acquired_ms
        if f.context not in ("OFFER","MAP","POST","UNCERTAIN") or (
            f.context=="OFFER" and (not f.visual_episode or not f.fingerprint)
        ) or (f.context!="OFFER" and (f.visual_episode or f.fingerprint)):
            raise ValueError("invalid context or episode")
        # No OCR text, location or price: only opaque synthetic identifiers.
        import re
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", v)
               for v in (f.visual_episode,f.fingerprint) if v):
            raise ValueError("unsafe identity")
        status=classify(Event(f.acquired_ms,f.started_ms,
                              f.completed_ms,f.stopped_ms),ttl_ms)
        counts[status]+=1
        if status!="FRESH":
            continue
        counts["eligible"]+=1
        if f.context=="OFFER":
            seen.add(f.visual_episode)
            first_seen.setdefault(f.visual_episode,f.acquired_ms)
            if not f.financial_ok:
                counts["financialAbstentions"]+=1
                gate.uncertain()
                continue
            if gate.observe(f.fingerprint,f.completed_ms):
                attempts[f.visual_episode]+=1
                alerted.add(f.visual_episode)
                first_alert.setdefault(f.visual_episode,f.completed_ms)
        elif f.context in ("MAP","POST"):
            counts["definiteNonOffer"]+=1
            gate.non_offer()
        else:
            counts["uncertain"]+=1
            gate.uncertain()
    delays=[first_alert[e]-first_seen[e] for e in alerted]
    return {
        "frames":len(frames),"fresh":counts["FRESH"],"stale":counts["STALE"],
        "afterStop":counts["AFTER_STOP"],"eligible":counts["eligible"],
        "financialAbstentions":counts["financialAbstentions"],
        "definiteNonOffer":counts["definiteNonOffer"],"uncertain":counts["uncertain"],
        "visualEpisodes":len(seen),"notifiedVisualEpisodes":len(alerted),
        "alertAttempts":sum(attempts.values()),
        "duplicateAlerts":sum(max(0,v-1) for v in attempts.values()),
        "missedVisualEpisodes":len(seen-alerted),
        "firstAlertDelayMs":min(delays) if delays else None,
        "scope":"synthetic events; cannot measure 99 accuracy or real ROI"
    }
