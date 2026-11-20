#!/usr/bin/env bash
set -euo pipefail
umask 077
export LC_ALL=C
stage=SOURCE
report() { printf 'AURORA_QA:%s\n' "$1"; }
work=$(mktemp -d "$RUNNER_TEMP/vexo-aurora.XXXXXXXX")
OUT="$RUNNER_TEMP/vexo-live-evidence"
export OUT
mkdir -p "$OUT"
adb=''
emulator_pid=''
serial=emulator-5554
cleanup() {
  rc=$?
  set +e
  printf 'stage=%s\nexit=%s\nrevision=%s\n' "$stage" "$rc" "${GITHUB_SHA:-unknown}" > "$OUT/job-result.txt"
  if [[ -n $adb && -n $emulator_pid ]]; then
    timeout 8s "$adb" -s "$serial" emu kill >/dev/null 2>&1 || true
    kill "$emulator_pid" 2>/dev/null || true
  fi
  rm -rf -- "$work"
  if (( rc != 0 )); then report "FAILED_$stage:$rc"; fi
}
trap cleanup EXIT
[[ $GITHUB_REPOSITORY == wayluloli-beep/vexo-mlkit-lab && $GITHUB_RUN_ATTEMPT == 1 ]]
[[ $GITHUB_EVENT_NAME == create && $GITHUB_REF == refs/heads/vexo-product-r16-card-once ]]
[[ $(git rev-parse HEAD) == "$GITHUB_SHA" ]]
[[ $(git ls-tree -r --name-only HEAD qa/payload | wc -l) == 24 ]]
printf '%s  %s\n' '1f1e08574699aabab795687db1816a5962d033652879b21d924cfc590d50199d' "$work/payload.tar.gz" > "$work/payload-check"
printf '%s  %s\n' '60ee91f33f41194f8514e926e4dbb692961cee2cd7fd983a45366b644facf7d9' qa/qa-source.sha256 | sha256sum --strict --check --status
cat qa/payload/chunk-* > "$work/payload.tar.gz"
sha256sum --strict --check --status "$work/payload-check"
mkdir -p "$work/src"
python3 - "$work/payload.tar.gz" "$work/src" <<'PY'
from pathlib import Path
import sys, tarfile
with tarfile.open(sys.argv[1], 'r:gz') as t:
    members = t.getmembers()
    names = [m.name for m in members]
    assert len(set(names)) == len(names) == 67
    assert all(m.isfile() and (m.name.startswith('aurora/') or m.name.startswith('fixtures/')) for m in members)
    assert all('..' not in Path(m.name).parts for m in members)
    t.extractall(sys.argv[2], filter='data')
PY
(cd "$work/src" && sha256sum --strict --check --status "$GITHUB_WORKSPACE/qa/qa-source.sha256")
report "SOURCE_OK:$GITHUB_SHA"

stage=PRODUCT
python3 qa/apply-checked-product.py "$work/src/aurora"
report PRODUCT_OVERLAY_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r10.patch
(cd "$work/src/aurora" && sha256sum --strict --check "$GITHUB_WORKSPACE/qa/product-r10.sha256")
report FRESHNESS_PATCH_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r11.patch
(cd "$work/src/aurora" && sha256sum --strict --check "$GITHUB_WORKSPACE/qa/product-r11.sha256")
report PREWARM_PATCH_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r12.patch
(cd "$work/src/aurora" && sha256sum --strict --check "$GITHUB_WORKSPACE/qa/product-r12.sha256")
report PENDING_NEWEST_FRAME_PATCH_CHECKED
PYTHONDONTWRITEBYTECODE=1 python3 qa/apply-r13-product.py "$work/src/aurora"
report R13_PRODUCT_LAYER_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r14.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$GITHUB_WORKSPACE/qa/product-r14.sha256")
report R14_CAPTURE_ID_LAYER_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r15.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$GITHUB_WORKSPACE/qa/product-r15.sha256")
report R15_WARM_LAYER_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r16.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$GITHUB_WORKSPACE/qa/product-r16.sha256")
report R16_CROP_LAYER_CHECKED
VEXO_HTML="$work/src/aurora/app/src/main/assets/aurora/index.html" node --test qa/local_ocr_region.test.cjs
# Save unmodified screenshots independently of any host OCR/observer.
if command -v tesseract >/dev/null; then
  python3 qa/pixel-preflight.py --driver qa/driver.py > "$work/pixel-observer.log" 2>&1 || true
