#!/usr/bin/env python3
"""Read-only static ordering checks for the MediaProjection entry path.

Matches Vexo's current service methods. No runtime guarantee that Android grants
consent or that all branches execute the expected ordering. Uses only source.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from lifecycle_review import block
from check_contract import _strip_java_comments


def finding(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _calls(body: str | None, function: str) -> list[int]:
    if body is None:
        return []
    return [m.start() for m in re.finditer(
        r"\b" + re.escape(function) + r"\s*\(", body)]


def review_text(service: str) -> list[dict[str, str]]:
    source = _strip_java_comments(service)
    start = block(source, "onStartCommand")
    initiate = block(source, "initiate")
    foreground = _calls(start, "startForeground")
    init_calls = _calls(start, "initiate")
    projection = _calls(initiate, "getMediaProjection")
    callback = _calls(initiate, "registerCallback")
    display = _calls(initiate, "createVirtualDisplay")
    return [
        finding(
            "FOREGROUND_BEFORE_CAPTURE_START",
            bool(foreground and init_calls and max(foreground) < min(init_calls)),
            "Todas as chamadas startForeground devem preceder initiate no fluxo de start"),
        finding(
            "GET_PROJECTION_BEFORE_CALLBACK",
            len(projection) == 1 and len(callback) == 1 and
            projection[0] < callback[0],
            "Obter MediaProjection uma vez e registrar callback depois"),
        finding(
            "CALLBACK_BEFORE_DISPLAY",
            len(callback) == 1 and len(display) == 1 and
            callback[0] < display[0],
            "Registrar MediaProjection.Callback antes do primeiro VirtualDisplay"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-service", action="store_true")
    args = parser.parse_args()
    path = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    if not path.is_file():
        findings = [finding("SERVICE_PRESENT", False, "LiveCaptureService ausente")] if args.require_service else [
            {"code": "SERVICE_PRESENT", "status": "SKIP", "detail": "Sem serviço nesta branch de auditoria"}]
    else:
        findings = review_text(path.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps({"checks": findings}, indent=2, ensure_ascii=False))
    else:
        for x in findings:
            print(x["status"], x["code"], x["detail"])
    return int(any(x["status"] == "FAIL" for x in findings))


if __name__ == "__main__":
    raise SystemExit(main())
