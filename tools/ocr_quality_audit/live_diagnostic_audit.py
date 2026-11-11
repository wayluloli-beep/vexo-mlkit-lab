"""Offline, aggregate-only Vexo live capture diagnostic checker (v1).

Never logs or repeats report text, screenshot content, IDs or OCR values.
A pipeline counter is evidence of stage activity, NOT proof of accurate OCR.
"""
import argparse
import json
from pathlib import Path

SCHEMA = "vexo-live-capture-diagnostic-v1"
COUNTERS = (
    "framesReceived", "ocrAttempts", "ocrCompleted", "ocrFailures",
    "offersAlerted", "offerContextCandidates", "screenContextUncertain",
    "screenContextRejected", "financiallyUnconfirmedFrames",
    "awaitingTwoStableReadings",
)
STRINGS = {"app", "diagnosticExplanation", "privacyNote"}
ENUMS = {"status", "diagnosticStage", "capturedWindowVisibility"}
FIELDS = {"schema", "noFieldAccuracyMeasured", "containsScreenshotOrOcrText"} | STRINGS | ENUMS | set(COUNTERS)
STAGES = {
    "WAITING_FOR_FRAMES", "NO_FRAMES_RECORDED", "FRAMES_WITHOUT_OCR_START",
    "OCR_FAILED", "OCR_NOT_COMPLETED", "OCR_OK_NO_CONFIRMED_OFFER",
    "OFFER_ALERT_GENERATED",
}
VISIBILITY = {"visível", "oculto", "não informada"}
MAX_BYTES = 8192


class DiagnosticInputError(ValueError):
    pass


def expected_stage(c, active):
    """Independent reconstruction of the Android CaptureHealthAnalyzer stage."""
    if c["framesReceived"] == 0:
        return "WAITING_FOR_FRAMES" if active else "NO_FRAMES_RECORDED"
    if c["ocrAttempts"] == 0:
        return "FRAMES_WITHOUT_OCR_START"
    if c["ocrCompleted"] == 0:
        return "OCR_FAILED" if c["ocrFailures"] else "OCR_NOT_COMPLETED"
    return "OFFER_ALERT_GENERATED" if c["offersAlerted"] else "OCR_OK_NO_CONFIRMED_OFFER"


def analyze(doc):
    if not isinstance(doc, dict) or set(doc) != FIELDS or doc.get("schema") != SCHEMA:
        raise DiagnosticInputError("unexpected schema or fields")
    if any(type(doc[f]) is not str for f in STRINGS):
        raise DiagnosticInputError("invalid descriptive field")
    if doc["status"] not in {"CAPTURE_ACTIVE", "CAPTURE_STOPPED"} or \
       doc["diagnosticStage"] not in STAGES or doc["capturedWindowVisibility"] not in VISIBILITY:
        raise DiagnosticInputError("invalid diagnostic enum")
    if doc["noFieldAccuracyMeasured"] is not True or doc["containsScreenshotOrOcrText"] is not False:
        raise DiagnosticInputError("privacy invariants not asserted")
    if any(type(doc[f]) is not int or not 0 <= doc[f] <= 1_000_000_000 for f in COUNTERS):
        raise DiagnosticInputError("invalid aggregate counter")
    c = {key: doc[key] for key in COUNTERS}
    errors = []
    if c["ocrAttempts"] > c["framesReceived"]:
        errors.append("OCR_ATTEMPTS_EXCEED_FRAMES")
    if c["ocrCompleted"] + c["ocrFailures"] > c["ocrAttempts"]:
        errors.append("OCR_OUTCOMES_EXCEED_ATTEMPTS")
    tagged = sum(c[key] for key in ("offerContextCandidates", "screenContextUncertain", "screenContextRejected"))
    if tagged > c["ocrCompleted"]:
        errors.append("CONTEXT_COUNTS_EXCEED_COMPLETED_OCR")
    if c["financiallyUnconfirmedFrames"] > c["offerContextCandidates"]:
        errors.append("FINANCIAL_GUARD_COUNT_EXCEEDS_CANDIDATES")
    if c["awaitingTwoStableReadings"] > c["offerContextCandidates"]:
        errors.append("STABILITY_COUNT_EXCEEDS_CANDIDATES")
    if c["offersAlerted"] > c["offerContextCandidates"]:
        errors.append("ALERTS_EXCEED_CANDIDATES")
    stage = expected_stage(c, doc["status"] == "CAPTURE_ACTIVE")
    if stage != doc["diagnosticStage"]:
        errors.append("DECLARED_STAGE_MISMATCH")
    notes = []
    if c["ocrCompleted"] > 0 and c["ocrCompleted"] < 3:
        notes.append("FEW_OCR_COMPLETIONS_NO_PRECISION_CLAIM")
    if c["framesReceived"] > c["ocrCompleted"]:
        notes.append("FRAME_OCR_DIFFERENCE_MAY_BE_THROTTLING_NOT_FAILURE")
    if c["offersAlerted"]:
        cause = "ALERT_RECORDED_NOT_OCR_ACCURACY"
    elif c["framesReceived"] == 0:
        cause = "NO_FRAMES"
    elif c["ocrAttempts"] == 0:
        cause = "NO_OCR_START"
    elif c["ocrCompleted"] == 0:
        cause = "OCR_INCOMPLETE_OR_FAILED"
    elif c["offerContextCandidates"] == 0:
        cause = "NO_CLASSIFIED_OFFER_EVIDENCE"
    elif c["financiallyUnconfirmedFrames"] == c["offerContextCandidates"]:
        cause = "FINANCIAL_GUARD_REJECTED_ALL_CANDIDATES"
    elif c["awaitingTwoStableReadings"] > 0:
        cause = "STABILITY_NOT_CONFIRMED_OR_EPISODE_UNCLEAR"
    else:
        cause = "NO_ALERT_CAUSE_UNRESOLVED_FROM_COUNTERS"
    return {
        "validSchema": True, "consistentCounters": not errors,
        "violations": errors, "diagnosticStageRecomputed": stage,
        "bottleneckHypothesis": cause,
        "counters": c,
        "notes": notes,
        "limits": "Counters cannot identify OCR content, prove offer identity, or certify 99 compatibility",
    }


def _unique_keys(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise DiagnosticInputError("duplicate report field")
        out[k] = v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit only aggregate Vexo v1 capture diagnostics")
    ap.add_argument("file", type=Path)
    args = ap.parse_args(argv)
    try:
        if args.file.stat().st_size > MAX_BYTES:
            raise DiagnosticInputError("report too large")
        with args.file.open(encoding="utf-8") as file:
            doc = json.load(file, object_pairs_hook=_unique_keys)
        result = analyze(doc)
    except (OSError, UnicodeError, ValueError, TypeError):
        print('{"error":"INVALID_OR_UNSAFE_DIAGNOSTIC_REPORT"}')
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["consistentCounters"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