else
  report PIXEL_OBSERVER_UNAVAILABLE_VISUAL_EVIDENCE_REQUIRED
fi

stage=KVM_DEVICE
printf 'Runner image: %s %s\n' "${ImageOS:-unknown}" "${ImageVersion:-unknown}"
[[ $(uname -m) == x86_64 && -c /dev/kvm ]]
report KVM_DEVICE_PRESENT

stage=KVM_PERMISSION
if [[ ! -r /dev/kvm || ! -w /dev/kvm ]]; then
  if command -v setfacl >/dev/null; then
    sudo -n setfacl -m "u:$(id -u):rw" /dev/kvm
  else
    sudo -n chgrp "$(id -gn)" /dev/kvm
    sudo -n chmod g+rw /dev/kvm
  fi
fi
[[ -r /dev/kvm && -w /dev/kvm ]]
python3 - <<'PYKVM'
import fcntl, os
fd = os.open("/dev/kvm", os.O_RDWR | os.O_CLOEXEC)
try:
    api = fcntl.ioctl(fd, 0xAE00)
    assert api == 12, api
finally:
    os.close(fd)
PYKVM
report KVM_API_12_OK

stage=SDK_ROOT
sdk=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
[[ -n $sdk && -d $sdk/cmdline-tools ]]
mgr="$sdk/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x $mgr ]]; then
  mgr=$(find "$sdk/cmdline-tools" -type f -path '*/bin/sdkmanager' | sort -V | tail -1)
fi
[[ -x $mgr ]]
cmdline=$(dirname -- "$mgr")
export JAVA_HOME=${JAVA_HOME_17_X64:?}
export PATH="$JAVA_HOME/bin:$PATH"
export GRADLE_USER_HOME="$work/gradle-home" ANDROID_USER_HOME="$work/android-home" ANDROID_AVD_HOME="$work/avd"
mkdir -p "$GRADLE_USER_HOME" "$ANDROID_USER_HOME" "$ANDROID_AVD_HOME"
unset ADB_SERVER_SOCKET ANDROID_ADB_SERVER_PORT ANDROID_ADB_SERVER_ADDRESS ANDROID_SERIAL
adb="$sdk/platform-tools/adb"
emulator="$sdk/emulator/emulator"
signer="$sdk/build-tools/35.0.0/apksigner"
image='system-images;android-35;google_apis;x86_64'

stage=SDK_EMULATOR
packages=()
[[ -x $emulator ]] || packages+=(emulator)
[[ -x $adb ]] || packages+=(platform-tools)
if (( ${#packages[@]} )); then
  timeout 300s "$mgr" --sdk_root="$sdk" --install "${packages[@]}" > "$work/sdk.log" 2>&1 || {
    grep -Ei 'error|failed|license|insufficient' "$work/sdk.log" | tail -8 > "$work/sdk-status" || true
    exit 1
  }
fi
[[ -x $emulator && -x $adb ]]
report EMULATOR_ADB_PRESENT

stage=ACCEL_CHECK
"$emulator" -accel-check > "$work/kvm" 2>&1
grep -Eiq 'KVM .*installed and usable' "$work/kvm"
report ACCEL_CHECK_KVM_OK

stage=SDK_IMAGE
if [[ ! -f $sdk/system-images/android-35/google_apis/x86_64/package.xml ]]; then
  timeout 300s "$mgr" --sdk_root="$sdk" --install "$image" > "$work/sdk.log" 2>&1 || {
    grep -Ei 'error|failed|license|insufficient' "$work/sdk.log" | tail -8 > "$work/sdk-status" || true
    exit 1
  }
fi
[[ -f $sdk/system-images/android-35/google_apis/x86_64/package.xml ]]
[[ -x $cmdline/avdmanager ]]
report API35_IMAGE_PRESENT

stage=BOOT
serial=emulator-5554
transports() { timeout 9s "$adb" devices | awk 'NR>1 && NF {print $1 " " $2}'; }
device() {
  local rows
  rows=$(transports) || return 1
  [[ $rows == "$serial device" ]] || return 1
  timeout "${ADB_COMMAND_TIMEOUT:-60s}" "$adb" -s "$serial" "$@"
}
rows=$(transports) || exit 1
[[ -z $rows ]]
printf 'no\n' | timeout 45s "$cmdline/avdmanager" create avd -n vexo_product_r13_once -k "$image" > "$work/avd.log" 2>&1
"$emulator" -avd vexo_product_r13_once -port 5554 -accel on -gpu swiftshader \
  -no-window -no-audio -no-boot-anim -no-snapshot -wipe-data > "$work/emulator.log" 2>&1 &
emulator_pid=$!
deadline=$((SECONDS + 210))
boot=''
while (( SECONDS < deadline )); do
  if ! kill -0 "$emulator_pid"; then
    grep -Ei 'fatal|error|failed|KVM' "$work/emulator.log" | tail -8 > "$work/emulator-status" || true
    exit 1
  fi
  rows=$(transports) || exit 1
  case $rows in
    '') ;;
    "$serial offline") ;;
    "$serial device")
      boot=$(device shell getprop sys.boot_completed | tr -d '\r') || boot=''
      if [[ $boot == 1 ]]; then break; fi
      ;;
    *) exit 1 ;;
  esac
  sleep 2
