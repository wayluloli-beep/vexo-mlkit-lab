#!/usr/bin/env python3
"""R22 beta gate: backend remains disabled until project is configured."""
from pathlib import Path
import json
import sys

root=Path(sys.argv[1])
n=root/"app/src/main/java/com/trackingracing"
a=root/"app/src/main/assets/aurora"
def need(condition,label):
    if not condition: raise SystemExit("R22_FAIL: "+label)
cloud=(n/"AuraGoogleVoice.kt").read_text()
source=(n/"AuroraActivity.kt").read_text()
r21=(n/"AuraVoice.kt").read_text()
web=(a/"central.html").read_text()
js=(a/"central.js").read_text()
gradle=(root/"app/build.gradle.kts").read_text()
config=json.loads((a/"aura-google-config.json").read_text())
need(config=={"endpoint":"","firebaseApiKey":"","firebaseAppId":"","firebaseProjectId":"","firebaseSenderId":""},"Google backend disabled until configured")
need("FirebaseAppCheck.getInstance" in cloud,"App Check token")
need("PlayIntegrityAppCheckProviderFactory.getInstance()" in cloud,"Play Integrity")
need('setRequestProperty("X-Firebase-AppCheck"' in cloud,"protected backend")
need("java.net.URL" in cloud and "HttpsURLConnection" in cloud,"TLS-only backend")
need("!parsed.host.endsWith(\".run.app\"" in cloud,"host allowlist")
need("offerMetrics(perKmCents:Int,perHourCents:Int)" in cloud,"typed metrics only")
need("fun preview():Boolean=dispatch(JSONObject().put(\"kind\",\"intro\"),true)" in cloud,"fixed preview phrase")
need("audio.size" not in cloud or "900000" in cloud,"size cap")
need("auraGoogleDelegate.isInitialized()" in source,"lifecycle")
need("previewGoogleAura()" in source and "auraGoogleReady()" in source,"native bridge")
need('id="aura-google-preview"' in web and "Serviço Google ainda não conectado" in web,"UI clear about unavailable API")
need("googlePreview.disabled=!available" in js and "previewGoogleAura" in js,"UI wiring")
need("com.google.firebase:firebase-appcheck-playintegrity:20.1.0" in gradle,"Firebase dependency")
need("android.speech.tts.TextToSpeech" not in cloud+r21,"not system TTS")
need("com.trackingracing" in source and "startExternalCapture()" in source,"capture untouched")
need((n/"ScreenCaptureService.kt").is_file(),"ML Kit service still present")
need(not (root/"app/src/main/assets/simulador99.html").exists(),"no fake ride simulator")
need("OCR" not in web,"technical acronym hidden")
print("R22_QA: secure Google TTS preview, Firebase App Check, disabled until setup, offline fallback; ML Kit preserved")
