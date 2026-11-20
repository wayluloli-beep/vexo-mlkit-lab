#!/usr/bin/env python3
"""R20: remove the on-screen 99 simulator, NOT the OCR engine.
Build the complete R19 product plus native OCR/overlay and an empty daytime home.
"""
from pathlib import Path
import re
import sys

root=Path(sys.argv[1]).resolve()
assets=root/"app/src/main/assets/aurora"
native=root/"app/src/main/java/com/trackingracing/AuroraActivity.kt"

def put(path, value):
    path.write_text(value,encoding="utf-8")

def one(raw, old, new, name):
    count=raw.count(old)
    if count!=1:
        raise SystemExit(f"R20 expected one {name}, saw {count}")
    return raw.replace(old,new,1)

# R19 materialization still contains the ML Kit/MediaProjection Kotlin sources.
# Do not run qa/r19/isolate-native.py: it deletes all OCR services.
manifest=root/"app/src/main/AndroidManifest.xml"
m=manifest.read_text()
m=one(m,'    <uses-permission android:name="android.permission.INTERNET" />',
'''    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />
    <uses-permission android:name="android.permission.INTERNET" />''',"OCR permissions")
m=one(m,'    </application>',
'''        <service
            android:name=".ScreenCaptureService"
            android:exported="false"
            android:foregroundServiceType="mediaProjection" />
    </application>''',"capture service declaration")
put(manifest,m)

kt=native.read_text()
kt=one(kt,'import android.util.Log\n','import android.util.Log\nimport android.util.AtomicFile\n',"AtomicFile import")
kt=one(kt,'import java.io.File\n','import java.io.File\nimport java.io.FileNotFoundException\nimport java.io.IOException\n',"IO imports")
kt=one(kt,'    private val ui = Handler(Looper.getMainLooper())',
'''    private val turnLock = Any()
    private val turnFile by lazy { AtomicFile(File(noBackupFilesDir, "turno-manual.v1.json")) }
    private val ui = Handler(Looper.getMainLooper())''',"persistent manual store")
kt=one(kt,'        // Manual edition: do not start the capture scheduler or load the model.',
'''        warmLocalRecognizer()
        ui.post(tick)''',"restore local OCR scheduler")
kt=one(kt,'@JavascriptInterface fun startExternal() { /* Capture is not available in this manual edition. */ }',
'''@JavascriptInterface fun startExternal() { ui.post { if (visible) startExternalCapture() } }''',"restore real external OCR")
inject=r'''
        private fun privacyPrefs() = getSharedPreferences("vexo.privacy-values.v1", MODE_PRIVATE)

        @JavascriptInterface fun readPrivacyPrefs(): String? = runCatching {
            privacyPrefs().getString("saved", "") ?: ""
        }.getOrNull()

        @JavascriptInterface fun writePrivacyPrefs(manual: Boolean, auto: Boolean): Boolean =
            privacyPrefs().edit().putString("saved", """{"manual":$manual,"auto":$auto}""").commit()

        @JavascriptInterface fun readManualTurn(): String? = synchronized(turnLock) {
            try {
                turnFile.readFully().toString(Charsets.UTF_8)
            } catch (_: FileNotFoundException) {
                if (turnFile.baseFile.exists()) null else ""
            } catch (_: IOException) {
                null
            }
        }

        @JavascriptInterface fun writeManualTurn(raw: String): Boolean = synchronized(turnLock) {
            if (raw.isEmpty() || raw.length > 500_000) return@synchronized false
            val bytes = raw.toByteArray(Charsets.UTF_8)
            val output = try { turnFile.startWrite() } catch (_: IOException) {
                return@synchronized false
            }
            try {
                output.write(bytes)
                output.fd.sync()
                turnFile.finishWrite(output)
                turnFile.readFully().contentEquals(bytes)
            } catch (_: IOException) {
                turnFile.failWrite(output)
                false
            }
        }

        @JavascriptInterface fun appVersion(): String = BuildConfig.VERSION_NAME

'''
kt=one(kt,'    private inner class Bridge {\n','    private inner class Bridge {\n'+inject,"keep R19 finance and privacy bridge")
put(native,kt)

gradle=root/"app/build.gradle.kts"
g=gradle.read_text()
g=one(g,'versionName = "0.1.3-r18-interno"','versionName = "0.1.3-r20-ocr-full"',"version")
put(gradle,g)

