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
echo 'AURA_R21: reuse the 20 neural audio clips from the already verified private R21 build'
[[ -n "${GH_TOKEN:-}" ]]
command -v gh >/dev/null
mkdir -p "$work/aura-verified"
gh release download vexo-r21-aura-test-ba970986cca9-44826397620 -R wayluloli-beep/vexo-mlkit-lab -p Vexo-R21-Aura-Sync.apk -D "$work/aura-verified"
printf 'fce92d39748c51b7dff87ae86c3b2530953c4607e5cfbf8fef48a75120a582e5  %s\\n' "$work/aura-verified/Vexo-R21-Aura-Sync.apk" | sha256sum --strict --check
python3 qa/r21/extract_verified_clips.py "$work/aura-verified/Vexo-R21-Aura-Sync.apk" "$src/app/src/main/assets/aurora/aura-phrases.json" "$src/app/src/main/assets/aurora/voice"
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
if s.count('Vexo-R20-teste.apk') != 2: raise SystemExit('R21 unexpected R20 APK names')
s=s.replace('Vexo-R20-teste.apk','Vexo-R21-Aura-Sync.apk')
swap('CN=Vexo R20 Private Test','CN=Vexo R21 Private Test')
swap("package: name='com.trackingracing.vexobeta.r20'","package: name='com.trackingracing.vexobeta.r21'")
swap("application-label:'Vexo R20'","application-label:'Vexo'")
swap('python3 qa/r20/check_apk.py "$apk"',
     'python3 qa/r20/check_apk.py "$apk"\npython3 qa/r21/check_apk.py "$apk"')
Path(sys.argv[1]).write_text(s)
PY
bash "$tmp"