done
[[ $boot == 1 ]]
[[ $(device shell getprop ro.build.version.sdk | tr -d '\r') == 35 ]]
[[ $(device shell getprop ro.product.cpu.abi | tr -d '\r') == x86_64 ]]
pm_ready=''
for attempt in {1..12}; do
  if device shell cmd package path android > "$work/boot-pm.log" 2>&1 && grep -q '^package:' "$work/boot-pm.log"; then
    pm_ready=1
    break
  fi
  sleep 2
done
[[ $pm_ready == 1 ]]
device shell wm dismiss-keyguard > "$work/keyguard.log" 2>&1
report BOOT_API35_X86_64_OK
stage=OFFLINE
device shell cmd connectivity airplane-mode enable > "$work/airplane.log" 2>&1
device shell svc wifi disable
[[ $(device shell settings get global airplane_mode_on | tr -d '\r') == 1 ]]
report DEVICE_OFFLINE_OK

stage=SDK_BUILD
packages=()
[[ -x $signer ]] || packages+=(build-tools\;35.0.0)
[[ -f $sdk/platforms/android-35/android.jar ]] || packages+=(platforms\;android-35)
if (( ${#packages[@]} )); then
  timeout 240s "$mgr" --sdk_root="$sdk" --install "${packages[@]}" > "$work/sdk.log" 2>&1 || {
    grep -Ei 'error|failed|license|insufficient' "$work/sdk.log" | tail -8 > "$work/sdk-status" || true
    exit 1
  }
fi
[[ -x $signer && -f $sdk/platforms/android-35/android.jar ]]

stage=GRADLE
curl --fail --location --silent --show-error --max-time 180 \
  'https://downloads.gradle.org/distributions/gradle-8.11.1-bin.zip' -o "$work/gradle.zip"
printf 'f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6  %s\n' "$work/gradle.zip" | sha256sum --strict --check --status
unzip -q "$work/gradle.zip" -d "$work"
report TOOLS_OK



stage=BUILD_UNSIGNED
unset APK_KEYSTORE_FILE APK_STORE_PASSWORD APK_KEY_ALIAS APK_KEY_PASSWORD GITHUB_RUN_NUMBER
report GRADLE_ASSEMBLE_START
build_rc=0
timeout 900s "$work/gradle-8.11.1/bin/gradle" --project-dir "$work/src/aurora" --no-daemon --console=plain --max-workers=2   -Dorg.gradle.internal.http.connectionTimeout=20000 -Dorg.gradle.internal.http.socketTimeout=45000   :app:assembleRelease :app:testDebugUnitTest > "$work/build.log" 2>&1 || build_rc=$?
report "GRADLE_ASSEMBLE_EXIT:$build_rc"
if (( build_rc != 0 )); then
  grep -Ei 'Could not resolve|Could not GET|Could not HEAD|could not download|(^e:)|timeout|timed out|connection reset|failed to transform|BUILD FAILED|^What went wrong|Execution failed' "$work/build.log" |
    sed -E 's#(https?://)[^/@[:space:]]+:[^/@[:space:]]+@#\1[redacted]@#g' |
    grep -Eiv 'password|authorization|bearer|token' | tail -16 | tee "$work/build-status" || true
  exit "$build_rc"
fi
grep -q 'BUILD SUCCESSFUL' "$work/build.log"
python3 - "$work/src/aurora/app/build/test-results/testDebugUnitTest" <<'PYJUNIT'
from pathlib import Path
from xml.etree import ElementTree as E
import sys
r=[E.parse(x).getroot() for x in Path(sys.argv[1]).glob("TEST-*.xml")]
counts={k:sum(int(a.get(k, 0)) for a in r) for k in ("tests","failures","errors","skipped")}
assert counts['tests'] >= 63 and not any(counts[k] for k in ("failures","errors"))
print("R16_JUNIT: "+" ".join(str(k)+"="+str(v) for k,v in counts.items()))
PYJUNIT
mapfile -t apks < <(find "$work/src/aurora/app/build/outputs/apk/release" -maxdepth 1 -name '*unsigned.apk')
[[ ${#apks[@]} == 1 ]]
report AURORA_UNSIGNED_BUILT

stage=SIGN_TEMP
bt="$sdk/build-tools/35.0.0"
[[ -x $bt/zipalign && -x $bt/aapt && -x $signer ]]
mkdir -p "$work/private"
keytool -genkeypair -noprompt -storetype PKCS12 -keyalg RSA -keysize 2048 -validity 2   -dname 'CN=Vexo Aurora QA Disposable only' -alias vexoqa   -keystore "$work/private/qa.p12" -storepass android > "$work/keytool.log" 2>&1
sign_qa() {
  local input=$1 role=$2
  "$bt/zipalign" -P 16 -f 4 "$input" "$work/$role-aligned.apk"
  "$signer" sign --ks "$work/private/qa.p12" --ks-key-alias vexoqa --ks-pass pass:android     --out "$work/$role.apk" "$work/$role-aligned.apk"
  "$signer" verify --print-certs "$work/$role.apk" > "$work/$role.cert"
  "$bt/aapt" dump badging "$work/$role.apk" > "$work/$role.badging"
}
sign_qa "${apks[0]}" candidate
sign_qa "$work/src/fixtures/source-unsigned.apk" presenter
cert_a=$(sed -n 's/^Signer #1 certificate SHA-256 digest: //p' "$work/candidate.cert")
cert_b=$(sed -n 's/^Signer #1 certificate SHA-256 digest: //p' "$work/presenter.cert")
[[ ${#cert_a} == 64 && $cert_a == "$cert_b" ]]
printf 'QA public certificate SHA-256 %s\n' "$cert_a" > "$OUT/qa-public-cert.txt"
report "SIGNER_QA_SHA256:$cert_a"
rm -f -- "$work/private/qa.p12"
grep -Fq "package: name='com.trackingracing'" "$work/candidate.badging"
grep -Fq "versionName='0.1.3-r16-interno'" "$work/candidate.badging"
grep -Fq "package: name='com.vexo.qa.pixels'" "$work/presenter.badging"
grep -E '^(package:|sdkVersion:|targetSdkVersion:)' "$work/candidate.badging" | sed 's/^/AURORA_APK: /'
"$bt/aapt" dump permissions "$work/candidate.apk" > "$OUT/candidate-permissions.txt"
grep -Fq 'android.permission.SYSTEM_ALERT_WINDOW' "$OUT/candidate-permissions.txt"
grep -Fq 'android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION' "$OUT/candidate-permissions.txt"
! grep -q 'BIND_ACCESSIBILITY_SERVICE' "$OUT/candidate-permissions.txt" || exit 1
(cd "$work" && sha256sum candidate.apk presenter.apk) > "$OUT/signed-source-apks.sha256"
report SIGN_TEMP_OK

stage=REAL_UI
device shell wm size 720x1280
device shell wm density 240
unset VEXO_PRODUCT_ONLY
export ADB="$adb" SERIAL="$serial" PKG=com.trackingracing
export VEXO_R12_DRIVER="$GITHUB_WORKSPACE/qa/driver.py"
# Runner side keeps raw ADB logs and captures ephemeral. The next workflow step retains only
# PNGs passing the narrow evidence validator, regardless of this wrapper's exit status.
driver_rc=0
bash qa/run-local.sh "$work/candidate.apk" "$work/presenter.apk" > "$work/driver.log" 2>&1 || driver_rc=$?
report "DRIVER_EXIT:$driver_rc"
sed -nE 's/^LIVE:([a-zA-Z0-9_-]{1,64}):([A-Z_]{1,32})([ ].*)?$/R16_STEP: \1 \2/p' "$work/driver.log" | tail -85
if [[ -s $OUT/local-ocr.log ]]; then
  sed -nE 's/^.*VexoLocalOcr[[:space:]]*:[[:space:]]+(witness=[a-z_]{1,30} card=[0-9]{1,18}-[0-9]{1,6} t=[0-9]{1,18}( cap=[0-9]{1,18})?)$/R16_WITNESS: \1/p' "$OUT/local-ocr.log" | tail -80
  sed -nE 's/^.*VexoLocalOcr[[:space:]]*:[[:space:]]+(warm=(start|ready|failed) t=[0-9]{1,18}( ms=[0-9]{1,18})?)$/R16_WARM: \1/p' "$OUT/local-ocr.log" | tail -8
  sed -nE 's/^.*VexoLocalOcr[[:space:]]*:[[:space:]]+((pixels src=(pixelcopy|web_draw)|parsed kind=(pop|negocia)|dispatched kind=offer|accepted kind=offer) cap=[0-9]{1,18} card=[0-9]{1,18}-[0-9]{1,6})$/R16_LOCAL: \1/p' "$OUT/local-ocr.log" | tail -24
fi
if [[ -s $OUT/vexo-r10-native-timing.txt ]]; then
  sed -nE 's/^.*VexoR10[[:space:]]*:[[:space:]]+((ocr_inicio |ocr_fim |descartado_cena |ui_envio |limpeza_cena )[0-9a-z =_-]{1,155})$/R16_EXTERNAL: \1/p' "$OUT/vexo-r10-native-timing.txt" | tail -48
fi

# No exception reasons, UI dumps or raw data make it into remote step logs.
python3 - "$OUT" <<'PYRESULT'
import json, pathlib, re, sys
out=pathlib.Path(sys.argv[1])
for path in (out/'device-apks.sha256',):
    if path.is_file() and path.stat().st_size < 512:
        for line in path.read_text().splitlines():
            if re.fullmatch(r'[a-f0-9]{64}  (com\.trackingracing|com\.vexo\.qa\.pixels)', line):
                print('R16_INSTALLED: '+line)
result=out/'driver-result.json'
if result.is_file() and result.stat().st_size <= 1024*1024:
    try:
        obj=json.loads(result.read_text())
        if not isinstance(obj, dict): raise ValueError()
    except (ValueError, OSError):
        sys.exit(0)
    for name in ('product_real_ocr_chain', 'collection_complete', 'stop'):
        value=obj.get(name)
        if type(value) is bool:
            print('R16_RESULT: '+name+'='+str(value).lower())
    allowed={'PASS','NOT_RUN','NOT_PROVEN','INCONCLUSIVE','VISUAL_REVIEW_REQUIRED','FAIL_OTHER_SCENE'}
    if isinstance(obj.get('primary_chain'), str) and obj['primary_chain'] in allowed:
        print('R16_RESULT: external_chain='+obj['primary_chain'])
    states=obj.get('product_stages')
    allowed|={'OBSERVED_AND_ACCEPTED','NOT_OBSERVED','PENDING','INCONCLUSIVE','ATTEMPTED'}
    if isinstance(states,dict):
        for name in ('launcher','first_terms','welcome_and_example','central_navigation','local_ocr','local_card_1_metrics','local_card_1_native','local_next_card','local_card_2_native','local_prewarm','local_cleanup','external_attempt'):
            state=states.get(name)
            if isinstance(state,str) and state in allowed:
                print('R16_RESULT: '+name+'='+state)
    states=obj.get('variants')
    if isinstance(states,dict):
        for name in ('A','B','N'):
            state=states.get(name)
            if isinstance(state,str) and state in allowed:
                print('R16_RESULT: '+name+'='+state)
PYRESULT
(( driver_rc == 0 )) || exit "$driver_rc"
test -s "$OUT/driver-result.json"
stage=COMPLETE
report UI_DRIVER_COMPLETED
