#!/usr/bin/env python3
"""Conservative source review of voluntary Vexo diagnostic export and OCR latency.

Only syntax-level checks. A PASS does not prove there is no information leak;
runtime clipboard behavior and user consent must be tested on Android.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from check_contract import _strip_java_comments
from lifecycle_review import block

# Reject unfamiliar report fields even when a developer labels them "safe".
SAFE_FIELDS = {
    "schema", "app", "status", "diagnosticStage",
    "diagnosticExplanation", "framesReceived", "ocrAttempts",
    "ocrCompleted", "ocrFailures", "offersAlerted",
    "ocrLatencySamples", "ocrLatencyLastMs", "ocrLatencyMeanMs",
    "ocrLatencyP50Ms", "ocrLatencyP95Ms", "ocrLatencyMaxMs",
    "offerContextCandidates", "screenContextUncertain",
    "screenContextRejected", "financiallyUnconfirmedFrames",
    "awaitingTwoStableReadings", "capturedWindowVisibility",
    "noFieldAccuracyMeasured", "containsScreenshotOrOcrText",
    "privacyNote",
}

# Every value, not just each key, is allowlisted. A future developer must
# update tests and review before exporting another data category.
SAFE_VALUES = {
    "schema": '"vexo-live-capture-diagnostic-v1"',
    "app": '"Vexo Captura 0.4 experimental"',
    "status": 'active?"CAPTURE_ACTIVE":"CAPTURE_STOPPED"',
    "diagnosticStage": "stage",
    "diagnosticExplanation": "CaptureHealthAnalyzer.explanation(stage)",
    "framesReceived": "n[0]",
    "ocrAttempts": "n[3]",
    "ocrCompleted": "n[1]",
    "ocrFailures": "n[4]",
    "offersAlerted": "n[2]",
    "ocrLatencySamples": "timing[0]",
    "ocrLatencyLastMs": "timing[1]",
    "ocrLatencyMeanMs": "timing[2]",
    "ocrLatencyP50Ms": "timing[3]",
    "ocrLatencyP95Ms": "timing[4]",
    "ocrLatencyMaxMs": "timing[5]",
    "offerContextCandidates": "offerCandidates.get()",
    "screenContextUncertain": "contextUncertain.get()",
    "screenContextRejected": "contextRejected.get()",
    "financiallyUnconfirmedFrames": "financeRejected.get()",
    "awaitingTwoStableReadings": "waitingConfirmation.get()",
    "capturedWindowVisibility": "visibility",
    "noFieldAccuracyMeasured": "true",
    "containsScreenshotOrOcrText": "false",
    "privacyNote": '"Contadores da sessao, sem imagens, texto OCR, enderecos ou identificadores."',
}


def result(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _puts(body: str) -> list[tuple[str | None, str]]:
    """Get value expressions from report.put calls without evaluating Java."""
    found = []
    for m in re.finditer(r"\breport\s*\.\s*put\s*\(\s*", body):
        start = m.end()
        key = re.match(r'"([^"]+)"\s*,\s*', body[start:])
        if not key:
            found.append((None, "DYNAMIC_KEY"))
            continue
        keyname = key.group(1)
        i = start + key.end()
        depth = 0
        quote = None
        escaped = False
        begin = i
        while i < len(body):
            ch = body[i]
            if quote:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    quote = None
            elif ch in ("'", '"'):
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                if ch == ")" and depth == 0:
                    break
                depth -= 1
            i += 1
        found.append((keyname, body[begin:i].strip()))
    return found


def review_text(state: str, activity: str, service: str,
                latency: str | None = None) -> list[dict[str, str]]:
    state = _strip_java_comments(state)
    activity = _strip_java_comments(activity)
    service = _strip_java_comments(service)
    report = block(state, "safeDiagnosticReport") or ""
    begin = block(state, "begin") or ""
    export = _puts(report)
    fields = [name for name, _ in export]
    unknown = sorted({str(k) for k in fields if k not in SAFE_FIELDS})
    duplicate = len(fields) != len(set(fields))
    unsafe_value = [
        name for name, val in export
        if name not in SAFE_VALUES or _compact(val) != _compact(SAFE_VALUES[name])
    ]

    # Clipboard must only happen inside the direct click callback of the
    # explicitly labelled copy button, never automatically on refresh/Resume.
    button = "Copiar diagnóstico da captura para análise"
    clicked = activity.find("copyReport.setOnClickListener")
    clip = activity.find("clipboard.setPrimaryClip")
    callback_region = activity[clicked:clip] if clicked >= 0 and clip > clicked else ""
    clipboard_ok = (clicked >= 0 and clip > clicked and button in activity and
                    "LiveCaptureState.safeDiagnosticReport()" in activity[clip:clip + 300] and
                    "getSystemService(Context.CLIPBOARD_SERVICE)" in callback_region and
                    activity.count("setPrimaryClip(") == 1)

    # The report method must not use snapshot/candidate/raw text getters.
    raw = bool(re.search(
        r"\b(?:lastCandidate|lastFingerprint|snapshot\s*\(|getText\s*\(|"
        r"getPrimaryClip\s*\(|ImageReader|Bitmap|MediaProjection)\b", report))

    # OCR timing from async ML Kit callbacks must be tied to the current
    # session/epoch; no delayed callback should pollute a new session.
    call = service.find("LiveCaptureState.ocrLatency(")
    near_call = service[max(0,call - 230):call] if call >= 0 else ""
    protected_latency = (
        call >= 0 and "epoch.get()==session" in near_call
        and "active" in near_call and "!stopping" in near_call
        and "SystemClock.elapsedRealtime()-startedAt" in service[call:call + 200]
        and "latency.reset();" in begin
    )
    bounded_latency = bool(
        latency and "MAX_SAMPLES=128" in re.sub(r"\s+", "", latency) and
        "elapsedMs<0" in re.sub(r"\s+", "", latency) and
        "elapsedMs>600000" in re.sub(r"\s+", "", latency) and
        "Arrays.copyOf(recentMs,count)" in re.sub(r"\s+", "", latency)
    )

    return [
        result("EXPORT_SCHEMA_FIELD_ALLOWLIST",
               bool(fields) and not unknown and not duplicate and
               set(fields) == SAFE_FIELDS,
               "Campos exportados devem ser exatamente os 25 autorizados; extras e chaves dinâmicas falham"),
        result("EXPORT_VALUES_ALLOWLIST",
               bool(fields) and not unsafe_value,
               "Valores de todos os campos devem vir de constantes/contadores/estado seguro, nunca OCR bruto"),
        result("EXPORT_NO_RAW_SCREEN_REFERENCE",
               bool(report) and not raw and "return report.toString(2)" in report,
               "Exportação não pode serializar snapshot, candidato, pixels, texto OCR ou token"),
        result("CLIPBOARD_EXPLICIT_USER_CLICK",
               clipboard_ok,
               "Copiar diagnóstico só após clique específico; clipboard é compartilhado e não deve ser automático"),
        result("OCR_LATENCY_CURRENT_SESSION_GUARD",
               protected_latency,
               "Latência OCR só é registrada sob guarda active/stopping/epoch e reset por sessão"),
        result("OCR_LATENCY_BOUNDED_SAMPLE_WINDOW",
               bounded_latency if latency is not None else False,
               "Guardar no máximo 128 amostras de duração, rejeitar anomalias, sem histórico de corrida"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-export", action="store_true")
    args = parser.parse_args()
    base = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab"
    files = [base / p for p in (
        "LiveCaptureState.java", "LiveCaptureActivity.java",
        "LiveCaptureService.java", "CaptureLatencyStats.java",
    )]
    if not all(p.exists() for p in files[:3]):
        checks = [result("EXPORT_SOURCE_PRESENT", False, "Fontes Android não encontradas")] if args.require_export else [{
            "code": "EXPORT_SOURCE_PRESENT", "status": "SKIP",
            "detail": "Branch exclusiva de auditoria sem fonte do aplicativo"}]
    else:
        checks = review_text(
            *[p.read_text(encoding="utf-8") for p in files[:3]],
            files[3].read_text(encoding="utf-8") if files[3].exists() else None,
        )
    if args.json:
        print(json.dumps({"checks": checks}, indent=2, ensure_ascii=False))
    else:
        for item in checks:
            print(f'{item["status"]} {item["code"]}: {item["detail"]}')
    return int(any(c["status"] == "FAIL" for c in checks))


if __name__ == "__main__":
    raise SystemExit(main())
