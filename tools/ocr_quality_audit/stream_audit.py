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
    # True if the callback changed driver-visible results, not just received.
    ui_applied: bool = False
    # Timestamp only from synthetic fixture clock; optional, milliseconds.
    at_ms: int | None = None

def audit_stream(events):
    """Conta frames, ofertas opacas e sessões sem inferir identidade por preço."""
    active = None
    used_epochs = set()
    last_seq = -1
    last_applied_seq = -1
    frames = set()
    callbacks = set()
    inflight = set()
    seen = set()
    notified = set()
    counts = Counter()
    errors = []
    for index, e in enumerate(events):
        if not isinstance(e, Event):
            errors.append((index, "invalid_event"))
            continue
        if type(e.epoch) is not int or e.epoch < 0 or type(e.seq) is not int:
            errors.append((index, "invalid_epoch_or_sequence"))
            continue
        if e.kind == "start":
            if active is not None or e.epoch in used_epochs:
                errors.append((index, "invalid_start"))
            else:
                active, last_seq, last_applied_seq = e.epoch, -1, -1
                used_epochs.add(e.epoch)
                frames.clear()
                callbacks.clear()
                inflight.clear()
                counts["sessions"] += 1
            continue
        if e.kind == "stop":
            if active != e.epoch:
                errors.append((index, "invalid_stop"))
            else:
                counts["inferences_pending_at_stop"] += len(inflight)
                inflight.clear()
                active = None
            continue
        if e.kind not in ("frame", "callback", "inference_start", "inference_end"):
            errors.append((index, "unknown_event"))
            continue
        if active != e.epoch:
            counts["late_or_foreign_events"] += 1
            # Receiving a late event is safe; applying its result is not.
            if e.notified or e.history_written or e.ui_applied:
                errors.append((index, "callback_after_stop_applied"))
            continue
        if e.kind == "frame":
            counts["frames"] += 1
            if e.seq < 0 or e.seq <= last_seq:
                errors.append((index, "nonmonotonic_frame"))
            else:
                frames.add(e.seq)
                last_seq = e.seq
            continue
        if e.kind == "inference_start":
            counts["inference_starts"] += 1
            if e.seq not in frames:
                errors.append((index, "inference_without_frame"))
            if inflight:
                errors.append((index, "concurrent_inference"))
            inflight.add(e.seq)
            counts["max_simultaneous_inferences"] = max(
                counts["max_simultaneous_inferences"], len(inflight))
            continue
        if e.kind == "inference_end":
            counts["inference_ends"] += 1
            if e.seq not in inflight:
                errors.append((index, "inference_end_without_start"))
            else:
                inflight.remove(e.seq)
            continue
        counts["callbacks"] += 1
        if e.seq not in frames:
            errors.append((index, "callback_without_frame"))
        if e.seq in callbacks:
            errors.append((index, "duplicate_callback"))
        callbacks.add(e.seq)
        changed_visible_state = e.ui_applied or e.notified or e.history_written
        if e.seq < last_applied_seq:
            if changed_visible_state:
                errors.append((index, "stale_callback_applied"))
            else:
                counts["stale_callbacks_suppressed"] += 1
        elif changed_visible_state:
            last_applied_seq = e.seq
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
                if e.notified:
                    errors.append((index, "notification_without_offer_identity"))
        elif e.context == "NON_OFFER":
            counts["non_offer_callbacks"] += 1
            if e.notified:
                errors.append((index, "notification_on_non_offer"))
        elif e.context == "UNCERTAIN":
            counts["uncertain_callbacks"] += 1
            if e.notified:
                errors.append((index, "notification_on_uncertain"))
        else:
            errors.append((index, "unknown_context"))
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
    counts["inferences_left_running_at_end_of_trace"] = len(inflight)
    counts["unique_labeled_offers"] = len(seen)
    counts["notifications"] = len(notified)
    return {"counts": dict(counts), "violations": errors}
