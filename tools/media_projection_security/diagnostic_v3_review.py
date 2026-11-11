#!/usr/bin/env python3
"""Fail-closed source allowlist for voluntary Vexo v3 diagnostic export.

Checks schema and VALUES, not only key names. Source check != runtime privacy
guarantee; only aggregate fields may be shared. Never prints user inputs.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from check_contract import _strip_java_comments
from e2e_evidence_review import _method_body
from diagnostic_privacy_review import SAFE_VALUES, _puts as report_puts
from context_evidence_v2_review import EVIDENCE_KEYS, _puts as nested_puts

EXPECTED = {
    **SAFE_VALUES,
    "schema": '"vexo-live-capture-diagnostic-v3"',
    "app": '"Vexo Captura 0.4.2 Janela experimental"',
    "discardedStaleOcrFrames": "staleOcrFrames.get()",
    "offerGateHeldFrames": "offerGateHeld.get()",
    "candidatesWithout99Logo": "offerCandidatesWithoutLogo.get()",
    "contextEvidenceCounts": "evidence",
}
NESTED_VALUES = [(name, f"ev[{i}]") for i,name in enumerate(EVIDENCE_KEYS)]


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def finding(name: str, passed: bool, info: str):
    return {"code": name, "status": "PASS" if passed else "FAIL", "detail": info}


def review_text(state: str, activity: str, service: str) -> list[dict[str,str]]:
    state, activity, service = map(_strip_java_comments,(state,activity,service))
    body = _method_body(state,"safeDiagnosticReport") or ""
    begin = _method_body(state,"begin") or ""
    export = report_puts(body)
    keys = [key for key,_ in export]
    valid_values = (
        len(export)==len(EXPECTED) and
        set(keys)==set(EXPECTED) and
        len(keys)==len(set(keys)) and
        all(key in EXPECTED and _compact(value)==_compact(EXPECTED[key])
            for key,value in export)
    )
    schema_ok=(
        ("schema",'"vexo-live-capture-diagnostic-v3"') in export and
        '"vexo-live-capture-diagnostic-v3"' in body
    )
    nested = nested_puts("evidence",body)
    nested_ok = (
        nested==NESTED_VALUES and
        "JSONObjectevidence=newJSONObject()" in _compact(body) and
        "long[]ev=contextEvidence.snapshot()" in _compact(body)
    )
    counters = (
        "private static final AtomicLong staleOcrFrames" in state and
        "private static final AtomicLong offerGateHeld" in state and
        "private static final AtomicLong offerCandidatesWithoutLogo" in state and
        all((name+".set(0)") in _compact(begin)
            for name in ("staleOcrFrames","offerGateHeld","offerCandidatesWithoutLogo"))
    )
    # Neither payload text nor a JSON string constructed from user OCR should
    # be referenced by the method; checking expressions above is stronger.
    raw = re.search(
        r"\b(?:lastCandidate|rawText|ocrText|Bitmap|ImageReader|"
        r"passenger|address|latitude|longitude|sessionToken)\b",body,re.I)
    click = activity.find("copyReport.setOnClickListener")
    clip = activity.find("clipboard.setPrimaryClip")
    copy_ok = (
        0 <= click < clip and
        activity.count("setPrimaryClip(")==1 and
        "LiveCaptureState.safeDiagnosticReport()" in activity[click:clip+250]
    )
    optin = (
        "if(!sessionAlive(session))return" in _compact(service) and
        "LiveCaptureState.recordContextEvidence(" in service
    )

    return [
        finding("V3_SCHEMA_EXACT",schema_ok,"Versão explícita v3"),
        finding("V3_TOP_KEYS_AND_VALUES_EXACT",valid_values,
                "Apenas campos técnicos permitidos, com valores derivados de contadores"),
        finding("V3_NESTED_EVIDENCE_EXACT",nested_ok,
                "8 contadores aninhados, nenhuma string/OCR bruto"),
        finding("V3_RESET_EXTRA_COUNTERS",counters,
                "3 contadores novos AtomicLong em RAM, zerados a cada sessão"),
        finding("V3_NO_PRIVATE_REPORT_REFERENCES",bool(body) and not raw,
                "Não serializar conteúdo de tela, endereço ou token"),
        finding("V3_CLIPBOARD_USER_INITIATED",copy_ok,
                "Cópia somente após gesto explícito"),
        finding("V3_SERVICE_HAS_SESSION_CHECK",optin,
                "Serviço usa verificação de sessão antes de publicar; testar corrida STOP em Android"),
    ]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=".")
    ap.add_argument("--json",action="store_true")
    args=ap.parse_args()
    base=Path(args.root)/"app/src/main/java/com/vexo/mlkitlab"
    paths=[base/x for x in ("LiveCaptureState.java","LiveCaptureActivity.java","LiveCaptureService.java")]
    if not all(x.is_file() for x in paths):
        checks=[finding("SOURCES",False,"Fontes do Android ausentes")]
    else:
        checks=review_text(*(x.read_text(encoding="utf-8") for x in paths))
    if args.json:
        print(json.dumps({"checks":checks},ensure_ascii=False,indent=2))
    else:
        for c in checks:print(c["status"],c["code"],c["detail"])
    return int(any(c["status"]=="FAIL" for c in checks))


if __name__=="__main__":
    raise SystemExit(main())
