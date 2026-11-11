#!/usr/bin/env python3
"""Read-only evaluation of MediaProjection *test evidence*, not app safety.

Rejects test designs that hide aggregate counters, leave screen-share scope
ambiguous, or skip STOP assertions after a failure in the OCR alert stage.
Java source matching is deliberately conservative/heuristic.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

from check_contract import _strip_java_comments


def finding(code: str, passed: bool, detail: str) -> dict[str, str]:
    return {"code": code, "status": "PASS" if passed else "FAIL", "detail": detail}


def _method_body(source: str, name: str) -> str | None:
    """Locate a Java method body, including declarations with throws."""
    match = re.search(
        r"\b" + re.escape(name) +
        r"\s*\([^)]*\)\s*(?:throws\s+[\w.,\s]+)?\{",
        source,
    )
    if not match:
        return None
    begin = match.end()
    depth = 1
    quote = None
    escaping = False
    for at in range(begin, len(source)):
        ch = source[at]
        if quote:
            if escaping:
                escaping = False
            elif ch == "\\":
                escaping = True
            elif ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[begin:at]
    return None


def review_text(source: str) -> list[dict[str, str]]:
    code = _strip_java_comments(source)
    dialog = _method_body(code, "approveThroughSystemDialog") or ""
    test = _method_body(code, "nativeConsentThenFakeOfferProducesRealFramesAndStops") or ""
    # No exact UI label is treated as proof of actual scope: the test must
    # REQUIRE the chosen scope, instead of silently proceeding if absent.
    optional_scope = bool(re.search(
        r"\bif\s*\(\s*dropdown\s*!=\s*null\s*\)", dialog))
    affirmative_entire = bool(re.search(r"\b(?:entire|wholeScreen)\s*\.\s*click\s*\(", dialog))
    selection_required = affirmative_entire and not optional_scope
    # An alternative can intentionally share *the demo app*; then it must
    # launch the demo before asking for consent, under a real system prompt.
    app_before_consent = (
        "DemoOfferActivity.class" in test and
        "approveThroughSystemDialog" in test and
        test.index("DemoOfferActivity.class") < test.index("approveThroughSystemDialog"))
    selection_required = selection_required or app_before_consent

    # For E2E failures, make the three separate counts observable without
    # logging any image, OCR text, route, token, or passenger information.
    helper_counts = _method_body(code, "awaitCounts") or ""
    counter_lines = bool(re.search(r"\bLiveCaptureState\s*\.\s*counts\s*\(",
                                   test + "\n" + (helper_counts if "awaitCounts(" in test else "")))
    named_metrics = all(re.search(r"\b" + key + r"\b", test, re.I)
                        for key in ("frames", "ocr", "avisos"))
    # Multiple distinct assert stages or independent wait attempts. A single
    # awaitCounts(frames,ocr,alerts) does not identify the failed stage.
    staged_asserts = (
        len(re.findall(r"\bawaitCounts\s*\(", test)) >= 3 or
        all(re.search(r"\bassert(?:True|Equals)\s*\([^;]*\[\s*" + idx + r"\s*\]",
                      test, flags=re.DOTALL)
            for idx in ("0", "1", "2"))
    )
    # A STOP test is independent if it precedes any hard OCR assertion, or
    # if a second dedicated @Test handles STOP with a real state assertion.
    stop_at = test.find("LiveCaptureService.ACTION_STOP")
    ocr_assert = re.search(r"\bassertTrue\s*\([^;]*\bawaitCounts\s*\(", test, flags=re.DOTALL)
    # A dedicated STOP @Test is valid even when the main E2E test does not
    # contain an ACTION_STOP itself.
    other_tests = code[code.find("nativeConsentThenFakeOfferProducesRealFramesAndStops") + 30:]
    dedicated_stop = bool(re.search(
        r"@Test[\s\S]{0,230}\bvoid\s+\w*(?:stop|Stop)\w*\s*\(",
        other_tests))
    stop_independent = dedicated_stop or (
        stop_at >= 0 and (ocr_assert is None or stop_at < ocr_assert.start()))
    # No bypass, screenshots saved on CI, or OCR text logged.
    suspicious = re.search(
        r"\b(?:takeScreenshot|FileOutputStream|openFileOutput|MediaStore|"
        r"AppOpsManager|grantRuntimePermission|Log\.(?:v|d|i|w|e))\s*(?:\.|\()",
        code)

    return [
        finding("E2E_USES_NATIVE_UI_CONSENT",
                all(x in code for x in ("UiDevice.getInstance",
                                        "approveThroughSystemDialog",
                                        "LiveCaptureActivity.class")) and
                "start.click()" in dialog,
                "Teste deve navegar diálogo real de autorização com UiAutomator"),
        finding("E2E_SCOPE_EXPLICIT",
                selection_required,
                "Exigir tela inteira explicitamente no teste ou selecionar app fictício ANTES do consentimento"),
        finding("E2E_EXERCISES_SYNTHETIC_DEMO",
                "DemoOfferActivity.class" in test and counter_lines,
                "Capturar atividade fictícia e consultar contadores reais de sessão"),
        finding("E2E_COUNTERS_VISIBLE_ON_FAILURE",
                counter_lines and named_metrics,
                "Exibir somente frames/OCR/avisos no erro sem revelar pixels ou texto OCR"),
        finding("E2E_STAGEWISE_ASSERTIONS",
                staged_asserts,
                "Separar diagnóstico de frames, OCR e alerta em etapas observáveis"),
        finding("E2E_STOP_NOT_SKIPPED_BY_OCR_FAILURE",
                stop_independent,
                "Verificar STOP mesmo quando a identificação da oferta falha"),
        finding("E2E_NO_PRIVATE_SCREEN_DUMPS",
                not suspicious,
                "Não salvar screenshot, OCR bruto ou dados privados em logs/artifacts"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-test", action="store_true")
    args = parser.parse_args()
    path = Path(args.root) / (
        "app/src/androidTest/java/com/vexo/mlkitlab/LiveProjectionConsentE2eTest.java")
    if not path.exists():
        findings = [finding("E2E_TEST_PRESENT", False, "Teste E2E ausente")] if args.require_test else [{
            "code": "E2E_TEST_PRESENT", "status": "SKIP", "detail": "Branch de auditoria sem APK"}]
    else:
        findings = review_text(path.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps({"checks": findings}, indent=2, ensure_ascii=False))
    else:
        for item in findings:
            print(item["status"], item["code"], item["detail"])
    return int(any(f["status"] == "FAIL" for f in findings))


if __name__ == "__main__":
    raise SystemExit(main())
