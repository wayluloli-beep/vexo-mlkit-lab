#!/usr/bin/env python3
from pathlib import Path
import json, sys
root=Path(sys.argv[1])
p=root/"app/src/main/assets/aurora"
native=root/"app/src/main/java/com/trackingracing"
def ck(x,message):
    if not x: raise SystemExit("AURA_R21_QA_FAIL: "+message)
a=(native/"AuroraActivity.kt").read_text()
voice=(native/"AuraVoice.kt").read_text()
page=(p/"central.html").read_text()
js=(p/"central.js").read_text()
data=json.loads((p/"aura-phrases.json").read_text())
ck(len(data)==20,"exactly 20 user lines")
ck("E aí, motora." in data["hello"],"first voice line")
ck("Copiloto ativa." in data["aura_ativa"],"activation line")
ck("com.google.mediapipe:tasks-audio:1.1.1" in (root/"app/build.gradle.kts").read_text(),"MediaPipe pin")
ck("TextToSpeech.create" in voice and "pf_dora" in voice,"neural voice")
ck("android.speech.tts.TextToSpeech" not in voice,"system voice disallowed")
ck("https://" not in voice and "http://" not in voice,"neural speech no cloud API")
ck('private val auraVoice by auraVoiceDelegate' in a and "previewAura()" in a,"bridge")
ck("auraVoiceEnabled()" in a and "speakAuraCue(" in a,"voice settings and events bridge")
ck('id="aura-voice-preview"' in page and 'id="aura-voice-enabled"' in page,"UX preview")
ck("Aura Sync" in page and "OCR" not in page,"product name in screens")
ck("voicePreview.addEventListener" in js,"UI preview wiring")
ck("data-action=\"externo\"" in page and "startExternalCapture()" in a,"real reader still intact")
ck(not (root/"app/src/main/assets/simulador99.html").exists(),"no 99 simulator in driver app")
ck((native/"ScreenCaptureService.kt").is_file(),"capture service not removed")
ck("noCompress += listOf(\"mp4\", \"litertlm\")" in (root/"app/build.gradle.kts").read_text(),"model compression")
print("AURA_R21: 20 lines, neural voice code, Aura controls, external capture preserved")
