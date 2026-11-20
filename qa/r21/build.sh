#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp "$RUNNER_TEMP/aura-r21-builder.XXXXXX.sh")
trap 'rm -f "$tmp"' EXIT
python3 - "$tmp" <<'PY'
from pathlib import Path
import sys
s=Path("qa/r20/build.sh").read_text()
def swap(old,new):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f"R21: stale R20 build script: {old[:40]} found {n}")
    s=s.replace(old,new,1)
swap('vexo-r20-ocr-full','vexo-r21-aura-sync-voice')
swap('python3 qa/r20/check.py "$src"',
'''python3 qa/r20/check.py "$src"
python3 qa/r21/apply.py "$src"
python3 qa/r21/check.py "$src"
echo 'AURA_R21: generating 20 neural pt-BR phrases in an isolated Linux environment'
sudo apt-get update -qq >/dev/null
sudo apt-get install -qq -y espeak-ng ffmpeg >/dev/null
python3 -m venv "$work/aura-voice-venv"
"$work/aura-voice-venv/bin/pip" install --disable-pip-version-check --quiet --no-cache-dir "kokoro==0.9.4" "numpy" "soundfile"
"$work/aura-voice-venv/bin/python" qa/r21/generate_voice.py "$src/app/src/main/assets/aurora/aura-phrases.json" "$src/app/src/main/assets/aurora/voice"
[[ $(find "$src/app/src/main/assets/aurora/voice" -maxdepth 1 -name '*.ogg' | wc -l) == 20 ]]
python3 - "$src" <<'PYPATCH'
from pathlib import Path
import sys
p=Path(sys.argv[1])/"app/src/main/AndroidManifest.xml"
s=p.read_text()
assert s.count('android:label="Vexo R20"')==1
p.write_text(s.replace('android:label="Vexo R20"','android:label="Vexo"',1))
PYPATCH''')
swap('applicationId = "com.trackingracing.vexobeta.r20"','applicationId = "com.trackingracing.vexobeta.r21"')
swap(':app:assembleRelease',':app:testDebugUnitTest :app:assembleRelease')
swap('Vexo-R20-teste.apk','Vexo-R21-Aura-Sync.apk')
swap('CN=Vexo R20 Private Test','CN=Vexo R21 Private Test')
swap("package: name='com.trackingracing.vexobeta.r20'","package: name='com.trackingracing.vexobeta.r21'")
swap("application-label:'Vexo R20'","application-label:'Vexo'")
swap('python3 qa/r20/check_apk.py "$apk"',
     'python3 qa/r20/check_apk.py "$apk"\npython3 qa/r21/check_apk.py "$apk"')
Path(sys.argv[1]).write_text(s)
PY
bash "$tmp"
