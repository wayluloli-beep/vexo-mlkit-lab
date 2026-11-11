#!/usr/bin/env python3
"""Synthetic Vexo safety policy for temporally valid offer notifications.

This is an independent reference model, NOT the Android implementation or a
claim of OCR accuracy. All fixtures use abstract labels; no video, image,
location, passenger information, real prices or raw OCR are required.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re


class Kind(str, Enum):
    OFFER = "OFFER"
    OFFER_LIST = "OFFER_LIST"
    MAP = "MAP"
    UNCERTAIN = "UNCERTAIN"
    EXPIRED = "EXPIRED"
    ADVERTISEMENT = "ADVERTISEMENT"
    STOP = "STOP"


@dataclass(frozen=True)
class Frame:
    kind: Kind
    captured_ms: int
    completed_ms: int
    fingerprint: str = "synthetic-A"
    financial_safe: bool = True
    actionable: bool = True


class NotificationPolicy:
    """Fail closed on stale recognition and terminal/expired content.

    Two matching valid observations are required for a single visual episode.
    Explicit expiration blocks that episode; only two confirmed non-offer
    frames unlock a *new* visual episode. Numeric identity is not trip identity.
    """

    def __init__(self, max_frame_age_ms: int = 3000):
        if max_frame_age_ms < 1:
            raise ValueError("max_frame_age_ms must be positive")
        self.max_frame_age_ms = max_frame_age_ms
        self.active = True
        self.alerted = False
        self.fingerprint = ""
        self.matched = 0
        self.absent = 0
        self.barrier_ms = -1
        self.blocked_after_expiry = False
        self.last_completed_ms = -1
        self.alerts: list[int] = []

    def _clear_episode(self) -> None:
        self.fingerprint = ""
        self.alerted = False
        self.matched = 0

    def observe(self, frame: Frame) -> bool:
        if frame.completed_ms < self.last_completed_ms:
            raise ValueError("completion order must be monotonic")
        self.last_completed_ms = frame.completed_ms

        if frame.kind == Kind.STOP:
            self.active = False
            self.barrier_ms = max(self.barrier_ms, frame.captured_ms)
            self._clear_episode()
            return False
        if not self.active:
            return False

        # Capture timestamp is the only source for freshness. Completion time
        # or timestamp of the latest result cannot make an old frame fresh.
        if (frame.captured_ms < 0 or frame.completed_ms < frame.captured_ms or
                frame.completed_ms - frame.captured_ms > self.max_frame_age_ms):
            self.matched = 0
            return False

        if frame.kind in (Kind.EXPIRED, Kind.ADVERTISEMENT):
            self.barrier_ms = max(self.barrier_ms, frame.captured_ms)
            self._clear_episode()
            self.absent = 0
            self.blocked_after_expiry = True
            return False

        # A late OCR callback from the old card must not resurrect it even
        # when its callback finishes AFTER an explicit expiry/map transition.
        if frame.captured_ms <= self.barrier_ms:
            return False

        if frame.kind == Kind.MAP:
            self.absent += 1
            self.matched = 0
            if self.absent >= 2:
                self._clear_episode()
                self.blocked_after_expiry = False
                self.barrier_ms = max(self.barrier_ms, frame.captured_ms)
            return False

        if frame.kind == Kind.UNCERTAIN:
            self.matched = 0
            self.absent = 0
            return False

        if frame.kind not in (Kind.OFFER, Kind.OFFER_LIST):
            return False

        self.absent = 0
        if self.blocked_after_expiry or not frame.financial_safe or not frame.actionable:
            self.matched = 0
            return False
        if self.alerted:
            # Different OCR numbers are not proof that a second trip exists.
            return False
        if frame.fingerprint != self.fingerprint:
            self.fingerprint = frame.fingerprint
            self.matched = 1
            return False

        self.matched += 1
        if self.matched < 2:
            return False
        self.alerted = True
        self.alerts.append(frame.completed_ms)
        return True


def review_source(service: str, classifier: str) -> list[dict[str, str]]:
    """Conservative feature-presence checks, not Java control-flow proofs."""
    from check_contract import _strip_java_comments
    s = _strip_java_comments(service)
    c = _strip_java_comments(classifier)
    expected = {
        "EXPIRATION_EXPLICITLY_CLASSIFIED":
            bool(re.search(r"(?:EXPIRED|EXPIRADA|EXPIROU|OFFER_EXPIRED)", c, re.I)),
        "OFFER_LIST_DISTINCT_FROM_SINGLE_CARD":
            bool(re.search(r"\b(?:OFFER_LIST_CANDIDATE|OFFER_LIST_CONFIRMED)\b", c)),
        "LATE_OCR_FRAME_AGE_CHECK":
            bool(re.search(r"(?:capturedAtMs|frameCapturedAt|frameTimestampMs|captureTimeMs)", s)
                 and re.search(r"(?:MAX_FRAME_AGE|MAX_OFFER_AGE|FRAME_TTL|isFreshFrame)", s)),
    }
    return [
        {
            "code": name,
            "status": "PASS" if yes else "FAIL",
            "detail": (
                "Indicador de fonte encontrado — exige teste Android real"
                if yes else "Sem regra explícita detectada; integração Android pendente"
            ),
        } for name, yes in expected.items()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab"
    service = root / "LiveCaptureService.java"
    classifier = root / "ScreenContextClassifier.java"
    if service.is_file() and classifier.is_file():
        items = review_source(service.read_text(encoding="utf-8"),
                              classifier.read_text(encoding="utf-8"))
    else:
        items = [{"code": "ANDROID_SOURCE_PRESENT", "status": "SKIP",
                  "detail": "Branch de auditoria sem serviço Android; execute com --root no checkout Android"}]
    if args.json:
        print(json.dumps({"checks": items}, ensure_ascii=False, indent=2))
    else:
        for item in items:
            print(item["status"], item["code"], item["detail"])
    return int(any(item["status"] == "FAIL" for item in items))


if __name__ == "__main__":
    raise SystemExit(main())
