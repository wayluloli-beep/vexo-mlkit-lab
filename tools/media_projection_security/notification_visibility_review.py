#!/usr/bin/env python3
"""Review stale Android foreground offer notification after screen-share visibility loss.

Static source check only; on-device notification tests remain required.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from check_contract import _strip_java_comments
from e2e_evidence_review import _method_body

def _if_body(text: str, predicate: str) -> str | None:
    m=re.search(r"if\s*\(\s*"+predicate+r"\s*\)\s*\{",text)
    if m is None: return None
    start=m.end()
    depth=1
    for i in range(start,len(text)):
        if text[i]=="{": depth+=1
        elif text[i]=="}":
            depth-=1
            if depth==0:return text[start:i]
    return None

def finding(name: str, passed: bool, info: str):
    return {"code":name,"status":"PASS" if passed else "FAIL","detail":info}

def review_text(service: str) -> list[dict[str,str]]:
    code=_strip_java_comments(service)
    callback=_method_body(code,"onCapturedContentVisibilityChanged") or ""
    notification=_method_body(code,"notification") or ""
    hidden=_if_body(callback,r"!\s*visible") or ""
    active_guard=(
        "synchronized(sessionLock)" in callback and
        "epoch.get()!=session" in callback and
        "!active" in callback and
        "stopping" in callback
    )
    clear="LiveCaptureState.clearCandidate()" in hidden
    update=bool(re.search(
        r"\b(?:nm|notificationManager|manager)\s*\.\s*notify\s*\("
        r"\s*NOTIFICATION_ID\s*,\s*notification\s*\(\s*false\s*\)\s*\)",
        hidden
    ))
    positive = (
        "offerDetected?" in notification and
        "Vexo: confira uma possível oferta" in notification
    )
    return [
        finding("VISIBILITY_LOSS_SESSION_EPOCH_GUARDED",active_guard,
                "Callback de visibilidade deve validar sessão atual sob lock"),
        finding("VISIBILITY_LOSS_CLEARS_CANDIDATE",clear,
                "Ao ocultar a janela capturada, descartar resumo antigo"),
        finding("VISIBILITY_LOSS_RESETS_ONGOING_OFFER_NOTIFICATION",
                bool(hidden) and update and positive,
                "P1: notificação 'possível oferta' precisa voltar para status neutro; "
                "não deixar título antigo após perder visibilidade"),
    ]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=".")
    ap.add_argument("--json",action="store_true")
    args=ap.parse_args()
    path=Path(args.root)/"app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    checks=review_text(path.read_text(encoding="utf-8")) if path.is_file() else [
        finding("SERVICE_SOURCE",False,"Fonte do Android ausente")]
    if args.json:print(json.dumps({"checks":checks},ensure_ascii=False,indent=2))
    else:
        for item in checks:print(item["status"],item["code"],item["detail"])
    return int(any(c["status"]=="FAIL" for c in checks))

if __name__=="__main__":
    raise SystemExit(main())
