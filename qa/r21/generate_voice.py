#!/usr/bin/env python3
"""Generate user's 20 voice cues from Apache-2.0 Kokoro pf_dora in CI.
No fake ride statistics are dispatched to customers by this generator.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
import numpy as np
import soundfile as sf

from kokoro import KPipeline

source = Path(sys.argv[1])
dest = Path(sys.argv[2])
texts = json.loads(source.read_text(encoding="utf8"))
assert len(texts) == 20
dest.mkdir(parents=True,exist_ok=True)

synth = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M")
for index,(key,text) in enumerate(texts.items(),1):
    if not key.replace("_","").isalnum() or len(text)>300:
        raise ValueError("Invalid voice catalog item")
    fragments=[]
    generator=synth(text,voice="pf_dora",speed=1.0)
    for item in generator:
        segment=getattr(item,"audio",None)
        if segment is None:
            segment=item[2]
        if hasattr(segment,"detach"):
            segment=segment.detach()
        if hasattr(segment,"cpu"):
            segment=segment.cpu()
        segment=np.asarray(segment,dtype="float32").reshape(-1)
        if segment.size:
            fragments.append(segment)
    if not fragments:
        raise RuntimeError("No audio for "+key)
    waveform=np.concatenate(fragments)
    if waveform.size<5000 or not np.isfinite(waveform).all():
        raise RuntimeError("Invalid neural audio for "+key)
    wav=dest/(key+".wav")
    ogg=dest/(key+".ogg")
    sf.write(str(wav),waveform,24000,subtype="PCM_16")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-i",str(wav),"-ac","1","-ar","24000","-c:a","libvorbis","-q:a","4",str(ogg)],check=True)
    wav.unlink()
    if not ogg.exists() or ogg.stat().st_size<1024:
        raise RuntimeError("Audio encode failed for "+key)
    print(f"AURA_NEURAL_AUDIO {index}/20 {key} {ogg.stat().st_size} bytes")
print("AURA_NEURAL_AUDIO_COMPLETE=20; output is offline playable, independent of Android native TTS")