html=assets/"central.html"
h=html.read_text()
h=one(h,'<link rel="stylesheet" href="privacy-values.css">','<link rel="stylesheet" href="privacy-values.css"><link rel="stylesheet" href="r20-drawer.css">',"drawer CSS")
h=one(h,'<script defer src="feedback.js"></script>','<script defer src="feedback.js"></script><script defer src="r20-drawer.js"></script>',"drawer JS")
head_start=h.index('<header>')
head_end=h.index('</header>',head_start)+len('</header>')
header='''<header class="vexo-topbar">
  <button id="vexo-menu-open" class="vexo-menu-trigger" type="button" aria-label="Abrir menu" aria-controls="vexo-drawer" aria-expanded="false">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
  </button>
  <span class="vexo-topbar-brand"><strong>VX</strong><span>Vexo</span></span>
  <span class="vexo-topbar-end" aria-hidden="true"></span>
</header>'''
h=h[:head_start]+header+h[head_end:]
h=one(h,'<section id="inicio" aria-labelledby="h-inicio"><h1 id="h-inicio" tabindex="-1">Painel do motorista</h1>',
'''<section id="inicio" class="vexo-empty-home" aria-labelledby="h-inicio">
  <h1 id="h-inicio" class="vexo-screenreader-only" tabindex="-1">Início</h1>
</section>
<section id="ganhos" aria-labelledby="h-ganhos"><h1 id="h-ganhos" tabindex="-1">Ganhos</h1>''',"blank home, move existing turn UI to Ganhos")
h=one(h,'<section id="veiculo" hidden aria-labelledby="h-veiculo">',
'''<section id="solicitacoes" hidden aria-labelledby="h-solicitacoes">
  <h1 id="h-solicitacoes" tabindex="-1">Solicitações visualizadas</h1>
  <p>Somente leituras reais do OCR. Nenhuma corrida fictícia é criada aqui.</p>
  <button class="outline" type="button" data-action="exportOcr">Exportar leituras do OCR</button>
  <button class="outline" type="button" data-action="externo">Iniciar ou encerrar OCR externo</button>
</section>
<section id="folha" hidden aria-labelledby="h-folha">
  <h1 id="h-folha" tabindex="-1">Folha de ponto</h1>
  <p>Histórico de turnos registrados por você.</p>
  <div id="vexo-folha-history"></div>
</section>
<section id="veiculo" hidden aria-labelledby="h-veiculo">''',"existing financial and new pages")
# A visible navigation bar would violate the requested blank home. Replace it with a side drawer.
h,count=re.subn(r'<nav aria-label="Navegação principal">.*?</nav>', '',h, count=1,flags=re.S)
if count!=1: raise SystemExit("bottom navigation mismatch")
h=one(h,'</main>\n','</main>\n',"main marker")
paths={
"ganhos":('Ganhos','<circle cx="12" cy="12" r="9"/><path d="M15 8c-2-2-6-1-6 1 0 3 6 1 6 5 0 3-6 4-7 1M12 5v14"/>'),
"solicitacoes":('Solicitações visualizadas','<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>'),
"veiculo":('Meu veículo','<path d="M5 16H3v-5l2-5h14l2 5v5h-2M5 16h14M5 16a2 2 0 1 0 4 0M15 16a2 2 0 1 0 4 0M3 11h18"/>'),
"folha":('Folha de ponto','<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>'),
"config":('Configurações','<circle cx="12" cy="12" r="3"/><path d="M10 2h4l1 3 2 1 3-1 2 4-2 2v2l2 2-2 4-3-1-2 1-1 3h-4l-1-3-2-1-3 1-2-4 2-2v-2L2 9l2-4 3 1 2-1z"/>'),
"plano":('Meu plano de ganhos','<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 3v3M21 12h-3"/>'),
"externo":('OCR em outros apps','<path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3M21 16v3a2 2 0 0 1-2 2h-3"/><circle cx="12" cy="12" r="3"/>'),
"ajuda":('Ajuda','<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3M12 17h.01"/>'),
"sobre":('Informações','<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>')
}
buttons=[]
for key,(label,icon) in paths.items():
    attr='data-action' if key in ('plano','externo') else 'data-page'
    buttons.append(f'<button type="button" class="vexo-drawer-link" {attr}="{key}">'
                   f'<svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg><span>{label}</span>'
                   '<span class="vexo-chevron" aria-hidden="true">›</span></button>')
drawer='''<div id="vexo-menu-shade" class="vexo-menu-shade" hidden></div>
<aside id="vexo-drawer" class="vexo-drawer" aria-label="Menu do Vexo" aria-hidden="true" hidden>
  <div class="vexo-menu-top">
    <button id="vexo-menu-close" type="button" aria-label="Fechar menu" class="vexo-menu-back">‹</button>
  </div>
  <div class="vexo-menu-profile">
    <span class="vexo-avatar" aria-hidden="true"><svg viewBox="0 0 64 64"><circle cx="32" cy="23" r="12"/><path d="M10 59c0-15 10-23 22-23s22 8 22 23"/></svg></span>
    <strong>Motorista</strong>
  </div>
  <nav class="vexo-drawer-links" aria-label="Áreas do Vexo">
'''+'\n'.join(buttons)+'''
  </nav>
</aside>'''
h=one(h,'</div></body></html>','</div>\n'+drawer+'</body></html>',"side drawer mount")
h=one(h,'Vexo Aurora · turno manual e plano de ganhos.', 'Vexo · controle de ganhos e OCR no aparelho.',"about app")
h=one(h,'Teste interno manual', 'Teste interno com OCR', "edition")
h=one(h,'Esta edição não usa localização nem conexão OBD2.', 'GPS e OBD2 ainda não estão ativos nesta edição. O OCR externo depende da permissão do Android.', "transparency")
put(html,h)

