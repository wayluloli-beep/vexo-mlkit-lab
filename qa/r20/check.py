#!/usr/bin/env python3
from pathlib import Path
import sys
src=Path(sys.argv[1])
assets=src/"app/src/main/assets/aurora"
def need(ok,label):
    if not ok: raise SystemExit("R20_FAIL: "+label)
m=(src/"app/src/main/AndroidManifest.xml").read_text()
native=(src/"app/src/main/java/com/trackingracing/AuroraActivity.kt").read_text()
web=(assets/"central.html").read_text()
js=(assets/"central.js").read_text()
need('android:name=".ScreenCaptureService"' in m,"screen capture service")
need('FOREGROUND_SERVICE_MEDIA_PROJECTION' in m and 'SYSTEM_ALERT_WINDOW' in m,"OCR permissions")
need('TextRecognition.getClient' in native and 'startExternalCapture()' in native and 'ui.post(tick)' in native,"actual OCR")
need('writeManualTurn' in native and 'readManualTurn' in native,"financial persistence")
need('writePrivacyPrefs' in native and 'readPrivacyPrefs' in native,"privacy persistence")
need('<section id="inicio" class="vexo-empty-home"' in web,"empty home")
home=web.split('<section id="inicio" class="vexo-empty-home"',1)[1].split('</section>',1)[0]
need('turno-card' not in home and 'data-action' not in home,"home must be blank")
need('<section id="ganhos"' in web and 'id="turno-form"' in web and 'id="t-indrive"' in web,"financial functions")
need('id="vexo-drawer"' in web and 'vexo-menu-shade' in web,"slide drawer")
need('data-action="externo"' in web and 'bridge[name]()' in js,"OCR menu action")
need('window.VexoDrawer?.closeIfOpen?.()' in js,"Android back closes drawer")
for name in ('Ganhos','Solicitações visualizadas','Meu veículo','Folha de ponto','Configurações','Meu plano de ganhos','OCR em outros apps'):
    need(name in web,"menu missing "+name)
need(not (src/"app/src/main/assets/simulador99.html").exists(),"simulator bundled")
need(not (src/"app/src/main/java/com/trackingracing/Simulador99Activity.kt").exists(),"simulator activity bundled")
need((src/"app/src/main/java/com/trackingracing/ScreenCaptureService.kt").is_file(),"removed OCR native source")
need('com.google.mlkit:text-recognition' in (src/"app/build.gradle.kts").read_text(),"removed ML Kit")
need((assets/"r20-drawer.js").is_file() and (assets/"r20-drawer.css").is_file(),"drawer assets")
print("R20_QA: PASS OCR + ML Kit + finance, blank daytime home, drawer, no 99 simulator")
