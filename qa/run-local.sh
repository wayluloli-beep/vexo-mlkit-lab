#!/usr/bin/env bash
set -euo pipefail
umask 077
front=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
candidate=$(realpath -- "${1:?candidate APK required}")
presenter=$(realpath -- "${2:?presenter APK required}")
: "${ADB:?}" "${SERIAL:?}" "${PKG:?}" "${OUT:?}"
[[ $SERIAL == emulator-5554 || $SERIAL == emulator-5556 ]]
[[ $PKG == com.trackingracing && -s $candidate && -s $presenter ]]
mkdir -p "$OUT"
dev() { timeout "${ADB_TIMEOUT:-22}s" "$ADB" -s "$SERIAL" "$@"; }
rec=""
stage=BOOT_GATE
cleanup() {
  local rc=$?
  printf 'stage=%s exit=%s\n' "$stage" "$rc" > "$OUT/shell-result.txt"
  if [[ -n $rec ]]; then
    touch "$OUT/record-external.done"
    wait "$rec" 2>/dev/null || true
  fi
  # Preserve the device briefly after an inconclusive local run so a corrected selector
  # can be retried on the same disposable AVD without a six-minute reboot. No CI wait.
  if (( rc != 0 )) && [[ $SERIAL == emulator-5556 && ${ANDROID_AVD_HOME:-} == /tmp/vexo-r13-avd-*/avd ]] &&
     [[ $(dev get-state 2>/dev/null || true) == device ]]; then
    local limit=$((SECONDS + 180))
    printf '%s\n' 'LOCAL_RESULT_INCONCLUSIVE; qualified selector retry available for 180s'
    : > "$front/runtime/retry-available"
    while [[ ! -e $front/runtime/retry ]]; do
      (( SECONDS < limit )) || break
      sleep 2
    done
    rm -f -- "$front/runtime/retry-available"
    if [[ -e $front/runtime/retry ]]; then
      rm -f -- "$front/runtime/retry"
      trap - EXIT
      for retry_package in "$PKG" com.vexo.qa.pixels; do
        if [[ $(dev shell pm path "$retry_package" 2>/dev/null || true) == package:* ]]; then
          dev uninstall "$retry_package" | grep -Fxq Success || exit 1
        fi
      done
      mv -- "$OUT" "$OUT.inconclusive.$(date -u +%Y%m%dT%H%M%SZ)"
      exec bash "$front/run-local.sh" "$candidate" "$presenter"
    fi
  fi
  return "$rc"
}
trap cleanup EXIT

package_hash() {
  local pkg=$1 local_path=$2 row remote device_sum expected
  expected=$(sha256sum "$local_path" | cut -d ' ' -f1)
  row=$(dev shell pm path "$pkg") || return 1
  [[ $row =~ ^package:(/[[:alnum:]/_.=+~-]+/base[.]apk)$ ]] || return 1
  remote=${BASH_REMATCH[1]}
  device_sum=$(dev shell sha256sum "$remote" | cut -d ' ' -f1)
  [[ $device_sum == "$expected" ]] || return 1
  printf '%s  %s\n' "$device_sum" "$pkg"
}
install_and_hash() {
  local pkg=$1 path=$2
  ADB_TIMEOUT=180 dev install --streaming "$path" > "$OUT/install-$pkg.txt"
  grep -Fxq 'Success' "$OUT/install-$pkg.txt"
  package_hash "$pkg" "$path"
}
[[ $(dev get-state) == device && $(dev shell getprop ro.build.version.sdk) == 35 && $(dev shell getprop sys.boot_completed) == 1 ]]
dev shell dumpsys webviewupdate | grep -E 'Current WebView package|Valid package' > "$OUT/webview.txt"
dev shell getprop ro.build.fingerprint > "$OUT/android-fingerprint.txt"
dev shell cmd package list packages "$PKG" > "$OUT/package-before.txt"
[[ ! -s $OUT/package-before.txt ]]
dev shell wm dismiss-keyguard
stage=OFFLINE_DEVICE
dev shell cmd connectivity airplane-mode enable > "$OUT/android-airplane-mode.txt" 2>&1
dev shell svc wifi disable
[[ $(dev shell settings get global airplane_mode_on | tr -d '\r') == 1 ]]
printf '%s\n' 'airplane_mode_verified=1' >> "$OUT/android-airplane-mode.txt"
stage=APK_INSTALL_AND_HASH
{
  install_and_hash "$PKG" "$candidate"
  install_and_hash com.vexo.qa.pixels "$presenter"
} | tee "$OUT/device-apks.sha256"
rm -f -- "$OUT/record-external.ready" "$OUT/record-external.done"
record_path=/sdcard/VexoR13-External-Test.mp4
record() {
  while [[ ! -s $OUT/record-external.ready ]]; do
    [[ ! -e $OUT/record-external.done ]] || return 0
    sleep .2
  done
  local capture
  dev shell rm -f "$record_path" || true
  ADB_TIMEOUT=110 dev shell screenrecord --size 540x960 --bit-rate 340000 --time-limit 85 "$record_path" > "$OUT/external-screenrecord.txt" 2>&1 &
  capture=$!
  while kill -0 "$capture" 2>/dev/null; do
    if [[ -e $OUT/record-external.done ]]; then
      dev shell pkill -2 -x screenrecord >/dev/null 2>&1 || true
      break
    fi
    sleep .3
  done
  wait "$capture" || true
  dev pull "$record_path" "$OUT/external-flow.mp4" > "$OUT/external-pull.txt" 2>&1 || true
  dev shell rm -f "$record_path" || true
}
record &
rec=$!
stage=ADB_DRIVER
set +e
PYTHONDONTWRITEBYTECODE=1 timeout 900s python3 -u "$front/r13_product_flow.py" 2>&1 | tee "$OUT/driver-console.txt"
status=${PIPESTATUS[0]}
set -e
stage=APK_FINAL_HASH
if ! { package_hash "$PKG" "$candidate" && package_hash com.vexo.qa.pixels "$presenter"; } > "$OUT/device-apks-after.sha256" ||
   ! cmp -s "$OUT/device-apks.sha256" "$OUT/device-apks-after.sha256"; then
  printf '%s\n' 'SAME_APK_EXIT_HASH_NOT_PROVEN'
  exit 1
fi
stage=COMPLETE
exit "$status"
