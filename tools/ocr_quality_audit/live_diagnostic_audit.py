"""Offline, aggregate-only Vexo live capture diagnostic checker (v1).

Never logs or repeats report text, screenshot content, IDs or OCR values.
A pipeline counter is evidence of stage activity, NOT proof of accurate OCR.
"""
import argparse
import json
from pathlib import Path

SCHEMA = "vexo-live-capture-diagnostic-v1"
SCHEMA_V2 = "vexo-live-capture-diagnostic-v2"
SCHEMA_V3 = "vexo-live-capture-diagnostic-v3"
COUNTERS = (
    "framesReceived", "ocrAttempts", "ocrCompleted", "ocrFailures",
    "offersAlerted", "offerContextCandidates", "screenContextUncertain",
    "screenContextRejected", "financiallyUnconfirmedFrames",
    "awaitingTwoStableReadings",
)
LATENCY = (
    "ocrLatencySamples", "ocrLatencyLastMs", "ocrLatencyMeanMs",
    "ocrLatencyP50Ms", "ocrLatencyP95Ms", "ocrLatencyMaxMs",
)
STRINGS = {"app", "diagnosticExplanation", "privacyNote"}
ENUMS = {"status", "diagnosticStage", "capturedWindowVisibility"}
FIELDS = {"schema", "noFieldAccuracyMeasured", "containsScreenshotOrOcrText"} | STRINGS | ENUMS | set(COUNTERS)
FIELDS_WITH_LATENCY = FIELDS | set(LATENCY)
EVIDENCE_KEYS = (
    "ocrReadsExamined", "readsWithPriceMarker", "readsWithActionButton",
    "readsWithOfferModality", "readsWithTwoDistances", "readsWithTwoTimes",
    "readsWith99Marker", "readsWithPartialOfferEvidence",
)
FIELDS_V2 = FIELDS_WITH_LATENCY | {"contextEvidenceCounts"}
V3_COUNTERS = (
    "discardedStaleOcrFrames", "offerGateHeldFrames", "candidatesWithout99Logo",
)
FIELDS_V3 = FIELDS_V2 | set(V3_COUNTERS)
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
    if not isinstance(doc, dict):
        raise DiagnosticInputError("report must be an object")
    keys = set(doc)
    version = doc.get("schema")
    if not ((version == SCHEMA and keys in (FIELDS, FIELDS_WITH_LATENCY)) or
            (version == SCHEMA_V2 and keys == FIELDS_V2) or
            (version == SCHEMA_V3 and keys == FIELDS_V3)):
        raise DiagnosticInputError("unexpected schema or fields")
    if any(type(doc[f]) is not str for f in STRINGS):
        raise DiagnosticInputError("invalid descriptive field")
    if any(type(doc[key]) is not str for key in ENUMS):
        raise DiagnosticInputError("invalid diagnostic enum type")
    if doc["status"] not in {"CAPTURE_ACTIVE", "CAPTURE_STOPPED"} or \
       doc["diagnosticStage"] not in STAGES or doc["capturedWindowVisibility"] not in VISIBILITY:
        raise DiagnosticInputError("invalid diagnostic enum")
    if doc["noFieldAccuracyMeasured"] is not True or doc["containsScreenshotOrOcrText"] is not False:
        raise DiagnosticInputError("privacy invariants not asserted")
    if any(type(doc[f]) is not int or not 0 <= doc[f] <= 1_000_000_000 for f in COUNTERS):
        raise DiagnosticInputError("invalid aggregate counter")
    c = {key: doc[key] for key in COUNTERS}
    errors = []
    latency = None
    if keys in (FIELDS_WITH_LATENCY, FIELDS_V2, FIELDS_V3):
        if any(type(doc[f]) is not int or not 0 <= doc[f] <= 1_000_000_000 for f in LATENCY):
            raise DiagnosticInputError("invalid aggregate latency")
        latency = {key: doc[key] for key in LATENCY}
        sample_count = latency["ocrLatencySamples"]
        times = [latency[key] for key in LATENCY[1:]]
        if sample_count > c["ocrAttempts"]:
            errors.append("LATENCY_SAMPLES_EXCEED_OCR_ATTEMPTS")
        if sample_count == 0 and any(times):
            errors.append("LATENCY_WITHOUT_SAMPLES")
        if sample_count > 0 and (
            latency["ocrLatencyP50Ms"] > latency["ocrLatencyP95Ms"] or
            latency["ocrLatencyP95Ms"] > latency["ocrLatencyMaxMs"] or
            latency["ocrLatencyLastMs"] > latency["ocrLatencyMaxMs"] or
            latency["ocrLatencyMeanMs"] > latency["ocrLatencyMaxMs"]
        ):
            errors.append("LATENCY_QUANTILE_ORDER_VIOLATION")
        # Nearest-rank P95 is the maximum with 1-19 recorded samples.
        if 0 < sample_count <= 19 and latency["ocrLatencyP95Ms"] != latency["ocrLatencyMaxMs"]:
            errors.append("SMALL_SAMPLE_P95_MUST_EQUAL_MAX")

    evidence = None
    if version in (SCHEMA_V2, SCHEMA_V3):
        raw_evidence = doc["contextEvidenceCounts"]
        if type(raw_evidence) is not dict or set(raw_evidence) != set(EVIDENCE_KEYS):
            raise DiagnosticInputError("invalid evidence object or keys")
        if any(type(raw_evidence[key]) is not int or
               not 0 <= raw_evidence[key] <= 1_000_000_000 for key in EVIDENCE_KEYS):
            raise DiagnosticInputError("invalid aggregate evidence counter")
        evidence = {key: raw_evidence[key] for key in EVIDENCE_KEYS}
        examined = evidence["ocrReadsExamined"]
        if examined > c["ocrCompleted"]:
            errors.append("EVIDENCE_READS_EXCEED_COMPLETED_OCR")
        for key in EVIDENCE_KEYS[1:]:
            if evidence[key] > examined:
                errors.append("EVIDENCE_SIGNAL_EXCEEDS_READS")
                break
        if evidence["readsWithPartialOfferEvidence"] > evidence["readsWithPriceMarker"]:
            errors.append("PARTIAL_OFFER_EXCEEDS_PRICE_MARKER")

    v3_counters = None
    if version == SCHEMA_V3:
        if any(type(doc[key]) is not int or not 0 <= doc[key] <= 1_000_000_000
               for key in V3_COUNTERS):
            raise DiagnosticInputError("invalid v3 aggregate counter")
        v3_counters = {key: doc[key] for key in V3_COUNTERS}
        stale = v3_counters["discardedStaleOcrFrames"]
        if stale > c["ocrCompleted"]:
            errors.append("STALE_FRAMES_EXCEED_COMPLETED_OCR")
        if v3_counters["offerGateHeldFrames"] > c["offerContextCandidates"]:
            errors.append("HELD_FRAMES_EXCEED_CANDIDATES")
        if v3_counters["candidatesWithout99Logo"] > c["offerContextCandidates"]:
            errors.append("CANDIDATES_WITHOUT_LOGO_EXCEED_CANDIDATES")
        if evidence["ocrReadsExamined"] > c["ocrCompleted"] - stale:
            errors.append("EVIDENCE_READS_EXCEED_FRESH_OCR")

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
    if evidence is not None:
        notes.append("EVIDENCE_SIGNALS_OVERLAP_NOT_ACCURACY_DENOMINATORS")
        notes.append("MISSING_MARKERS_MAY_BE_MAP_PLAYER_AD_OR_INCOMPLETE_OCR")
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
        "latency": latency,
        "contextEvidenceCounts": evidence,
        "v3Counters": v3_counters,
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
