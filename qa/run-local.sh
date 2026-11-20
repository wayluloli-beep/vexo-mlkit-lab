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
package_hash() {
  local pkg=$1 local_path=$2 row remote device_sum expected
  expected=$(sha256sum "$local_path" | cut -d ' ' -f1)
  row=$(dev shell pm path "$pkg")
  [[ $row =~ ^package:(/[[:alnum:]/_.=+~-]+/base[.]apk)$ ]]
  remote=${BASH_REMATCH[1]}
  device_sum=$(dev shell sha256sum "$remote" | cut -d ' ' -f1)
  [[ $device_sum == "$expected" ]]
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
dev shell svc wifi disable
dev shell svc data disable
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
cleanup() {
  touch "$OUT/record-external.done"
  wait "$rec" 2>/dev/null || true
}
trap cleanup EXIT
set +e
PYTHONDONTWRITEBYTECODE=1 timeout 900s python3 -u "$front/r13_product_flow.py" 2>&1 | tee "$OUT/driver-console.txt"
status=${PIPESTATUS[0]}
set -e
if ! { package_hash "$PKG" "$candidate" && package_hash com.vexo.qa.pixels "$presenter"; } > "$OUT/device-apks-after.sha256" ||
   ! cmp -s "$OUT/device-apks.sha256" "$OUT/device-apks-after.sha256"; then
  printf '%s\n' 'SAME_APK_EXIT_HASH_NOT_PROVEN'
  exit 1
fi
exit "$status"
