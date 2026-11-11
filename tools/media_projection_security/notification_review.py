#!/usr/bin/env python3
"""Read-only lock/epoch review of offer notification and reset paths.

Static lexical checks only: callback concurrency, Android notification delivery,
and MediaProjection permission must be verified with runtime instrumentation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

from check_contract import _strip_java_comments
from lifecycle_review import block


def check(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _ordered(text: str | None, tokens: tuple[str, ...]) -> bool:
    if text is None:
        return False
    pos = -1
    for token in tokens:
        at = text.find(token, pos + 1)
        if at < 0:
            return False
        pos = at
    return True


def review_text(service: str, capture_state: str) -> list[dict[str, str]]:
    s = _strip_java_comments(service)
    st = _strip_java_comments(capture_state)
    clear = block(s, "clearCandidateIfCurrent")
    evaluate = block(s, "evaluate")
    stop = block(s, "invalidateStoppedSession")
    clear_synchronized = block(clear, "synchronized") if clear else None
    offer_synchronized = block(evaluate, "synchronized") if evaluate else None
    stop_synchronized = block(stop, "synchronized") if stop else None
    state_clear = block(st, "clearCandidate")

    return [
        check("CLEAR_NOTIFICATION_LOCKED_WITH_STOP",
              _ordered(clear_synchronized, (
                  "sessionAlive(session)", "episodes.nonOffer()",
                  "LiveCaptureState.clearCandidate()", "nm.notify("
              )) and bool(clear and "synchronized(sessionLock)" in clear),
              "Ao limpar alerta, sessionAlive e episodes.nonOffer precedem state.clear + notify dentro do lock"),
        check("OFFER_NOTIFICATION_LOCKED_WITH_STOP",
              _ordered(offer_synchronized, (
                  "sessionAlive(session)", "episodes.observe(",
                  "LiveCaptureState.candidate(", "nm.notify("
              )) and bool(evaluate and "synchronized(sessionLock)" in evaluate),
              "Ao mostrar alerta, verificar sessão e episódio sob o mesmo lock do STOP"),
        check("STOP_ENDS_STATE_BEFORE_ASYNC_CLEANUP",
              _ordered(stop_synchronized, (
                  "stopping=true", "active=false", "epoch.incrementAndGet()",
                  "LiveCaptureState.end("
              )) and bool(stop and "synchronized(sessionLock)" in stop) and
              stop.find("main.post(") > stop.find("epoch.incrementAndGet()"),
              "No onStop delegado, invalidar epoch e limpar UI sob lock antes de agendar cleanup"),
        check("CANDIDATE_CLEAR_PRESERVES_CAPTURE_SESSION",
              bool(state_clear and "if(!active) return" in state_clear and
                   re.search(r"\blastCandidate\s*=\s*\"\"\s*;", state_clear) and
                   re.search(r"\bstatus\s*=", state_clear) and
                   not re.search(r"\bactive\s*=\s*false\s*;", state_clear)),
              "Um mapa limpa apenas candidato; não encerra a autorização de captura"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-service", action="store_true")
    args = parser.parse_args()
    root = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab"
    service = root / "LiveCaptureService.java"
    state = root / "LiveCaptureState.java"
    if not service.is_file() or not state.is_file():
        checks = [check("OFFER_CAPTURE_SOURCES_PRESENT", False, "Serviço/estado ausente")] if args.require_service else [{
            "code": "OFFER_CAPTURE_SOURCES_PRESENT", "status": "SKIP",
            "detail": "Branch de auditoria independente sem Android."}]
    else:
        checks = review_text(service.read_text(encoding="utf-8"),
                             state.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
    else:
        for finding in checks:
            print(finding["status"], finding["code"], finding["detail"])
    return int(any(item["status"] == "FAIL" for item in checks))


if __name__ == "__main__":
    raise SystemExit(main())
