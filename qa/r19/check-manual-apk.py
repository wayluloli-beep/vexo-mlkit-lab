"""Verify the built QA artifact, not just the source manifest."""
from pathlib import Path
import re
import subprocess
import sys
from xml.etree.ElementTree import parse
from zipfile import ZipFile

apk, aapt, result = map(Path, sys.argv[1:])
metadata = subprocess.check_output([aapt, "dump", "badging", apk], text=True)
perms = subprocess.check_output([aapt, "dump", "permissions", apk], text=True)
assert "package: name='com.trackingracing' versionCode='6'" in metadata, metadata.splitlines()[0]
assert "sdkVersion:'26'" in metadata and "targetSdkVersion:'36'" in metadata
assert not re.search(r"FOREGROUND_SERVICE|LOCATION|BLUETOOTH|SYSTEM_ALERT_WINDOW|POST_NOTIFICATIONS", perms)
with ZipFile(apk) as z:
    names = z.namelist()
    dex = [z.read(name) for name in names if re.fullmatch(r"classes\d*\.dex", name)]
    assert dex and any(b"Lcom/trackingracing/VexoManualWeb;" in blob for blob in dex)
    for code in (b"Lcom/trackingracing/ScreenCaptureService;", b"Lcom/trackingracing/SincronizadorPlanilha;",
                 b"Lcom/google/mlkit/", b"Landroidx/work/Worker;"):
        assert not any(code in blob for blob in dex), code
    assert not any("simulador99" in name or "lab99" in name for name in names)
    assert "assets/aurora/central.html" in names and "assets/aurora/turno.js" in names
print("R19_APK: manual mode, API 26 min and 36 target, no OCR or legacy sync in DEX")
suites = [parse(xml).getroot() for xml in result.glob("TEST-*.xml")]
totals = {k: sum(int(s.get(k, "0")) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
assert totals == {"tests": 5, "failures": 0, "errors": 0, "skipped": 0}, totals
print("R19_JVM: five tests passed")
