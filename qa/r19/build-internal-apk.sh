#!/usr/bin/env bash
set -euo pipefail
umask 077
export LC_ALL=C
[[ ${GITHUB_REPOSITORY:-} == wayluloli-beep/vexo-mlkit-lab && ${GITHUB_REF:-} == refs/heads/vexo-r19-apk-download ]]
[[ $(git rev-parse HEAD) == "$GITHUB_SHA" ]]
unset APK_KEYSTORE_FILE APK_STORE_PASSWORD APK_KEY_ALIAS APK_KEY_PASSWORD GITHUB_RUN_NUMBER
export JAVA_HOME="${JAVA_HOME_17_X64:?}"
export PATH="$JAVA_HOME/bin:$PATH"
sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[[ -n $sdk ]]
mgr="$sdk/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x $mgr ]]; then
  mgr=$(find "$sdk/cmdline-tools" -type f -path '*/bin/sdkmanager' | sort -V | tail -1)
fi
[[ -x $mgr ]]
bt="$sdk/build-tools/35.0.0"
work=$(mktemp -d "$RUNNER_TEMP/vexo-internal.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
bash qa/r19/materialize.sh "$work"
source_tree="$work/src/aurora"
python3 qa/r19/isolate-native.py "$source_tree"
python3 - "$source_tree" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
def replace(path, old, new):
    p = source / path
    data = p.read_bytes()
    assert data.count(old.encode()) == 1, (path, old)
    p.write_bytes(data.replace(old.encode(), new.encode(), 1))

# One-off test package. This is the only difference in app configuration from R19.
replace("app/build.gradle.kts", 'applicationId = "com.trackingracing"', 'applicationId = "com.trackingracing.vexobeta.r19"')
replace("app/build.gradle.kts", 'versionName = "0.1.3-r19-interno"', 'versionName = "0.1.3-r19-teste"')
replace("app/src/main/AndroidManifest.xml", 'android:label="Vexo Aurora"', 'android:label="Vexo Beta"')
PY
packages=()
[[ -f $sdk/platforms/android-36/android.jar ]] || packages+=('platforms;android-36')
[[ -x $bt/aapt && -x $bt/apksigner && -x $bt/zipalign ]] || packages+=('build-tools;35.0.0')
if (( ${#packages[@]} )); then timeout 300s "$mgr" --sdk_root="$sdk" --install "${packages[@]}"; fi
export GRADLE_USER_HOME="$work/gradle-home"
curl --fail --location --silent --show-error --max-time 180 'https://downloads.gradle.org/distributions/gradle-8.11.1-bin.zip' -o "$work/gradle.zip"
printf 'f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6  %s\n' "$work/gradle.zip" | sha256sum --strict --check --status
unzip -q "$work/gradle.zip" -d "$work"
"$work/gradle-8.11.1/bin/gradle" --project-dir "$source_tree" --no-daemon --console=plain --max-workers=2 :app:assembleRelease
mapfile -t unsigned < <(find "$source_tree/app/build/outputs/apk/release" -maxdepth 1 -name '*unsigned.apk')
[[ ${#unsigned[@]} == 1 ]]
out="$RUNNER_TEMP/vexo-test-delivery"
mkdir "$out"
out_apk="$out/Vexo-R19-teste.apk"
export VEXO_INTERNAL_KEY_PASS
VEXO_INTERNAL_KEY_PASS=$(openssl rand -hex 20)
keytool -genkeypair -noprompt -storetype PKCS12 -keyalg RSA -keysize 2048 -validity 3650 -dname 'CN=Vexo R19 Private Test' -alias vexotest -keystore "$work/test.p12" -storepass:env VEXO_INTERNAL_KEY_PASS > "$work/signer.log" 2>&1
"$bt/zipalign" -P 16 -f 4 "${unsigned[0]}" "$work/aligned.apk"
"$bt/apksigner" sign --ks "$work/test.p12" --ks-key-alias vexotest --ks-pass env:VEXO_INTERNAL_KEY_PASS --out "$out_apk" "$work/aligned.apk"
unset VEXO_INTERNAL_KEY_PASS
rm -f -- "$work/test.p12"
"$bt/apksigner" verify --verbose --print-certs "$out_apk" >"$work/verification"
"$bt/zipalign" -c -P 16 4 "$out_apk"
grep -Eq 'Verified using v[23] scheme .*: true' "$work/verification"
"$bt/aapt" dump badging "$out_apk" >"$work/badging"
"$bt/aapt" dump permissions "$out_apk" >"$work/permissions"
grep -Fq "package: name='com.trackingracing.vexobeta.r19' versionCode='6' versionName='0.1.3-r19-teste'" "$work/badging"
grep -Fq "application-label:'Vexo Beta'" "$work/badging"
grep -Fq "launchable-activity: name='com.trackingracing.AuroraActivity'" "$work/badging"
grep -Fq "sdkVersion:'26'" "$work/badging"
grep -Fq "targetSdkVersion:'36'" "$work/badging"
! grep -Fq 'application-debuggable' "$work/badging" || exit 1
! grep -Eq 'FOREGROUND_SERVICE|LOCATION|BLUETOOTH|SYSTEM_ALERT_WINDOW|POST_NOTIFICATIONS' "$work/permissions" || exit 1
python3 - "$out_apk" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import re, sys
with ZipFile(Path(sys.argv[1])) as apk:
    names = apk.namelist()
    dex = [apk.read(p) for p in names if re.fullmatch(r"classes\d*\.dex", p)]
    assert dex and any(b"Lcom/trackingracing/AuroraActivity;" in item for item in dex)
    for marker in (b"Lcom/trackingracing/ScreenCaptureService;", b"Lcom/google/mlkit/", b"Lcom/trackingracing/SincronizadorPlanilha;"):
        assert not any(marker in item for item in dex)
    assert not any("simulador99" in p or "lab99" in p for p in names)
    assert {"assets/aurora/central.html", "assets/aurora/turno-storage.js", "assets/aurora/privacy-values.js"} <= set(names)
print("VEXO_APK: package, signature, offline manual modules and release metadata checked")
PY
(cd "$out" && sha256sum Vexo-R19-teste.apk)
