#!/usr/bin/env python3
from zipfile import ZipFile
import sys,re,json
with ZipFile(sys.argv[1]) as z:
    names=set(z.namelist())
    catalog=json.loads(z.read("assets/aurora/aura-phrases.json"))
    assert len(catalog)==20
    for name in catalog:
        p="assets/aurora/voice/"+name+".ogg"
        assert p in names,p
        info=z.getinfo(p)
        assert info.file_size>1024, p
        assert info.compress_type==0,p
    assert "assets/simulador99.html" not in names
    dex=b''.join(z.read(p) for p in names if re.fullmatch(r'classes\d*\.dex',p))
    assert b'com/trackingracing/AuraVoice' in dex
    assert b'com/trackingracing/ScreenCaptureService' in dex
    assert b'com/google/mlkit' in dex
print("AURA_R21_APK: 20 offline neural clips, real reader and Aura UI bundled, simulator absent")
