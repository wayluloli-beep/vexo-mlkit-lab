"""Compare two *aggregate-only* Vexo diagnostics without identifying a session.

This cannot prove that snapshots came from one MediaProjection session: the
current v1 JSON has no session ID, counter epoch or monotonic snapshot timestamp.
No screens, OCR, fares or user identifiers are parsed, stored or printed.
"""
import argparse
import json
from pathlib import Path

try:
    from .live_diagnostic_audit import (
        analyze, DiagnosticInputError, COUNTERS, LATENCY,
        _unique_keys, MAX_BYTES,
    )
except ImportError:
    from live_diagnostic_audit import (
        analyze, DiagnosticInputError, COUNTERS, LATENCY,
        _unique_keys, MAX_BYTES,
    )

def compare(first, second):
    a = analyze(first)
    b = analyze(second)
    if first["schema"] != second["schema"]:
        return {"canCompare": False, "reason": "INCOMPATIBLE_DIAGNOSTIC_VERSIONS"}
    if not a["consistentCounters"] or not b["consistentCounters"]:
        return {
            "canCompare": False,
            "reason": "INDIVIDUAL_REPORT_CONSISTENCY_VIOLATION",
            "firstViolations": a["violations"],
            "secondViolations": b["violations"],
        }
    diffs = {key: b["counters"][key] - a["counters"][key] for key in COUNTERS}
    resets = sorted(k for k, delta in diffs.items() if delta < 0)
    latency_a, latency_b = a["latency"], b["latency"]
    if (latency_a is None) != (latency_b is None):
        return {"canCompare": False, "reason": "INCOMPATIBLE_DIAGNOSTIC_VERSIONS"}
    delta_samples = None
    if latency_a is not None:
        delta_samples = latency_b["ocrLatencySamples"] - latency_a["ocrLatencySamples"]
        if delta_samples < 0:
            resets.append("ocrLatencySamples")
    evidence_a = a["contextEvidenceCounts"]
    evidence_b = b["contextEvidenceCounts"]
    evidence_delta = None
    if evidence_a is not None:
        evidence_delta = {key: evidence_b[key] - evidence_a[key] for key in evidence_a}
        resets.extend(key for key, delta in evidence_delta.items() if delta < 0)
    v3_a, v3_b = a["v3Counters"], b["v3Counters"]
    v3_delta = None
    if v3_a is not None:
        v3_delta = {key: v3_b[key] - v3_a[key] for key in v3_a}
        resets.extend(key for key, delta in v3_delta.items() if delta < 0)
    notes = ["NO_SESSION_ID_OR_SNAPSHOT_TIMESTAMP_IN_REPORT"]
    if resets:
        return {"canCompare": False, "reason": "POSSIBLE_SESSION_RESET_OR_INCONSISTENT_COUNTERS",
                "decreasedCounters": sorted(resets), "notes": notes}
    # A monotonic sequence is only consistent with a shared session, not proof.
    anomalies = []
    if latency_a is not None:
        old_n = latency_a["ocrLatencySamples"]
        new_n = latency_b["ocrLatencySamples"]
        if new_n >= old_n > 0 and new_n <= 19 and (
                latency_b["ocrLatencyP95Ms"] < latency_a["ocrLatencyMaxMs"]):
            anomalies.append("P95_DROPPED_BELOW_PREVIOUS_MAX_WITH_SMALL_SAMPLE_WINDOW")
        if delta_samples > diffs["ocrAttempts"]:
            anomalies.append("NEW_LATENCY_SAMPLES_EXCEED_NEW_OCR_ATTEMPTS")
    if v3_delta is not None:
        if v3_delta["discardedStaleOcrFrames"] > diffs["ocrCompleted"]:
            anomalies.append("NEW_STALE_FRAMES_EXCEED_NEW_OCR_COMPLETIONS")
        if v3_delta["candidatesWithout99Logo"] > diffs["offerContextCandidates"]:
            anomalies.append("NEW_NO_LOGO_CANDIDATES_EXCEED_NEW_CANDIDATES")
        if v3_delta["offerGateHeldFrames"] > diffs["offerContextCandidates"]:
            anomalies.append("NEW_HELD_FRAMES_EXCEED_NEW_CANDIDATES")
    if diffs["ocrCompleted"] > diffs["ocrAttempts"]:
        anomalies.append("NEW_OCR_COMPLETIONS_EXCEED_NEW_ATTEMPTS")
    if diffs["offersAlerted"] > diffs["offerContextCandidates"]:
        anomalies.append("NEW_ALERTS_EXCEED_NEW_CONTEXT_CANDIDATES")
    return {
        "canCompare": True,
        "sessionContinuityProven": False,
        "counterDeltasIfSameSession": diffs,
        "latencySampleDeltaIfSameSession": delta_samples,
        "evidenceDeltasIfSameSession": evidence_delta,
        "v3CounterDeltasIfSameSession": v3_delta,
        "crossSnapshotAnomalies": anomalies,
        "notes": notes,
        "interpretation": "Counter differences are conditional; uncertain classifications are not proven OCR errors; p95 can fluctuate without performance improvement",
    }


def _read(path):
    if path.stat().st_size > MAX_BYTES:
        raise DiagnosticInputError("oversized report")
    with path.open(encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=_unique_keys)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare two voluntary Vexo v1 reports, aggregate only")
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    args = ap.parse_args(argv)
    try:
        result = compare(_read(args.before), _read(args.after))
    except (OSError, UnicodeError, TypeError, ValueError):
        print('{"error":"INVALID_OR_UNSAFE_DIAGNOSTIC_REPORT"}')
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["canCompare"] and not result["crossSnapshotAnomalies"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
