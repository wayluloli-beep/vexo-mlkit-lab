#!/usr/bin/env python3
"""R21 opt-in on-device voice, preserving R20 OCR engine and financial data."""
from pathlib import Path
import sys, shutil

root=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
assets=root/"app/src/main/assets/aurora"
main=root/"app/src/main/java/com/trackingracing"
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"AURA_R21: expected 1 {label}, got {n}")
    return s.replace(a,b,1)
shutil.copy2(here/"AuraVoice.kt",main/"AuraVoice.kt")
shutil.copy2(here/"aura-phrases.json",assets/"aura-phrases.json")

gradle=root/"app/build.gradle.kts"
g=gradle.read_text()
g=one(g,'    implementation("com.google.mlkit:text-recognition:16.0.1")',
'''    implementation("com.google.mlkit:text-recognition:16.0.1")
    // Neural speech is pre-generated and bundled as audio assets.''',"TTS dependency")
g=one(g,'androidResources { noCompress += "mp4" }',
'''androidResources { noCompress += listOf("mp4", "ogg") }''',"uncompressed neural voice model")
g=one(g,'versionName = "0.1.3-r20-ocr-full"','versionName = "0.1.3-r21-aura-voice"',"version")
gradle.write_text(g)

kotlin=main/"AuroraActivity.kt"
k=kotlin.read_text()
k=one(k,'    private val ui = Handler(Looper.getMainLooper())',
'''    private val auraVoiceDelegate = lazy { AuraVoice(this) }
    private val auraVoice by auraVoiceDelegate
    private val ui = Handler(Looper.getMainLooper())''',"voice service field")
k=one(k,'        web.destroy()\n        if (recognizerDelegate.isInitialized()) recognizer.close()',
'''        web.destroy()
        if (auraVoiceDelegate.isInitialized()) auraVoice.close()
        if (recognizerDelegate.isInitialized()) recognizer.close()''',"voice resource shutdown")
k=one(k,'    private inner class Bridge {\n','''    private inner class Bridge {
        @JavascriptInterface fun previewAura(): Boolean = auraVoice.preview()
        @JavascriptInterface fun auraVoiceEnabled(): Boolean = auraVoice.enabled()
        @JavascriptInterface fun setAuraVoiceEnabled(enabled: Boolean): Boolean = auraVoice.setEnabled(enabled)
        @JavascriptInterface fun speakAuraCue(id: String): Boolean = auraVoice.cue(id)
''',"voice bridge")
kotlin.write_text(k)

html=assets/"central.html"
h=html.read_text()
repl={
"Somente leituras reais do OCR. Nenhuma corrida fictícia é criada aqui.":
    "Somente solicitações realmente visualizadas pela Aura Sync. Nenhuma corrida fictícia é criada aqui.",
"Exportar leituras do OCR":"Exportar leituras da Aura",
"Iniciar ou encerrar OCR externo":"Ativar ou encerrar Aura Sync",
"OCR em outros apps":"Aura Sync",
"Vexo · controle de ganhos e OCR no aparelho.":"Vexo · sua copiloto inteligente Aura Sync e seu controle de ganhos.",
"Teste interno com OCR":"Teste interno com Aura Sync",
"O OCR externo depende da permissão do Android.":"A leitura da Aura Sync depende de autorização de captura da tela pelo Android."
}
for a,b in repl.items():
    if a not in h: raise SystemExit("missing R20 HTML marker: "+a)
    h=h.replace(a,b)
setting='''<section id="aura-voice-settings" aria-labelledby="aura-voice-title">
<h2 id="aura-voice-title">Voz da Aura</h2>
<p class="detail">Voz neural feminina em português brasileiro. Funciona no próprio aparelho, sem usar a voz padrão do Android. Os áudios vêm junto com o aplicativo e funcionam sem internet.</p>
<label for="aura-voice-enabled"><input type="checkbox" id="aura-voice-enabled"> Permitir avisos falados da Aura</label>
<button type="button" id="aura-voice-preview" class="outline">Ouvir Aura</button>
<p id="aura-voice-status" role="status" aria-live="polite"></p>
</section>
'''
marker='<section id="ajuda" hidden aria-labelledby="h-ajuda">'
h=one(h,"</section>\n"+marker,setting+"</section>\n"+marker,"voice settings inside Configurações")
# User-visible copy only, not internal code symbols/diagnostics.
if 'OCR' in h:
    raise SystemExit("R21 has technical OCR labels visible in central.html")
html.write_text(h)

js=assets/"central.js"
j=js.read_text()
j=one(j,'"Recurso disponível somente no app Android com OCR."',
        '"A Aura Sync está disponível no aplicativo Android."',"visible technical term in warning")
j=one(j,'"Não foi possível executar o OCR. Verifique as permissões do Android."',
        '"A Aura Sync não conseguiu iniciar. Confira a permissão de tela no Android."',"visible OCR error")
j=one(j,'  show(active, false);\n',
'''  const voicePreview=byId("aura-voice-preview"),voiceEnabled=byId("aura-voice-enabled"),voiceStatus=byId("aura-voice-status");
  if (voicePreview && voiceEnabled && voiceStatus) {
    try { voiceEnabled.checked=bridge?.auraVoiceEnabled?.() === true; } catch (_) {}
    voiceEnabled.addEventListener("change",()=>{
      let ok=false;
      try { ok=bridge?.setAuraVoiceEnabled?.(voiceEnabled.checked) === true; } catch (_) {}
      if(!ok) {
        voiceEnabled.checked=!voiceEnabled.checked;
        voiceStatus.textContent="Não foi possível salvar sua escolha.";
      } else {
        voiceStatus.textContent=voiceEnabled.checked?"Avisos por voz ativados.":"Avisos por voz desligados.";
      }
    });
    voicePreview.addEventListener("click",()=>{
      let queued=false;
      try { queued=bridge?.previewAura?.() === true; } catch (_) {}
      voiceStatus.textContent=queued
        ?"Preparando a voz neural da Aura no próprio aparelho. Na primeira vez, isso pode demorar."
        :"Não foi possível iniciar a voz da Aura neste aparelho.";
    });
  }
  show(active, false);
''',"voice settings JS")
js.write_text(j)
print("AURA_R21: Kotlin neural speech, 20 cues, UI activation, privacy opt-in; OCR unchanged")
