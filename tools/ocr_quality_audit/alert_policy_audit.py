"""Fictional trace model of the PR #24 notification policy; never ingests OCR."""
from dataclasses import dataclass
from collections import Counter


@dataclass(frozen=True)
class Frame:
    at_ms: int
    context: str
    group: str = ""     # independent identity given ONLY by a synthetic fixture
    fingerprint: str = ""  # opaque equality token, never a route, fare or OCR text


def replay_value_cooldown(frames, cooldown_ms=25_000):
    """Mirror the Android two-consecutive-scan + fingerprint/cooldown logic.

    This is a model based on code review, not Android runtime instrumentation.
    It returns only aggregate counters; never emits fixture identifiers.
    """
    last_fingerprint = ""
    last_notified = ""
    last_notification_at = -1
    consecutive = 0
    last_at = -1
    attempts = Counter()
    eligible = set()
    last_group = ""
    group_reads = 0
    for frame in frames:
        if not isinstance(frame, Frame):
            raise ValueError("invalid fixture frame")
        if type(frame.at_ms) is not int or frame.at_ms < last_at:
            raise ValueError("fixture clock must be nondecreasing")
        if frame.context not in {"OFFER_CANDIDATE", "NON_OFFER", "UNCERTAIN"}:
            raise ValueError("invalid fixture context")
        last_at = frame.at_ms
        if frame.context != "OFFER_CANDIDATE" or not frame.fingerprint:
            last_fingerprint, consecutive, last_group, group_reads = "", 0, "", 0
            continue
        if frame.fingerprint == last_fingerprint:
            consecutive += 1
        else:
            last_fingerprint, consecutive = frame.fingerprint, 1
        if frame.group and frame.group == last_group:
            group_reads += 1
        else:
            last_group, group_reads = frame.group, 1
        if frame.group and group_reads >= 2:
            eligible.add(frame.group)
        if consecutive < 2:
            continue
        if (frame.fingerprint == last_notified and last_notification_at >= 0
                and frame.at_ms - last_notification_at < cooldown_ms):
            continue
        last_notified, last_notification_at = frame.fingerprint, frame.at_ms
        if frame.group:
            attempts[frame.group] += 1
    return {
        "eligibleUniqueFixtureOffers": len(eligible),
        "notifiedUniqueFixtureOffers": len(attempts),
        "notificationAttempts": sum(attempts.values()),
        "duplicateAlertsForSameFixtureOffer": sum(max(0, n-1) for n in attempts.values()),
        "eligibleOffersNeverNotified": len(eligible - set(attempts)),
        "scope": "synthetic model of PR24 Java policy, not an observed Android execution",
    }


def held_card_trace():
    return [Frame(i * 1_500, "OFFER_CANDIDATE", "fixture-A", "opaque-same")
            for i in range(23)]


def transition_same_values_trace():
    # Two independent fictitious offers A and B with identical abstract values.
    # A definite non-offer screen separates them. B starts within 25s of A.
    return [Frame(0, "OFFER_CANDIDATE", "fixture-A", "opaque-value"),
            Frame(1_500, "OFFER_CANDIDATE", "fixture-A", "opaque-value"),
            Frame(2_000, "NON_OFFER"),
            Frame(3_000, "OFFER_CANDIDATE", "fixture-B", "opaque-value"),
            Frame(4_500, "OFFER_CANDIDATE", "fixture-B", "opaque-value")]
