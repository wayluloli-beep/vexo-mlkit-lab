#!/usr/bin/env python3
"""Read-only security/consent review of optional Android overlay PR35-37.

Static checks only: Android 12+ touch passthrough, frame obscuration and overlay
lifecycle NEED instrumented tests on actual device. Avoids private images/OCR.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

from check_contract import _strip_java_comments
from e2e_evidence_review import _method_body


def finding(code: str, ok: bool, desc: str):
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": desc}


def review_text(overlay: str, activity: str, service: str) -> list[dict]:
    o, a, s = map(_strip_java_comments, (overlay, activity, service))
    allowed = _method_body(o, "allowed") or ""
    hide = _method_body(s, "scheduleOverlayHide") or ""
    start = _method_body(s, "onStartCommand") or ""
    stop = _method_body(s, "shutdown") or ""
    optout = _method_body(a, "toggleOverlay") or ""
    show = _method_body(o, "ensureWindow") or ""

    m = re.search(r"\bparams\.alpha\s*=\s*(\d+(?:\.\d+)?)f?\s*;", show)
    alpha = float(m.group(1)) if m else None
    flags = all(x in show for x in (
        "TYPE_APPLICATION_OVERLAY", "FLAG_NOT_TOUCHABLE",
        "FLAG_NOT_FOCUSABLE", "FLAG_SECURE"))
    alpha_ok = alpha is not None and 0 < alpha <= 0.8
    optin_ok = (
        'getBoolean(OPT_IN,false)' in re.sub(r"\s+", "", o) and
        "optedIn(context)" in allowed and
        "Settings.canDrawOverlays(context)" in allowed and
        "Build.VERSION.SDK_INT>=26" in allowed)
    hide_guard = all(x in hide for x in (
        "overlayGeneration.incrementAndGet()",
        "final long version",
        "version!=overlayGeneration.get()",
        "synchronized(sessionLock)",
        "offerOverlay.hide()"))
    stop_hide = ("scheduleOverlayHide()" in stop and
                 "active=false" in stop and "epoch.incrementAndGet()" in stop)
    hide_action = (
        "ACTION_HIDE_OVERLAY.equals(action)" in start and
        "scheduleOverlayHide()" in start and
        "VexoOfferOverlay.setOptIn(this,false)" in optout and
        "LiveCaptureService.ACTION_HIDE_OVERLAY" in optout and
        "startService(off)" in optout)
    # Informational only; static code cannot prove that 99 accept/reject buttons
    # are left unobscured, or that FLAG_SECURE does not mask nearby OCR pixels.
    no_clicks = not re.search(
        r"\b(?:performClick|dispatchTouchEvent|AccessibilityService|"
        r"performGlobalAction|Instrumentation|input\s+tap)\b",o)
    one_window = "if(window!=null) return true" in show and "wm.addView(root,params)" in show

    return [
        finding("OVERLAY_OPTIN_AND_SYSTEM_PERMISSION", optin_ok,
                "Por padrão OFF; requer adesão separada e Settings.canDrawOverlays"),
        finding("OVERLAY_DISPLAY_FLAGS", flags,
                "TYPE_APPLICATION_OVERLAY com NOT_TOUCHABLE, NOT_FOCUSABLE, SECURE"),
        finding("OVERLAY_ANDROID12_ALPHA_LIMIT", alpha_ok,
                f"alpha={alpha}; Android S permite toque sob uma SAW com opacidade combinada <=0.8 por padrão"),
        finding("OVERLAY_ONE_WINDOW_INSTANCE", one_window,
                "Criar no máximo uma janela própria por instância de overlay"),
        finding("OVERLAY_NO_AUTOMATIC_CLICKS", no_clicks,
                "Overlay não invoca cliques nem serviços de acessibilidade"),
        finding("OVERLAY_HIDE_GENERATION_GUARD", hide_guard,
                "hide antigo não pode remover janela de sessão nova"),
        finding("OVERLAY_STOP_INVALIDATES_AND_HIDES", stop_hide,
                "STOP encerra epoch e agenda remoção do overlay"),
        finding("OVERLAY_OPTOUT_REMOVES_NOW", hide_action,
                "Opt-out envia comando de remoção, sem esperar próximo STOP"),
    ]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=".")
    ap.add_argument("--json",action="store_true")
    args=ap.parse_args()
    base=Path(args.root)/"app/src/main/java/com/vexo/mlkitlab"
    files=[base/x for x in ("VexoOfferOverlay.java","LiveCaptureActivity.java","LiveCaptureService.java")]
    if not all(f.is_file() for f in files):
        result=[finding("OVERLAY_SOURCES_PRESENT",False,"Fontes ausentes")]
    else:
        result=review_text(*(f.read_text(encoding="utf-8") for f in files))
    if args.json:
        print(json.dumps({"checks":result},ensure_ascii=False,indent=2))
    else:
        for x in result: print(x["status"],x["code"],x["detail"])
    return int(any(x["status"]=="FAIL" for x in result))


if __name__=="__main__":
    raise SystemExit(main())
