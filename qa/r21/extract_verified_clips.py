#!/usr/bin/env python3
"""Copy only the 20 verified Kokoro voice clips from a SHA256-pinned private R21 APK."""
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
import json
import sys

apk=Path(sys.argv[1])
catalog=Path(sys.argv[2])
out=Path(sys.argv[3])
names=json.loads(catalog.read_text())
assert len(names)==20
assert all(k.replace("_","").isalnum() for k in names)
out.mkdir(parents=True,exist_ok=True)
with ZipFile(apk) as z:
    for k in names:
        internal="assets/aurora/voice/"+k+".ogg"
        meta=z.getinfo(internal)
        if meta.compress_type!=ZIP_STORED or meta.file_size<1024 or meta.file_size>250000:
            raise RuntimeError("invalid expected voice clip "+k)
        b=z.read(internal)
        if not b.startswith(b"OggS"):
            raise RuntimeError("not real Ogg Vorbis audio "+k)
        (out/(k+".ogg")).write_bytes(b)
actual={x.name for x in out.iterdir() if x.is_file()}
expected={k+".ogg" for k in names}
assert actual==expected,actual^expected
print("AURA_R21_VERIFIED_CLIPS_REUSED: 20/20 neural audio recordings identical to source release")
