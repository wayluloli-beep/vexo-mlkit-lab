"""Fictional mirror of PR37 OfferEpisodeGate.observeAt for alert risk studies.

No real fare, OCR text, route or passenger data. The independent truth group
comes from a human-annotated synthetic episode, never from Android.
PR37 gate uses no actual screenshot-based offer identity; these tests expose
what can and cannot be inferred from repeated numeric fingerprints.
"""
from dataclasses import dataclass
from collections import Counter
import re

_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")


@dataclass(frozen=True)
class Sample:
    t_ms: int
    context: str  # OFFER, UNCERTAIN, DEFINITE_NON_OFFER
    visual_episode: str = ""  # fixture-only, independent of OCR numbers
    fingerprint: str = ""    # fictional opaque equality token


class Pr37GateMirror:
    """Mirror the PR37 branch gate; not a claim of executing Android/Java."""
    def __init__(self):
        self.fingerprint = ""
        self.matched = 0
        self.uncertain_count = 0
        self.last_valid_ms = -1
        self.last_alert_ms = -1
        self.pending = ""
        self.pending_count = 0
        self.pending_last_ms = -1
        self.absent = 0
        self.alerted = False

    def uncertain(self):
        self.absent = 0
        if not self.alerted and self.matched > 0:
            self.uncertain_count += 1
            if self.uncertain_count >= 2:
                self.matched, self.fingerprint = 0, ""
                self.last_valid_ms, self.uncertain_count = -1, 0
        if self.alerted:
            self.pending, self.pending_count, self.pending_last_ms = "", 0, -1

    def non_offer(self):
        self.absent = min(2, self.absent + 1)
        if self.absent < 2:
            if not self.alerted:
                self.matched, self.last_valid_ms, self.uncertain_count = 0, -1, 0
            return False
        closed = self.alerted or bool(self.fingerprint)
        self.__init__()
        return closed

    def observe(self, next_fingerprint, t_ms):
        if not next_fingerprint:
            self.uncertain()
            return False
        self.absent = 0
        if self.alerted:
            if next_fingerprint != self.fingerprint:
                if self.last_alert_ms < 0 or t_ms < self.last_alert_ms or t_ms - self.last_alert_ms < 7500:
                    self.pending, self.pending_count, self.pending_last_ms = "", 0, -1
                    return False
                if (next_fingerprint != self.pending or self.pending_last_ms < 0 or
                    t_ms < self.pending_last_ms or t_ms - self.pending_last_ms > 5500):
                    self.pending, self.pending_count = next_fingerprint, 1
                else:
                    self.pending_count = min(3, self.pending_count + 1)
                self.pending_last_ms = t_ms
                if self.pending_count < 3:
                    return False
                self.fingerprint = next_fingerprint
                self.last_alert_ms = t_ms
                self.pending, self.pending_count, self.pending_last_ms = "", 0, -1
                return True
            self.pending, self.pending_count, self.pending_last_ms = "", 0, -1
            return False
        if (next_fingerprint != self.fingerprint or self.matched == 0 or
            self.last_valid_ms < 0 or t_ms < self.last_valid_ms or
            t_ms - self.last_valid_ms > 5500):
            self.fingerprint, self.matched = next_fingerprint, 1
        else:
            self.matched = min(2, self.matched + 1)
        self.last_valid_ms, self.uncertain_count = t_ms, 0
        if self.matched < 2:
            return False
        self.alerted, self.last_alert_ms = True, t_ms
        return True


def replay(samples):
    gate = Pr37GateMirror()
    alerts = Counter()
    seen = set()
    prev_t = -1
    for x in samples:
        if not isinstance(x, Sample) or type(x.t_ms) is not int or x.t_ms < prev_t:
            raise ValueError("invalid synthetic sample time")
        prev_t = x.t_ms
        if x.context not in {"OFFER", "UNCERTAIN", "DEFINITE_NON_OFFER"}:
            raise ValueError("invalid synthetic context")
        for token in (x.visual_episode, x.fingerprint):
            if type(token) is not str or (token and not _TOKEN.fullmatch(token)):
                raise ValueError("non-opaque fixture identity")
        if x.context == "OFFER":
            if not x.visual_episode or not x.fingerprint:
                raise ValueError("fixture offer requires truth and fingerprint")
            seen.add(x.visual_episode)
            if gate.observe(x.fingerprint, x.t_ms):
                alerts[x.visual_episode] += 1
        elif x.context == "UNCERTAIN":
            gate.uncertain()
        else:
            gate.non_offer()
    return {
        "visualEpisodes": len(seen),
        "notifiedVisualEpisodes": len(alerts),
        "alertAttempts": sum(alerts.values()),
        "duplicatesSameVisualEpisode": sum(max(0, c - 1) for c in alerts.values()),
        "visualEpisodesNotAlerted": len(seen - set(alerts)),
        "scope": "PR37 source-model synthetic fixture, not Android runtime/OCR accuracy",
    }


def one_card_with_consistent_numeric_jitter():
    o = lambda t, fp: Sample(t, "OFFER", "one-visual-card", fp)
    return [o(0, "correct"), o(1000, "correct"),
            o(8500, "wrong"), o(9200, "wrong"), o(9900, "wrong")]


def distinct_cards_without_map():
    o = lambda t, group, fp: Sample(t, "OFFER", group, fp)
    return [o(0, "A", "value-A"), o(1000, "A", "value-A"),
            o(8500, "B", "value-B"), o(9200, "B", "value-B"), o(9900, "B", "value-B")]
