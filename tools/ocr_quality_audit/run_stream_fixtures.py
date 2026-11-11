"""Execute only local synthetic MediaProjection temporal fixtures; no 99 screenshots."""
import json
from stream_audit import audit_stream
from stream_fixtures import all_scenarios
from stream_timing import timing_metrics

EXPECTED_VIOLATIONS = {
    "repeat_30_frames": set(),
    "map_offer_map": set(),
    "equal_values_distinct_offers": set(),
    "stop_callback_discarded": set(),
    "stop_callback_applied": {"callback_after_stop_applied"},
}


def run_suite():
    cases = []
    for name, events in all_scenarios().items():
        audited = audit_stream(events)
        actual = {v[1] for v in audited["violations"]}
        expected = EXPECTED_VIOLATIONS[name]
        summary = audited["counts"]
        metrics = timing_metrics(events)
        cases.append({"case": name, "pass": actual == expected,
                      "expectedViolations": sorted(expected),
                      "actualViolations": sorted(actual),
                      "frames": summary.get("frames", 0),
                      "offers": summary.get("unique_labeled_offers", 0),
                      "notifications": summary.get("notifications", 0),
                      "firstCandidateP95Ms": metrics["firstCandidateLatencyP95Ms"],
                      "inferenceP95Ms": metrics["ocrInferenceP95Ms"]})
    return {"scenarios": len(cases), "passed": sum(c["pass"] for c in cases),
            "cases": cases, "scope": "synthetic offline OCR timing only"}


def main():
    result = run_suite()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["scenarios"] == result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
