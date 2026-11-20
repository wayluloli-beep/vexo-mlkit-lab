#!/usr/bin/env bash
set -euo pipefail
umask 077
export LC_ALL=C
[[ "$GITHUB_REPOSITORY" == "wayluloli-beep/vexo-mlkit-lab" ]]
[[ "$GITHUB_REF" == "refs/heads/vexo-r20-ocr-full" ]]
[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]
unset APK_KEYSTORE_FILE APK_STORE_PASSWORD APK_KEY_ALIAS APK_KEY_PASSWORD GITHUB_RUN_NUMBER
export JAVA_HOME="$JAVA_HOME_17_X64"
export PATH="$JAVA_HOME/bin:$PATH"
sdk="$ANDROID_HOME"
mgr="$sdk/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x "$mgr" ]]; then mgr=$(find "$sdk/cmdline-tools" -type f -path '*/bin/sdkmanager' | sort -V | tail -1); fi
[[ -x "$mgr" ]]
bt="$sdk/build-tools/35.0.0"
work=$(mktemp -d "$RUNNER_TEMP/vexo-r20.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
bash qa/r19/materialize.sh "$work"
src="$work/src/aurora"
python3 qa/r20/upgrade.py "$src"
python3 qa/r20/vx_icon.py "$src"
python3 qa/r20/check.py "$src"
for js in "$src/app/src/main/assets/aurora/"*.js; do node --check "$js"; done
python3 - "$src" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/"app/build.gradle.kts"
s=p.read_text()
old='applicationId = "com.trackingracing"'
assert s.count(old)==1
p.write_text(s.replace(old,'applicationId = "com.trackingracing.vexobeta.r20"',1))
PY
[[ -f "$sdk/platforms/android-35/android.jar" ]] || timeout 300s "$mgr" --sdk_root="$sdk" --install 'platforms;android-35'
[[ -x "$bt/aapt" && -x "$bt/apksigner" && -x "$bt/zipalign" ]] || timeout 300s "$mgr" --sdk_root="$sdk" --install 'build-tools;35.0.0'
export GRADLE_USER_HOME="$work/gradle-home"
curl --fail --location --silent --show-error --max-time 180 'https://downloads.gradle.org/distributions/gradle-8.11.1-bin.zip' -o "$work/gradle.zip"
printf 'f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6  %s\n' "$work/gradle.zip" | sha256sum --strict --check --status
unzip -q "$work/gradle.zip" -d "$work"
"$work/gradle-8.11.1/bin/gradle" --project-dir "$src" --no-daemon --console=plain --max-workers=2 :app:testDebugUnitTest :app:assembleRelease
unsigned=$(find "$src/app/build/outputs/apk/release" -maxdepth 1 -name '*unsigned.apk' -print -quit)
[[ -n "$unsigned" ]]
out="$RUNNER_TEMP/vexo-test-delivery"
mkdir -p "$out"
apk="$out/Vexo-R20-teste.apk"
export VEXO_INTERNAL_KEY_PASS
VEXO_INTERNAL_KEY_PASS=$(openssl rand -hex 20)
keytool -genkeypair -noprompt -storetype PKCS12 -keyalg RSA -keysize 2048 -validity 3650 -dname 'CN=Vexo R20 Private Test' -alias vexotest -keystore "$work/test.p12" -storepass:env VEXO_INTERNAL_KEY_PASS > "$work/signer.log" 2>&1
"$bt/zipalign" -P 16 -f 4 "$unsigned" "$work/aligned.apk"
"$bt/apksigner" sign --ks "$work/test.p12" --ks-key-alias vexotest --ks-pass env:VEXO_INTERNAL_KEY_PASS --out "$apk" "$work/aligned.apk"
unset VEXO_INTERNAL_KEY_PASS
rm -f "$work/test.p12"
"$bt/apksigner" verify --verbose --print-certs "$apk" > "$work/verification"
"$bt/zipalign" -c -P 16 4 "$apk"
grep -Eq 'Verified using v[23] scheme .*: true' "$work/verification"
"$bt/aapt" dump badging "$apk" > "$work/badging"
"$bt/aapt" dump permissions "$apk" > "$work/permissions"
grep -Fq "package: name='com.trackingracing.vexobeta.r20'" "$work/badging"
grep -Fq "application-label:'Vexo R20'" "$work/badging"
grep -Fq 'android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION' "$work/permissions"
grep -Fq 'android.permission.SYSTEM_ALERT_WINDOW' "$work/permissions"
python3 qa/r20/check_apk.py "$apk"
(cd "$out" && sha256sum Vexo-R20-teste.apk)
