#!/usr/bin/env bash
set -euo pipefail
umask 077
export LC_ALL=C
[[ ${GITHUB_REPOSITORY:-} == wayluloli-beep/vexo-mlkit-lab && ${GITHUB_REF:-} == refs/heads/vexo-product-r19-privacy-recheck ]]
export JAVA_HOME="${JAVA_HOME_17_X64:?}"
export PATH="$JAVA_HOME/bin:$PATH"
sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[[ -n $sdk && -c /dev/kvm ]]
mgr="$sdk/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x $mgr ]]; then
  mgr=$(find "$sdk/cmdline-tools" -type f -path '*/bin/sdkmanager' | sort -V | tail -1)
fi
[[ -x $mgr ]]
export ADB="$sdk/platform-tools/adb"
emulator="$sdk/emulator/emulator"
serial=emulator-5554
work=$(mktemp -d "$RUNNER_TEMP/vexo-journey.XXXXXX")
emu_pid=''
clean() {
  rc=$?
  set +e
  if [[ -n $emu_pid ]]; then timeout 8s "$ADB" -s "$serial" emu kill >/dev/null; kill "$emu_pid" 2>/dev/null; fi
  rm -rf -- "$work"
  exit "$rc"
}
trap clean EXIT
bash qa/r19/materialize.sh "$work"
python3 qa/r19/isolate-native.py "$work/src/aurora"
export ANDROID_USER_HOME="$work/android" ANDROID_AVD_HOME="$work/avd" GRADLE_USER_HOME="$work/gradle-home"
mkdir -p "$ANDROID_USER_HOME" "$ANDROID_AVD_HOME"
unset ADB_SERVER_SOCKET ANDROID_ADB_SERVER_PORT ANDROID_ADB_SERVER_ADDRESS ANDROID_SERIAL
unset APK_KEYSTORE_FILE APK_STORE_PASSWORD APK_KEY_ALIAS APK_KEY_PASSWORD GITHUB_RUN_NUMBER
if [[ ! -r /dev/kvm || ! -w /dev/kvm ]]; then
  if command -v setfacl >/dev/null; then sudo -n setfacl -m "u:$(id -u):rw" /dev/kvm
  else sudo -n chgrp "$(id -gn)" /dev/kvm; sudo -n chmod g+rw /dev/kvm; fi
fi
[[ -r /dev/kvm && -w /dev/kvm ]]
image='system-images;android-36;google_apis;x86_64'
packages=()
[[ -x $ADB ]] || packages+=(platform-tools)
[[ -x $emulator ]] || packages+=(emulator)
[[ -f $sdk/platforms/android-36/android.jar ]] || packages+=('platforms;android-36')
[[ -x $sdk/build-tools/35.0.0/aapt ]] || packages+=('build-tools;35.0.0')
[[ -f $sdk/system-images/android-36/google_apis/x86_64/package.xml ]] || packages+=("$image")
if (( ${#packages[@]} )); then timeout 320s "$mgr" --sdk_root="$sdk" --install "${packages[@]}"; fi
printf 'no\n' | timeout 45s "$(dirname "$mgr")/avdmanager" create avd -n vexo_journey_only -k "$image"
[[ -z $("$ADB" devices | awk 'NR>1 && NF {print $1}') ]]
"$emulator" -avd vexo_journey_only -port 5554 -accel on -gpu swiftshader -no-window -no-audio -no-boot-anim -no-snapshot -wipe-data >"$work/emulator.log" 2>&1 &
emu_pid=$!
curl --fail --location --silent --show-error --max-time 180 'https://downloads.gradle.org/distributions/gradle-8.11.1-bin.zip' -o "$work/gradle.zip"
printf 'f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6  %s\n' "$work/gradle.zip" | sha256sum --strict --check --status
unzip -q "$work/gradle.zip" -d "$work"
gradle="$work/gradle-8.11.1/bin/gradle"
# Both debug artifacts use the same disposable runner debug key. Neither becomes a release.
"$gradle" --project-dir "$work/src/aurora" --no-daemon --console=plain --max-workers=2 :app:assembleDebug
boot=0
for n in {1..36}; do
  kill -0 "$emu_pid" || { tail -25 "$work/emulator.log"; exit 1; }
  boot=$(timeout 8s "$ADB" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r') || boot=0
  [[ $boot == 1 ]] && break
  sleep 2
done
[[ $boot == 1 ]]
[[ $("$ADB" -s "$serial" shell getprop ro.build.version.sdk | tr -d '\r') == 36 ]]
"$ADB" -s "$serial" shell wm dismiss-keyguard
"$ADB" -s "$serial" shell cmd connectivity airplane-mode enable
"$ADB" -s "$serial" shell svc wifi disable
mapfile -t next < <(find "$work/src/aurora/app/build/outputs/apk/debug" -maxdepth 1 -name '*.apk')
[[ ${#next[@]} == 1 ]]
timeout 150s node qa/r19/android-webview-smoke.cjs --privacy-only "${next[0]}"
