#!/usr/bin/env python3
"""Fail closed on the merged target manifest for the isolated debug replay."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"
APP_ID = "com.trackingracing.replay"
ACTIVITY = APP_ID + ".ReplayActivity"
INIT = "com.google.mlkit.common.internal.MlKitInitProvider"
DISCOVERY = "com.google.mlkit.common.internal.MlKitComponentDiscoveryService"
COMPONENTS = {("activity", ACTIVITY), ("provider", INIT), ("service", DISCOVERY)}
REGISTRARS = {
    "com.google.firebase.components:com.google.mlkit.common.internal.CommonComponentRegistrar",
    "com.google.firebase.components:com.google.mlkit.vision.common.internal.VisionCommonRegistrar",
    "com.google.firebase.components:com.google.mlkit.vision.text.internal.TextRegistrar",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify(path):
    root = ET.parse(path).getroot()
    require(root.tag == "manifest" and root.get("package") == APP_ID, "wrong target manifest package")
    require(not root.get(ANDROID + "sharedUserId"), "sharedUserId not allowed")
    for node in root:
        require(node.tag in {"uses-sdk", "application"}, f"root capability not allowed: {node.tag}")
    apps = root.findall("application")
    require(len(apps) == 1, "expected one application")
    app = apps[0]
    require(app.get(ANDROID + "allowBackup") == "false", "allowBackup must be false")
    require(app.get(ANDROID + "usesCleartextTraffic") == "false", "usesCleartextTraffic must be false")
    for key in ("name", "backupAgent", "manageSpaceActivity", "networkSecurityConfig"):
        require(app.get(ANDROID + key) is None, f"application {key} not allowed")
    require(app.get(ANDROID + "appComponentFactory") in (None, "androidx.core.app.CoreComponentFactory"),
            "application appComponentFactory not allowed")
    seen = set()
    registrars = set()
    for node in app:
        name = node.get(ANDROID + "name")
        if node.tag == "meta-data" and name == "com.google.android.gms.version":
            require(len(node) == 0, "nested gms metadata not allowed")
            continue
        if name and name.startswith("."):
            name = APP_ID + name
        key = (node.tag, name)
        require(key in COMPONENTS and key not in seen, f"unexpected component: {node.tag} {name}")
        seen.add(key)
        require(node.get(ANDROID + "exported") == "false", f"{name} exported must be false")
        require(node.get(ANDROID + "grantUriPermissions") in (None, "false"),
                f"{name} grantUriPermissions not allowed")
        require(node.get(ANDROID + "foregroundServiceType") is None, f"{name} declares foregroundServiceType")
        for child in node:
            registrar = child.get(ANDROID + "name")
            require(name == DISCOVERY and child.tag == "meta-data" and len(child) == 0
                    and registrar in REGISTRARS and registrar not in registrars
                    and child.get(ANDROID + "value") == "com.google.firebase.components.ComponentRegistrar",
                    f"{name} unexpected child {child.tag}")
            registrars.add(registrar)
        if name == INIT:
            require(node.get(ANDROID + "authorities") == APP_ID + ".mlkitinitprovider",
                    "ML Kit provider authority does not match target package")
    require(seen == COMPONENTS, f"missing expected components: {sorted(COMPONENTS - seen)}")
    require(registrars == REGISTRARS, f"missing ML Kit registrar: {sorted(REGISTRARS - registrars)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: verify-manifest.py PATH_TO_MERGED_TARGET_MANIFEST")
    try:
        verify(Path(sys.argv[1]))
    except (ET.ParseError, OSError, ValueError) as exc:
        sys.exit(f"S13 manifest FAIL: {exc}")
    print("S13 manifest PASS: private replay and ML Kit initialization only")
