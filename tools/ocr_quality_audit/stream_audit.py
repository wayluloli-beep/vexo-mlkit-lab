"""Auditoria de eventos temporais fictícios; não ingere pixels nem OCR bruto."""
from dataclasses import dataclass
from collections import Counter

@dataclass(frozen=True)
class Event:
    kind: str
    epoch: int
    seq: int = 0
    context: str = "UNCERTAIN"
    group: str = ""
    guard_blocked: bool = True
    notified: bool = False
    history_written: bool = False
    inference_ms: int = 0
    roi_passes: int = 0
    unsafe_financial: bool = False

def audit_stream(events):
    """Conta frames, ofertas opacas e sessões sem inferir identidade por preço."""
    active = None
    stopped = set()
    last_seq = -1
    seen = set()
    notified = set()
    counts = Counter()
    errors = []
    for index, e in enumerate(events):
        if e.kind == "start":
            if active is not None or e.epoch in stopped:
                errors.append((index, "invalid_start"))
            else:
                active, last_seq = e.epoch, -1
                counts["sessions"] += 1
            continue
        if e.kind == "stop":
            if active != e.epoch:
                errors.append((index, "invalid_stop"))
            else:
                stopped.add(e.epoch)
                active = None
            continue
        if e.kind not in ("frame", "callback"):
            errors.append((index, "unknown_event"))
            continue
        if active != e.epoch:
            counts["late_or_foreign_events"] += 1
            if e.notified or e.history_written:
                errors.append((index, "callback_after_stop_applied"))
            continue
        if e.kind == "frame":
            counts["frames"] += 1
            if e.seq <= last_seq:
                errors.append((index, "nonmonotonic_frame"))
            last_seq = max(last_seq, e.seq)
            continue
        counts["callbacks"] += 1
        if e.seq > last_seq or e.seq < 0:
            errors.append((index, "callback_without_frame"))
        if e.context == "OFFER_CANDIDATE":
            counts["offer_candidate_callbacks"] += 1
            if e.group:
                key = (e.epoch, e.group)
                seen.add(key)
                if e.notified:
                    if key in notified:
                        errors.append((index, "duplicate_notification"))
                    notified.add(key)
            else:
                counts["unlabeled_candidates"] += 1
        elif e.context == "NON_OFFER":
            counts["non_offer_callbacks"] += 1
            if e.notified:
                errors.append((index, "notification_on_non_offer"))
        else:
            counts["uncertain_callbacks"] += 1
            if e.notified:
                errors.append((index, "notification_on_uncertain"))
        if e.history_written:
            errors.append((index, "automatic_history_write"))
        if e.unsafe_financial and not e.guard_blocked:
            errors.append((index, "unsafe_financial_unblocked"))
        if e.inference_ms < 0 or e.roi_passes < 0:
            errors.append((index, "negative_cost"))
        counts["inference_ms_total"] += max(0, e.inference_ms)
        counts["roi_passes_total"] += max(0, e.roi_passes)
        if e.guard_blocked:
            counts["guard_abstentions"] += 1
    counts["unique_labeled_offers"] = len(seen)
    counts["notifications"] = len(notified)
    return {"counts": dict(counts), "violations": errors}