js=assets/"central.js"
j=js.read_text()
j=one(j,'const pages = ["inicio", "config", "ajuda", "sobre", "veiculo"];',
'''const pages = ["inicio", "ganhos", "solicitacoes", "folha", "veiculo", "config", "ajuda", "sobre"];''',"new pages")
j=one(j,'    active = page;\n','''    active = page;
    document.body.classList.toggle("vexo-home",page === "inicio");''',"home theme")
j=one(j,'    if (page === "inicio" || page === "config") refresh();','    if (page === "ganhos" || page === "config") refresh();',"goal")
j=one(j,'    if (page === "inicio") window.VexoTurnoUI.refresh();',
'''    if (page === "ganhos" || page === "folha") window.VexoTurnoUI?.refresh?.();''',"turn refresh")
j=one(j,'    if (action === "plano") location.replace("./onboarding.html");',
'''    if (action === "plano") { location.replace("./onboarding.html"); return; }
    if (action === "externo" || action === "exportOcr") {
      const name = action === "externo" ? "startExternal" : "exportOcr";
      if (typeof bridge?.[name] !== "function") {
        message("Recurso disponível somente no app Android com OCR."); return;
      }
      try { bridge[name](); }
      catch (_) { message("Não foi possível executar o OCR. Verifique as permissões do Android."); }
    }''',"native OCR actions")
j=one(j,'    if (active === "inicio" && window.VexoTurnoUI.handleBack()) return;',
'''    if (window.VexoDrawer?.closeIfOpen?.()) return;
    if (active === "ganhos" && window.VexoTurnoUI?.handleBack?.()) return;''',"drawer Android back")
j=one(j,'  const garage=byId("veiculo-frame");',
'''  const panel=byId("turno-history-panel"), mount=byId("vexo-folha-history");
  if (panel && mount) mount.appendChild(panel);
  const garage=byId("veiculo-frame");''',"folha moves existing history")
put(js,j)

css=r'''/* Only the entry screen uses the requested light theme; other product modules keep their visuals. */
body.vexo-home{background:#f5f6f8;color:#15191d;min-height:100vh}
body.vexo-home .shell{background:#f5f6f8;min-height:100vh}
body.vexo-home main{padding:0 6vw;min-height:calc(100vh - 78px)}
body.vexo-home #inicio{min-height:calc(100vh - 100px)}
.vexo-screenreader-only{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.vexo-topbar{display:grid;grid-template-columns:56px 1fr 56px;align-items:center;gap:8px;min-height:72px;padding:8px 16px!important;color:#13161a;background:#f5f6f8;border-bottom:0}
.vexo-menu-trigger{display:grid;place-items:center;width:52px;height:52px;padding:12px;background:transparent;border:0;border-radius:12px;color:inherit}
.vexo-menu-trigger svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round}
.vexo-topbar-brand{justify-self:center;display:flex;align-items:baseline;gap:8px;font-size:20px;letter-spacing:-.04em}
.vexo-topbar-brand strong{color:#05a5bb;font-weight:850;font-size:22px}
.vexo-topbar-brand span{font-weight:700}
.vexo-topbar-end{width:52px}
.vexo-menu-shade{position:fixed;inset:0;z-index:2990;background:rgba(0,0,0,.42);opacity:0;transition:opacity .24s}
.vexo-menu-shade.is-open{opacity:1}
.vexo-drawer{position:fixed;left:0;top:0;bottom:0;z-index:3000;width:min(90vw,380px);overflow-y:auto;background:#f5f6f8;color:#15171a;transform:translateX(-103%);transition:transform .26s ease;box-shadow:14px 0 40px rgba(0,0,0,.15);overscroll-behavior:contain}
.vexo-drawer.is-open{transform:translateX(0)}
.vexo-menu-top{padding:50px 22px 0}
.vexo-menu-back{border:0;background:transparent;color:inherit;font-size:38px;font-weight:300;line-height:1;min-width:48px;min-height:48px;text-align:left}
.vexo-menu-profile{padding:26px 24px 34px;display:flex;align-items:center;gap:18px;font-size:25px}
.vexo-avatar{width:75px;height:75px;border-radius:50%;background:linear-gradient(145deg,#b8c7d8,#e0e7ed);display:grid;place-items:center;overflow:hidden}
.vexo-avatar svg{width:70px;height:70px;margin-top:12px;fill:#42566b;stroke:none}
.vexo-drawer-links{position:static;left:auto;right:auto;bottom:auto;background:transparent;border:0;padding:0 20px 32px;display:flex}
.vexo-drawer-link{display:flex;align-items:center;gap:20px;width:100%;min-height:75px;border:0;background:transparent;color:#17191d;text-align:left;padding:10px 7px;font-size:18px}
.vexo-drawer-link svg{width:27px;height:27px;min-width:27px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.vexo-drawer-link span:nth-child(2){flex:1}
.vexo-chevron{color:#68717c;font-size:31px;font-weight:300}
.vexo-drawer-link:active{background:#e8ebef}
body.vexo-drawer-open{overflow:hidden}
.vexo-menu-trigger:focus-visible,.vexo-menu-back:focus-visible,.vexo-drawer-link:focus-visible{outline:3px solid #008ba7;outline-offset:2px}
@media(prefers-reduced-motion:reduce){.vexo-menu-shade,.vexo-drawer{transition:none}}
@media(min-width:710px){body.vexo-home main{padding:0 32px}.vexo-topbar{padding:12px 32px!important}}
'''
put(assets/"r20-drawer.css",css)

