#!/usr/bin/env python3
"""Read-only audit: MediaProjection visibility callbacks versus STOP/restart.

Source-only, conservative. No images, tokens, OCR text or user media.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from check_contract import _strip_java_comments
from e2e_evidence_review import _method_body


def audit_text(source: str) -> list[dict[str, str]]:
    s = _strip_java_comments(source)
    callback = _method_body(s, "onCapturedContentVisibilityChanged") or ""
    stop = _method_body(s, "invalidateStoppedSession") or ""
    def finding(code: str, passed: bool, detail: str):
        return {"code": code, "status": "PASS" if passed else "FAIL", "detail": detail}

    lock = callback.find("synchronized(sessionLock)")
    write = callback.find("capturedVisible=visible")
    ui = callback.find("LiveCaptureState.capturedContentVisibility(visible)")
    epoch = callback.find("epoch.get()")
    active = callback.find("active")
    stopping = callback.find("stopping")
    # Lock must enclose the check and both writes; lexical approximation only.
    locked = lock >= 0 and min(write,ui,epoch,active,stopping) > lock
    nested = callback[lock:ui] if locked else ""
    braces = nested.count("{") > nested.count("}")
    guard = (locked and braces and
             ("epoch.get()!=session" in callback or "epoch.get()==session" in callback) and
             "!active" in callback and "stopping" in callback and
             max(epoch, active, stopping) < write < ui)
    goodstop = (
        "synchronized(sessionLock)" in stop and
        "epoch.incrementAndGet()" in stop and "active=false" in stop
        and "stopping=true" in stop
    )
    return [
        finding("VISIBILITY_CALLBACK_EPOCH_STOP_LOCK",
                guard, "visibilidade deve validar epoch + active + stopping sob o mesmo lock do STOP"),
        finding("VISIBILITY_STATE_WRITES_IN_GUARDED_SECTION",
                guard and write > lock and ui > write,
                "capturedVisible e UI precisam ser alterados sob guarda da sessão"),
        finding("STOP_INVALIDATES_SAME_LOCK",
                goodstop, "onStop deve invalidar a sessão no mesmo sessionLock"),
    ]


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args=parser.parse_args()
    path=Path(args.root)/"app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    results=audit_text(path.read_text(encoding="utf-8")) if path.is_file() else [
        {"code":"SERVICE_PRESENT","status":"SKIP","detail":"Android ausente na branch do auditor"}]
    if args.json:
        print(json.dumps({"checks":results},ensure_ascii=False,indent=2))
    else:
        for r in results: print(r["status"],r["code"],r["detail"])
    return int(any(r["status"]=="FAIL" for r in results))


if __name__=="__main__":
    raise SystemExit(main())
