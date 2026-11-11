#!/usr/bin/env python3
"""Conservative source-only review of MediaProjection stop and resize.

Recognises either direct onStop invalidation or delegation to a synchronous
locked helper. Does NOT prove runtime concurrency safety; instrumented tests
with a pending ML Kit Task and forced resize exceptions remain mandatory.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys

from check_contract import _strip_java_comments


def result(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def block(source: str, method_name: str) -> str | None:
    """Best-effort brace-delimited Java method body (not full Java grammar)."""
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


def _immediate_invalidation(body: str | None, *, delegated: bool = False) -> bool:
    """A pre-dispatch generation bump plus active/stopping guards.

    Delegated cleanup must be serialized on sessionLock to protect notification
    delivery in the same lock. This is a source contract, not a control-flow proof.
    """
    if body is None:
        return False
    before_dispatch = body.split("main.post(", 1)[0]
    invalidating = re.search(r"\bepoch\s*\.\s*(?:incrementAndGet|set)\s*\(", before_dispatch)
    inactive = re.search(r"\bactive\s*=\s*false\s*;", before_dispatch)
    stopping = re.search(r"\bstopping\s*=\s*true\s*;", before_dispatch)
    locked = re.search(r"\bsynchronized\s*\(\s*sessionLock\s*\)", before_dispatch)
    return bool(invalidating and inactive and stopping and (locked or not delegated))


def _onstop_invalidation(source: str) -> bool:
    on_stop = block(source, "onStop")
    if on_stop is None:
        return False
    before_dispatch = on_stop.split("main.post(", 1)[0]
    if _immediate_invalidation(before_dispatch):
        return True
    # Recognise an explicit helper called synchronously by onStop BEFORE it
    # posts a cleanup. Inspect the referenced helper; not any helper anywhere.
    for match in re.finditer(r"\b(invalidate[A-Za-z_]*Session)\s*\(", before_dispatch):
        helper = block(source, match.group(1))
        if _immediate_invalidation(helper, delegated=True):
            return True
    return False


def _reader_released_on_resize_error(resize: str | None) -> tuple[str, bool | None]:
    if resize is None:
        return "resize(w,h) ausente", False
    # Two legitimate ownership patterns:
    #   ImageReader replacement = ImageReader.newInstance(...)
    #   ImageReader replacement = null; try { replacement=...; } catch {...close...}
    local = re.search(
        r"\bImageReader\s+([A-Za-z_]\w*)\s*=\s*(?:null|ImageReader\.newInstance\s*\()",
        resize)
    if local is None:
        return "Sem ImageReader provisório local; revisar ownership manualmente", None
    name = local.group(1)
    allocation = re.search(
        r"\b" + re.escape(name) + r"\s*=\s*ImageReader\.newInstance\s*\(",
        resize)
    if allocation is None:
        return "Variável provisória existe, mas allocation não localizada", False

    catch = re.search(r"\bcatch\s*\([^)]*\)\s*\{", resize[allocation.start():])
    if not catch:
        return "Reader provisório sem catch de falha localizado", False
    catch_offset = allocation.start() + catch.end()
    catch_text = resize[catch_offset:]
    release = re.search(r"\b" + re.escape(name) + r"\s*\.\s*close\s*\(", catch_text)
    transfer = re.search(r"\bimageReader\s*=\s*(?:newReader|" +
                         re.escape(name) + r")\s*;", resize[allocation.start():])
    if release and transfer:
        # Close must occur in catch before cleanup invocation, not after it.
        cleanup = re.search(r"\b(?:shutdown|invalidateStoppedSession)\s*\(", catch_text)
        if cleanup and release.start() > cleanup.start():
            return "Fechamento do reader provisório após cleanup", False
        return "Provisório fechado no catch e ownership transferido após setSurface (revisar runtime)", True
    return "Fechamento de reader provisório ausente em falha de resize", False


def review_text(service: str) -> list[dict[str, str]]:
    source = _strip_java_comments(service)
    resize = block(source, "resize")
    reader_detail, reader_ok = _reader_released_on_resize_error(resize)
    checks = [
        result("STOP_INVALIDATES_EPOCH_BEFORE_DISPATCH",
               _onstop_invalidation(source),
               "Invalidar epoch, active e stopping antes de postar cleanup; "
               "se delegado, helper sincronizado em sessionLock"),
        result("RESIZE_REPLACEMENT_RELEASE_ON_EXCEPTION",
               bool(reader_ok),
               reader_detail),
    ]
    if reader_ok is None:
        checks[-1]["status"] = "SKIP"
    if resize is None:
        checks.append(result("RESIZE_HANDLER_PRESENT", False,
                             "resize(w,h) não identificado; verificar rotação"))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--require-service", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    if not path.exists():
        out = [result("SERVICE_PRESENT", False, "LiveCaptureService ausente")] if args.require_service else [{
            "code": "SERVICE_PRESENT", "status": "SKIP",
            "detail": "Sem serviço na branch exclusiva do auditor"}]
    else:
        out = review_text(path.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps({"checks": out}, indent=2, ensure_ascii=False))
    else:
        for item in out:
            print(f"{item['status']:4} {item['code']}: {item['detail']}")
    return int(any(x["status"] == "FAIL" for x in out))


if __name__ == "__main__":
    sys.exit(main())
