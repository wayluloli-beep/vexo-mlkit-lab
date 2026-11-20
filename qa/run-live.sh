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
record_pid=''
stop_recording() {
  if [[ -n $record_pid ]]; then
    touch "$work/stop-recording"
    for _ in {1..21}; do
      kill -0 "$record_pid" 2>/dev/null || break
      sleep 1
    done
    kill "$record_pid" 2>/dev/null || true
    wait "$record_pid" 2>/dev/null || true
    record_pid=''
  fi
}
cleanup() {
  rc=$?
  set +e
  stop_recording
  printf 'stage=%s\nexit=%s\nrevision=%s\n' "$stage" "$rc" "${GITHUB_SHA:-unknown}" > "$OUT/job-result.txt"
  for n in kvm sdk-status build-status emulator-status; do
    [[ ! -s $work/$n ]] || cp -- "$work/$n" "$OUT/$n.txt"
  done
  if [[ -n $adb && -n $emulator_pid ]]; then
    timeout 12s "$adb" -s "$serial" logcat -d -v brief -s VexoOCR AndroidRuntime CrRendererMain ActivityManager |
      grep -Ei 'VexoOCR|com.trackingracing|ANR in|crashpad|Fatal signal|renderer' | tail -110 > "$OUT/android-logagem.txt" || true
    timeout 8s "$adb" -s "$serial" emu kill >/dev/null 2>&1 || true
  fi
  if [[ -n $emulator_pid ]]; then kill "$emulator_pid" 2>/dev/null || true; fi
  rm -rf -- "$work"
  if (( rc != 0 )); then report "FAILED_$stage:$rc"; fi
}
trap cleanup EXIT
[[ $GITHUB_REF == refs/heads/vexo-live-aurora-r11-once ]]
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
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then report VIDEO_TOOLS_AVAILABLE; else report VIDEO_TOOLS_CONTAINER_ONLY; fi
ui_python=$(command -v python3)
# Save unmodified screenshots independently of any host OCR/observer.
if command -v tesseract >/dev/null; then
  "$ui_python" qa/pixel-preflight.py --driver qa/driver.py || true
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
printf 'no\n' | timeout 45s "$cmdline/avdmanager" create avd -n vexo_s13_once -k "$image" > "$work/avd.log" 2>&1
"$emulator" -avd vexo_s13_once -port 5554 -accel on -gpu swiftshader \
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
timeout 900s "$work/gradle-8.11.1/bin/gradle" --project-dir "$work/src/aurora" --no-daemon --console=plain --max-workers=2   -Dorg.gradle.internal.http.connectionTimeout=20000 -Dorg.gradle.internal.http.socketTimeout=45000   :app:assembleRelease > "$work/build.log" 2>&1 || build_rc=$?
report "GRADLE_ASSEMBLE_EXIT:$build_rc"
if (( build_rc != 0 )); then
  grep -Ei 'Could not resolve|Could not GET|Could not HEAD|could not download|(^e:)|timeout|timed out|connection reset|failed to transform|BUILD FAILED|^What went wrong|Execution failed' "$work/build.log" |
    sed -E 's#(https?://)[^/@[:space:]]+:[^/@[:space:]]+@#\1[redacted]@#g' |
    grep -Eiv 'password|authorization|bearer|token' | tail -16 | tee "$work/build-status" || true
  exit "$build_rc"
fi
grep -q 'BUILD SUCCESSFUL' "$work/build.log"
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
grep -Fq "versionName='0.1.3'" "$work/candidate.badging"
grep -Fq "package: name='com.vexo.qa.pixels'" "$work/presenter.badging"
grep -E '^(package:|sdkVersion:|targetSdkVersion:)' "$work/candidate.badging" | sed 's/^/AURORA_APK: /'
"$bt/aapt" dump permissions "$work/candidate.apk" > "$OUT/candidate-permissions.txt"
grep -Fq 'android.permission.SYSTEM_ALERT_WINDOW' "$OUT/candidate-permissions.txt"
grep -Fq 'android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION' "$OUT/candidate-permissions.txt"
! grep -q 'BIND_ACCESSIBILITY_SERVICE' "$OUT/candidate-permissions.txt" || exit 1
(cd "$work" && sha256sum candidate.apk presenter.apk) | tee "$OUT/device-apks.sha256"
report SIGN_TEMP_OK

