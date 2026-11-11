#!/usr/bin/env python3
"""Fail-closed, read-only MediaProjection contract audit (stdlib only).

This is a static safety gate, not proof of runtime permission flow or memory safety.
It never opens images, reads actual OCR, uploads files, or logs screen content.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"
PRIVACY_HAZARDS = {
    "MediaStore": r"\bMediaStore\b",
    "FileOutputStream": r"\bFileOutputStream\b",
    "openFileOutput": r"\bopenFileOutput\s*\(",
    "HttpURLConnection": r"\bHttpURLConnection\b",
    "OkHttp": r"\bOkHttpClient\b",
    "Retrofit": r"\bRetrofit\b",
    "accessibility": r"\bAccessibilityService\b",
    "screen-protection-bypass": r"\bFLAG_SECURE\s*[&|^=]",
}


def finding(code: str, ok: bool, explanation: str) -> dict:
    return {"code": code, "status": "PASS" if ok else "FAIL", "detail": explanation}


def _strip_java_comments(source: str) -> str:
    # This intentionally is only a heuristic; not a Java parser.
    return re.sub(r"(?s)/\*.*?\*/|(?m)//[^\n]*", "", source)


def _manifest_name(value: str) -> str:
    return value.rsplit(".", 1)[-1]


def audit(root: Path, require_capture: bool = False) -> list[dict]:
    root = Path(root)
    java_root = root / "app/src/main/java"
    manifest_path = root / "app/src/main/AndroidManifest.xml"
    sources = {p.stem: _strip_java_comments(p.read_text(encoding="utf-8"))
               for p in java_root.rglob("*.java")} if java_root.exists() else {}
    projection_sources = {name: source for name, source in sources.items()
                          if ("MediaProjection" in source or "createVirtualDisplay" in source
                              or name.startswith("LiveCapture"))}
    if not projection_sources:
        return [finding("CAPTURE_IMPLEMENTATION_PRESENT", False, "Nenhuma implementação MediaProjection encontrada")] if require_capture else [
            {"code": "CAPTURE_IMPLEMENTATION_PRESENT", "status": "SKIP",
             "detail": "Branch sem captura: fixtures sintéticas exercitam os contratos."}
        ]

    findings = []
    if not manifest_path.is_file():
        return [finding("MANIFEST_PRESENT", False, "AndroidManifest.xml ausente")]
    try:
        manifest = ET.parse(manifest_path).getroot()
    except ET.ParseError:
        return [finding("MANIFEST_VALID", False, "AndroidManifest.xml inválido")]

    permissions = {entry.get(ANDROID + "name") for entry in manifest.findall("uses-permission")}
    application = manifest.find("application")
    if application is None:
        return [finding("APPLICATION_PRESENT", False, "<application> ausente")]
    activities = {_manifest_name(x.get(ANDROID + "name", "")) for x in application.findall("activity")}
    services = {_manifest_name(x.get(ANDROID + "name", "")): x for x in application.findall("service")}
    receivers = application.findall("receiver")
    capture_activities = [name for name, source in projection_sources.items()
                          if "MediaProjectionManager" in source and
                          re.search(r"\bextends\s+Activity\b", source)]
    service_refs = set()
    for source in projection_sources.values():
        service_refs.update(re.findall(r"\b([A-Za-z]\w*Service)\s*\.class\b", source))
    capture_services = {name: el for name, el in services.items()
                        if "mediaProjection" in el.get(ANDROID + "foregroundServiceType", "")}
    requested_services = service_refs | set(capture_services)

    findings.append(finding(
        "CAPTURE_ACTIVITY_MANIFEST",
        bool(capture_activities) and all(name in activities for name in capture_activities),
        "Activity de consentimento precisa estar registrada no Manifest"))
    findings.append(finding(
        "FGS_REQUIRED_PERMISSIONS",
        {"android.permission.FOREGROUND_SERVICE",
         "android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION"}.issubset(permissions),
        "Declarar FOREGROUND_SERVICE e FOREGROUND_SERVICE_MEDIA_PROJECTION"))
    findings.append(finding(
        "CAPTURE_SERVICE_SOURCE",
        bool(requested_services) and all(name in sources for name in requested_services),
        "Cada serviço referenciado precisa existir como classe Java"))
    findings.append(finding(
        "CAPTURE_SERVICE_MANIFEST",
        bool(requested_services) and all(
            name in services and
            "mediaProjection" in services[name].get(ANDROID + "foregroundServiceType", "").split("|") and
            services[name].get(ANDROID + "exported") == "false"
            for name in requested_services),
        "Service precisa ser não exportado e foregroundServiceType=mediaProjection"))
    service_code = "\n".join(sources.get(name, "") for name in requested_services)
    findings.append(finding(
        "FOREGROUND_BEFORE_CAPTURE_CONTRACT",
        bool(re.search(r"\bstartForeground\s*\(", service_code)) and
        bool(re.search(r"\bgetMediaProjection\s*\(", service_code)),
        "Service deve promover a foreground antes de obter MediaProjection; ordem exige teste runtime"))
    findings.append(finding(
        "STOP_CALLBACK_REGISTERED",
        "registerCallback(" in service_code and
        bool(re.search(r"\bonStop\s*\(", service_code)),
        "Registrar callback com onStop antes de criar display"))
    display_calls = len(re.findall(r"\bcreateVirtualDisplay\s*\(", service_code))
    projection_calls = len(re.findall(r"\bgetMediaProjection\s*\(", service_code))
    findings.append(finding(
        "SINGLE_PROJECTION_AND_DISPLAY_CALLSITE",
        projection_calls == 1 and display_calls == 1,
        "Esperado um callsite de getMediaProjection e de createVirtualDisplay; não prova token único em runtime"))
    findings.append(finding(
        "IMAGE_READER_BACKPRESSURE",
        "ImageReader" in service_code and "acquireLatestImage(" in service_code,
        "Usar ImageReader com frame recente, limite de fila e descarte de antigos"))
    findings.append(finding(
        "IMAGE_CLOSE_FINALLY",
        bool(re.search(r"\bfinally\s*\{", service_code)) and
        bool(re.search(r"\b[A-Za-z_]\w*\.close\s*\(", service_code)),
        "Fechar Image adquirido em finally; revisar fluxo de exceções manualmente"))
    findings.append(finding(
        "RESOURCE_RELEASE",
        bool(re.search(r"\b[A-Za-z_]\w*\.release\s*\(", service_code)) and
        bool(re.search(r"\b[A-Za-z_]\w*\.close\s*\(", service_code)),
        "Release de VirtualDisplay/Surface e close do reader no STOP, idempotente"))
    findings.append(finding(
        "NO_ACCESSIBILITY_PERMISSION",
        "android.permission.BIND_ACCESSIBILITY_SERVICE" not in permissions and
        not any("android.accessibilityservice.AccessibilityService" in s
                for s in projection_sources.values()),
        "Não usar serviços de acessibilidade como alternativa à captura"))
    boot_receivers = [x for x in receivers if any(
        intent.get(ANDROID + "name") == "android.intent.action.BOOT_COMPLETED"
        for f in x.findall("intent-filter")
        for intent in f.findall("action"))]
    findings.append(finding(
        "NO_BOOT_AUTOSTART",
        not boot_receivers,
        "Não iniciar sessão de captura após boot; consentimento novo é obrigatório"))
    bad = sorted({label for label, pattern in PRIVACY_HAZARDS.items()
                  if any(re.search(pattern, src) for src in projection_sources.values())})
    findings.append(finding(
        "NO_CAPTURE_PERSISTENCE_OR_EXFIL_CALLS",
        not bad,
        "APIs suspeitas no caminho de captura: " + (", ".join(bad) if bad else "nenhuma detectada")))
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=".", help="Raiz do repositório local")
    p.add_argument("--require-capture", action="store_true",
                   help="Falhar se ainda não houver implementação MediaProjection")
    p.add_argument("--json", action="store_true", help="Saída JSON sem conteúdo privado")
    args = p.parse_args(argv)
    results = audit(Path(args.root), require_capture=args.require_capture)
    if args.json:
        print(json.dumps({"checks": results}, indent=2, ensure_ascii=False))
    else:
        for item in results:
            print(f"{item['status']:4} {item['code']}: {item['detail']}")
    return 1 if any(item["status"] == "FAIL" for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
