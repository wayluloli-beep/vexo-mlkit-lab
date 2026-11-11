#!/usr/bin/env python3
"""Read-only v2 evidence JSON privacy + stale-session audit.

Static/lexical contracts only: no APK runtime proof, no raw OCR, no user videos.
This checker deliberately FAILS closed when the nested schema changes.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from check_contract import _strip_java_comments
from e2e_evidence_review import _method_body

EVIDENCE_KEYS = (
    "ocrReadsExamined",
    "readsWithPriceMarker",
    "readsWithActionButton",
    "readsWithOfferModality",
    "readsWithTwoDistances",
    "readsWithTwoTimes",
    "readsWith99Marker",
    "readsWithPartialOfferEvidence",
)

def check(code: str, ok: bool, detail: str) -> dict[str,str]:
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _puts(var: str, source: str) -> list[tuple[str, str]]:
    # The allowed expressions here are simple and contain no parentheses.
    return [(key, re.sub(r"\s+", "", val))
            for key, val in re.findall(
                r"\b" + re.escape(var) + r"\s*\.\s*put\s*\(\s*"
                r'"([^"]+)"\s*,\s*([^;]+?)\s*\)\s*;',
                source)]


def review_text(state: str, service: str, counter: str,
                classifier: str) -> list[dict[str,str]]:
    s = _strip_java_comments(state)
    a = _strip_java_comments(service)
    c = _strip_java_comments(counter)
    k = _strip_java_comments(classifier)
    report = _method_body(s, "safeDiagnosticReport") or ""
    record_call = _method_body(a, "evaluate") or ""
    state_record = _method_body(s, "recordContextEvidence") or ""
    counter_record = _method_body(c, "record") or ""
    counter_reset = _method_body(c, "reset") or ""
    state_begin = _method_body(s, "begin") or ""
    mask = _method_body(k, "diagnosticEvidenceMask") or ""

    expected = [(name, f"ev[{i}]") for i, name in enumerate(EVIDENCE_KEYS)]
    actual = _puts("evidence", report)
    nested = _puts("report", report)
    nested_keys = [n for n,_ in nested if n == "contextEvidenceCounts"]
    nested_type = (
        "JSONObject evidence=new JSONObject()" in re.sub(r"\s+", " ", report)
        and "long[]ev=contextEvidence.snapshot()" in re.sub(r"\s+", "", report)
        and nested_keys == ["contextEvidenceCounts"]
        and ("contextEvidenceCounts", "evidence") in nested
    )
    full_values = actual == expected
    v2_schema = ('report.put("schema","vexo-live-capture-diagnostic-v2")'
                 in re.sub(r"\s+", "", report))
    no_raw = not re.search(
        r"\b(?:lastCandidate|(?<!\.)snapshot\s*\(|getText\s*\(|Bitmap|"
        r"ImageReader|MediaProjection|Uri|Route|Address|rawText|ocrText)\b",
        report)
    only_counters = (
        "AtomicLong" in c
        and not re.search(r"\b(?:String|Bitmap|File|JSONObject|Map\s*<|List\s*<)\s+\w+\s*[;=]", c)
        and bool(re.search(r"\breads\s*\.\s*incrementAndGet\s*\(", counter_record))
        and "contextEvidence.reset()" in state_begin
        and all(f"{name}.set(0)" in re.sub(r"\s+", "", counter_reset)
                for name in ("reads", "price", "action", "modality",
                             "twoDistances", "twoMinutes", "literal99", "partialOffer"))
    )
    # Regression contract: telemetry must not promote UNCERTAIN to OFFER.
    no_changed_offer_rules = (
        "diagnosticEvidenceMask(" in k
        and "classify(" in k
        and "return Kind.OFFER_CANDIDATE" in k
        and "return Kind.UNCERTAIN" in k
        and "EVIDENCE_PRICE" in mask
    )
    # The Android live service has a sessionLock and epoch. It is NOT enough
    # for the asynchronous ML Kit caller to check epoch before evaluate();
    # onStop and restart may happen between that check and telemetry update.
    # Correct contract: check sessionAlive and record inside SAME lock.
    call_at = record_call.find("LiveCaptureState.recordContextEvidence")
    guarded = False
    if call_at >= 0:
        before = record_call[:call_at]
        # A synchronized block must contain the call; require a lexical
        # match without a closing brace between its session check and call.
        lock = before.rfind("synchronized(sessionLock)")
        if lock >= 0:
            after = before[lock:]
            guarded = "sessionAlive(session)" in after and \
                after.count("{") > after.count("}")
    # State.active alone is insufficient to prove epoch ownership.
    state_guard = ("if(active)" in re.sub(r"\s+", "", state_record))
    return [
        check("V2_SCHEMA_EXACT", v2_schema,
              "schema literal v2 exigido; não aceitar v1 com campos extras"),
        check("V2_NESTED_KEYS_VALUES_ALLOWLIST",
              nested_type and full_values and len(actual) == 8,
              "contextEvidenceCounts deve conter exatamente 8 chaves e valores ev[0..7]"),
        check("V2_NO_PRIVATE_TEXT_OR_PIXEL_REFERENCES",
              bool(report) and no_raw,
              "sem candidato, endereço, OCR bruto, pixels ou token na exportação"),
        check("V2_COUNTERS_ONLY_RAM_AND_RESET",
              only_counters,
              "apenas AtomicLong sem textos; reset por sessão de todos 8 contadores"),
        check("V2_DIAGNOSTIC_NOT_OFFER_DECISION",
              no_changed_offer_rules,
              "sinais diagnósticos separados de decisão OCR/FinancialGuard"),
        check("V2_SESSION_GUARD_BEFORE_COUNT",
              guarded and state_guard,
              "P1: telemetria sob sessionLock + sessionAlive(epoch), não só active"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    base = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab"
    names = ("LiveCaptureState.java", "LiveCaptureService.java",
             "CaptureContextEvidence.java", "ScreenContextClassifier.java")
    files = [base / n for n in names]
    if not all(p.is_file() for p in files):
        findings = [check("V2_SOURCES_PRESENT", False,
                          "Fontes v2 ausentes do checkout; auditoria não executada")]
    else:
        findings = review_text(*(p.read_text(encoding="utf-8") for p in files))
    if args.json:
        print(json.dumps({"checks": findings}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f["status"], f["code"], f["detail"])
    return int(any(f["status"] == "FAIL" for f in findings))


if __name__ == "__main__":
    raise SystemExit(main())