stage=INSTALL
for role in candidate presenter; do
  ADB_COMMAND_TIMEOUT=100s device install --streaming "$work/$role.apk" > "$work/$role.install"
  grep -Fxq Success "$work/$role.install"
done
device shell dumpsys webviewupdate | grep -E 'Current WebView package|Valid package' > "$OUT/webview.txt" || true
device shell getprop ro.build.fingerprint > "$OUT/android-fingerprint.txt"
sed 's/^/AURORA_DEVICE: /' "$OUT/android-fingerprint.txt"
device shell wm size 720x1280
device shell wm density 240
report BOTH_INSTALLED

stage=REAL_UI
export ADB="$adb" SERIAL="$serial" PKG=com.trackingracing FIXTURE="$work/src/fixtures/controle-0954.png"
record_video() {
  local path="/sdcard/VexoR9-External-Test.mp4" partial="$OUT/recording.partial" capture
  until [[ -s $OUT/record-external.ready ]]; do
    [[ ! -e $work/stop-recording ]] || return 0
    sleep .2
  done
  [[ ! -e $work/stop-recording ]] || return 0
  report SCREENRECORD_START
  timeout 82s "$adb" -s "$serial" shell screenrecord --size 540x960 --bit-rate 340000 --time-limit 70 "$path"     > "$OUT/screenrecord-status.txt" 2>&1 &
  capture=$!
  while kill -0 "$capture" 2>/dev/null; do
    if [[ -s $OUT/record-external.done || -e $work/stop-recording ]]; then
      timeout 6s "$adb" -s "$serial" shell pkill -2 -x screenrecord >/dev/null 2>&1 || true
      break
    fi
    sleep .3
  done
  wait "$capture" || true
  if timeout 12s "$adb" -s "$serial" pull "$path" "$partial" >/dev/null 2>&1 && [[ -s $partial ]]; then
    mv "$partial" "$OUT/vexo-fluxo.mp4"
    report "SCREENRECORD_PULLED_BYTES:$(stat -c %s "$OUT/vexo-fluxo.mp4")"
  else
    report SCREENRECORD_NOT_RECOVERED
    rm -f -- "$partial"
  fi
  timeout 4s "$adb" -s "$serial" shell rm -f "$path" >/dev/null 2>&1 || true
}
record_video &
record_pid=$!
set +e
timeout 480s "$ui_python" -u qa/driver.py 2>&1 | tee "$OUT/observacao.txt"
driver_rc=${PIPESTATUS[0]}
set -e
stop_recording
report "DRIVER_EXIT:$driver_rc"
if [[ -s $OUT/vexo-r10-native-timing.txt ]]; then
  sed -nE 's/^.*VexoR10[[:space:]]*:[[:space:]]+((cena=|limpeza_cena |ocr_inicio |ocr_fim |ocr_erro |descartado_cena |descartado_apos_parse |falha_isolada |ui_envio )[0-9a-z =_-]{1,155})$/R10_TIMING: \1/p' "$OUT/vexo-r10-native-timing.txt" | tail -200
  sed -nE 's/^.*VexoR11[[:space:]]*:[[:space:]]+((prewarm_inicio |prewarm_fim |prewarm_erro |ocr_pixels )[0-9a-z =_-]{1,155})$/R11_TIMING: \1/p' "$OUT/vexo-r10-native-timing.txt" | tail -100
fi
if [[ -s $OUT/driver-result.json ]]; then
  python3 -m json.tool "$OUT/driver-result.json" | sed 's/^/AURORA_RESULT: /'
  if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
    {
      printf '### Vexo Aurora Android R11 aquecimento\n\nCommit `%s`, driver exit `%s`.\n\n' "$GITHUB_SHA" "$driver_rc"
      printf '```json\n'
      python3 -m json.tool "$OUT/driver-result.json"
      printf '```\n'
    } >> "$GITHUB_STEP_SUMMARY"
  fi
fi
(( driver_rc == 0 )) || exit "$driver_rc"
test -s "$OUT/driver-result.json"
stage=COMPLETE
report UI_DRIVER_COMPLETED
