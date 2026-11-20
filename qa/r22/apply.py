#!/usr/bin/env python3
"""Add optional Google Cloud TTS preview without touching OCR or R21 offline audio."""
from pathlib import Path
import shutil,sys

root=Path(sys.argv[1]).resolve()
p=Path(__file__).resolve().parent
assets=root/"app/src/main/assets/aurora"
main=root/"app/src/main/java/com/trackingracing"

def one(raw,old,new,label):
    n=raw.count(old)
    if n!=1:raise SystemExit(f"R22 expected one {label}, found {n}")
    return raw.replace(old,new,1)

shutil.copy2(p/"AuraGoogleVoice.kt",main/"AuraGoogleVoice.kt")
shutil.copy2(p/"aura-google-config.json",assets/"aura-google-config.json")

gfile=root/"app/build.gradle.kts"
gradle=gfile.read_text()
gradle=one(gradle,'    // Neural speech is pre-generated and bundled as audio assets.',
'''    // Neural speech is pre-generated and bundled as audio assets.
    implementation("com.google.firebase:firebase-appcheck-playintegrity:20.1.0")''',"Firebase App Check")
gradle=one(gradle,'versionName = "0.1.3-r21-aura-voice"',
           'versionName = "0.1.3-r22-aura-google"',"version name")
gfile.write_text(gradle)

activity=main/"AuroraActivity.kt"
s=activity.read_text()
s=one(s,"    private val auraVoice by auraVoiceDelegate",
'''    private val auraVoice by auraVoiceDelegate
    private val auraGoogleDelegate = lazy { AuraGoogleVoice(this, auraVoice) }
    private val auraGoogle by auraGoogleDelegate''',"cloud voice field")
s=one(s,"        if (auraVoiceDelegate.isInitialized()) auraVoice.close()",
'''        if (auraGoogleDelegate.isInitialized()) auraGoogle.close()
        if (auraVoiceDelegate.isInitialized()) auraVoice.close()''',"cloud shutdown")
s=one(s,"        @JavascriptInterface fun previewAura(): Boolean = auraVoice.preview()",
'''        @JavascriptInterface fun previewAura(): Boolean = auraVoice.preview()
        @JavascriptInterface fun auraGoogleReady(): Boolean = auraGoogle.isConfigured()
        @JavascriptInterface fun previewGoogleAura(): Boolean = auraGoogle.preview()''',"cloud bridge")
activity.write_text(s)

html=assets/"central.html"
h=html.read_text()
h=one(h,'<p id="aura-voice-status" role="status" aria-live="polite"></p>',
'''<p id="aura-voice-status" role="status" aria-live="polite"></p>
<div id="aura-google-settings">
  <h3>Voz Google HD</h3>
  <p>Precisa de internet. Se não funcionar, a Aura continua com a voz offline.</p>
  <button id="aura-google-preview" class="outline" type="button" disabled>Ouvir voz Google</button>
  <p id="aura-google-status" role="status" aria-live="polite">Serviço Google ainda não conectado.</p>
</div>''',"Google preview in Settings")
html.write_text(h)

js=assets/"central.js"
j=js.read_text()
j=one(j,"  show(active, false);\n",
'''  const googlePreview=byId("aura-google-preview"),googleStatus=byId("aura-google-status");
  if (googlePreview && googleStatus) {
    let available=false;
    try { available=bridge?.auraGoogleReady?.() === true; } catch (_) {}
    googlePreview.disabled=!available;
    googleStatus.textContent=available
      ?"Voz Google HD disponível pela internet.":"Serviço Google ainda não conectado. A voz offline continua disponível.";
    googlePreview.addEventListener("click",()=>{
      let queued=false;
      try { queued=bridge?.previewGoogleAura?.() === true; } catch (_) {}
      googleStatus.textContent=queued
        ?"Consultando a voz Google HD. Se ela falhar, a Aura usa a voz offline."
        :"Voz Google não disponível. Use Ouvir Aura.";
    });
  }
  show(active, false);
''',"Google preview JS")
js.write_text(j)
print("R22_GOOGLE_TTS: Firebase App Check + Cloud Run client + offline fallback; safe disabled default")