drawerjs=r'''(() => {
  "use strict";
  const drawer=document.getElementById("vexo-drawer");
  const shade=document.getElementById("vexo-menu-shade");
  const trigger=document.getElementById("vexo-menu-open");
  const closeButton=document.getElementById("vexo-menu-close");
  let opened=false, closeTimer=0, priorFocus=null, touchStart=null;
  const links=[...drawer.querySelectorAll(".vexo-drawer-link")];

  function finishClose() {
    if (opened) return;
    drawer.hidden=true; shade.hidden=true;
  }
  function open() {
    if (opened) return;
    clearTimeout(closeTimer);
    priorFocus=document.activeElement;
    opened=true;
    drawer.hidden=false; shade.hidden=false;
    drawer.removeAttribute("inert");
    drawer.setAttribute("aria-hidden","false");
    trigger.setAttribute("aria-expanded","true");
    document.body.classList.add("vexo-drawer-open");
    requestAnimationFrame(() => {
      drawer.classList.add("is-open");shade.classList.add("is-open");
      closeButton.focus({preventScroll:true});
    });
  }
  function close() {
    if (!opened) return false;
    opened=false;drawer.classList.remove("is-open");shade.classList.remove("is-open");
    drawer.setAttribute("aria-hidden","true");drawer.setAttribute("inert","");
    trigger.setAttribute("aria-expanded","false");
    document.body.classList.remove("vexo-drawer-open");
    const target=priorFocus?.isConnected ? priorFocus : trigger;
    target.focus({preventScroll:true});
    clearTimeout(closeTimer);
    closeTimer=setTimeout(finishClose,270);
    return true;
  }
  trigger.addEventListener("click",open);
  closeButton.addEventListener("click",close);
  shade.addEventListener("click",close);
  links.forEach(button=>button.addEventListener("click",()=>close()));
  document.addEventListener("keydown",event=>{
    if(!opened) return;
    if(event.key==="Escape"){event.preventDefault();close();return;}
    if(event.key!=="Tab")return;
    const focusable=[closeButton,...links.filter(x=>!x.disabled)];
    const current=focusable.indexOf(document.activeElement);
    if(event.shiftKey && current<=0){event.preventDefault();focusable[focusable.length-1].focus();}
    else if(!event.shiftKey && current===focusable.length-1){event.preventDefault();closeButton.focus();}
  });
  document.addEventListener("touchstart",event=>{
    if(event.touches.length!==1){touchStart=null;return;}
    const t=event.touches[0];touchStart={x:t.clientX,y:t.clientY};
  },{passive:true});
  document.addEventListener("touchend",event=>{
    if(!touchStart || event.changedTouches.length!==1)return;
    const t=event.changedTouches[0],dx=t.clientX-touchStart.x,dy=t.clientY-touchStart.y;
    if(Math.abs(dx)>75 && Math.abs(dx)>Math.abs(dy)*1.5){
      if(opened && dx < 0)close();
      if(!opened && dx > 0 && touchStart.x < 32)open();
    }
    touchStart=null;
  },{passive:true});
  window.VexoDrawer=Object.freeze({closeIfOpen:close,isOpen:()=>opened});
})();
'''
put(assets/"r20-drawer.js",drawerjs)

print("VEXO_R20_UPGRADE: OCR retained, simulator absent, blank day home, swipe drawer, finance retained")
