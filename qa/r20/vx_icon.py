#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
manifest=root/"app/src/main/AndroidManifest.xml"
m=manifest.read_text()
old='android:label="Vexo Aurora"'
assert m.count(old)==1
m=m.replace(old,'android:icon="@drawable/vexo_launcher_vx"\n        android:roundIcon="@drawable/vexo_launcher_vx"\n        android:label="Vexo R20"',1)
manifest.write_text(m)
drawable=root/"app/src/main/res/drawable"
drawable.mkdir(parents=True,exist_ok=True)
(drawable/"vexo_launcher_vx.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108">
<path android:fillColor="#0D141B" android:pathData="M0,0h108v108h-108z"/>
<path android:fillColor="#F0F8FC" android:pathData="M6,28h14l19,46 19,-46h14L47,85H32z"/>
<path android:fillColor="#00C5D8" android:pathData="M61,28h15l10,16 10,-16h12L93,53l15,27H94L85,64 74,80H60l17,-27z"/>
</vector>''')
print("R20_QA: VX icon is in launcher")
