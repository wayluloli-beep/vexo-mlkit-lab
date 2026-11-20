#!/usr/bin/env python3
from zipfile import ZipFile
import re,sys
with ZipFile(sys.argv[1]) as z:
    names=set(z.namelist())
    dex=b''.join(z.read(p) for p in names if re.fullmatch(r'classes\d*\.dex',p))
    for marker in (b'com/trackingracing/ScreenCaptureService',b'com/trackingracing/PainelOcrFlutuante',b'com/google/mlkit',b'com/trackingracing/AuroraActivity'):
        assert marker in dex,marker
    for path in ('assets/aurora/r20-drawer.css','assets/aurora/r20-drawer.js','assets/aurora/central.html','assets/aurora/privacy-values.js'):
        assert path in names,path
    assert 'assets/simulador99.html' not in names
print("R20_APK: ML Kit, OCR overlay, screenshot service and menu bundled; in-app 99 simulator absent")
