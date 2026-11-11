#!/usr/bin/env python3
"""Conservative, source-only review of stop/resize resource safety.

Checks known failure patterns in the current Android service.
Does NOT prove thread safety or replace Android instrumentation tests.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys


def result(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def block(source: str, method_name: str) -> str | None:
    """Extract a brace-delimited Java method body using a best-effort lexical scan.

    The service uses brace-delimited method bodies without embedded raw-text blocks.
    This deliberately does not claim to be a complete Java grammar parser.
    """
    match = re.search(r"\b" + re.escape(method_name) + r"\s*\([^)]*\)\s*\{", source)
    if not match:
        return None
    start = match.end()
    depth = 1
    quote = None
    escaping = False
    for i in range(start, len(source)):
        c = source[i]
        if quote:
            if escaping:
                escaping = False
            elif c == "\\":
                escaping = True
            elif c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return source[start:i]
    return None


def review_text(service: str) -> list[dict[str, str]]:
    """Return explicit checks that can be meaningfully inspected from text."""
    on_stop = block(service, "onStop")
    resize = block(service, "resize")
    stop_prepost = on_stop.split(".post(", 1)[0] if on_stop is not None else ""
    # Postponing shutdown to main while active/epoch remain valid leaves a
    # window in which another callback may apply a stale OCR result.
    synchronous_invalidate = bool(re.search(
        r"\bepoch\s*\.\s*(?:incrementAndGet|set)\s*\(|"
        r"\b(?:invalidateSession|invalidateEpoch)\s*\(",
        stop_prepost))
    checks = [result("STOP_INVALIDATES_EPOCH_BEFORE_DISPATCH",
                     synchronous_invalidate,
                     "onStop deve invalidar epoch imediatamente, antes de postar cleanup em outra thread")]
    if resize is None:
        checks.append(result("RESIZE_HANDLER_PRESENT", False,
                             "resize(w,h) não identificado; teste de rotação necessário"))
        return checks

    # A locally allocated replacement may be leaked if VirtualDisplay.resize
    # or setSurface throws before imageReader is reassigned.
    replacement = re.search(r"\bImageReader\s+([A-Za-z_]\w*)\s*=\s*ImageReader\.newInstance\s*\(", resize)
    if replacement:
        local = replacement.group(1)
        cleanup = bool(re.search(
            r"\b(?:catch|finally)\s*(?:\([^)]*\))?\s*\{[\s\S]*?"
            r"(?:\b" + re.escape(local) + r"\s*\.\s*close\s*\(|"
            r"\b(?:close|dispose|release)Reader\s*\(\s*" + re.escape(local) + r"\s*\))",
            resize))
        checks.append(result("RESIZE_REPLACEMENT_RELEASE_ON_EXCEPTION",
                             cleanup,
                             "ImageReader provisório deve ser fechado se resize/setSurface falhar antes de assumir ownership"))
    else:
        checks.append({"code": "RESIZE_REPLACEMENT_RELEASE_ON_EXCEPTION",
                       "status": "SKIP",
                       "detail": "Não há ImageReader local replacement; avaliar ownership do Surface manualmente"})
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--require-service", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    service = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    if not service.exists():
        out = [result("SERVICE_PRESENT", False, "LiveCaptureService ausente")] if args.require_service else [{
            "code": "SERVICE_PRESENT", "status": "SKIP",
            "detail": "Branch de auditoria não contém o serviço Android; avaliar branch de integração"}]
    else:
        out = review_text(service.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps({"checks": out}, indent=2, ensure_ascii=False))
    else:
        for item in out:
            print(f"{item['status']:4} {item['code']}: {item['detail']}")
    return int(any(x["status"] == "FAIL" for x in out))


if __name__ == "__main__":
    sys.exit(main())
