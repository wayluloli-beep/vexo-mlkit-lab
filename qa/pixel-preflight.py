#!/usr/bin/env python3
"""Host-only independent crop/OCR readiness, never an Aurora runtime test.

Use before boot/build with the SAME Python and prospective driver as the later run.
A/B authorize only the numeric witness. Select --require-footer / --require-neutral
when those specific observations must also survive this pixel reader.
"""
import argparse, base64, hashlib, importlib.util, json, os, platform, re, shutil
import subprocess, sys, tempfile
from pathlib import Path

sys.dont_write_bytecode = True
CALIBRATION_PNG = "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"
PNG_SHA = "9bfe2be735e5358b0169c5556cb0ca7151cc7c8dbb6843b4ef77890240027c16"
FRAMES = {"A": (20, 19, 272, 255), "B": (315, 19, 567, 255), "N": (610, 19, 862, 255)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, default=Path(__file__).resolve().parent.parent / "driver.py")
    parser.add_argument("--require-footer", action="store_true")
    parser.add_argument("--require-neutral", action="store_true")
    args = parser.parse_args()
    audit = {"synthetic_host_preflight_only": True, "python": sys.executable,
             "python_version": platform.python_version(), "tessdata_prefix_set": bool(os.getenv("TESSDATA_PREFIX"))}

    def done(ok, reason):
        audit.update(ok=ok, reason=reason)
        print("AURORA_QA:PIXEL_PREFLIGHT:" + json.dumps(audit, ensure_ascii=True, separators=(",", ":")), flush=True)
        return 0 if ok else 1

    try:
        tess = shutil.which("tesseract")
        if not tess: return done(False, "tesseract_not_on_path")
        audit["tesseract"] = tess
        ver = subprocess.run([tess, "--version"], capture_output=True, text=True, timeout=6)
        if ver.returncode: return done(False, "tesseract_not_executable")
        audit["version"] = (ver.stdout or ver.stderr).splitlines()[0][:65]
        langs = subprocess.run([tess, "--list-langs"], capture_output=True, text=True, timeout=6)
        if langs.returncode or "eng" not in (langs.stdout + "\n" + langs.stderr).splitlines():
            return done(False, "eng_traineddata_not_listed")
        try:
            from PIL import Image
            audit["crop_backend"] = "PIL " + Image.__version__
        except ImportError:
            audit["crop_backend"] = shutil.which("magick") or shutil.which("convert")
            if not audit["crop_backend"]: return done(False, "no_crop_backend_for_this_python")

        png = base64.b64decode(CALIBRATION_PNG, validate=True)
        if hashlib.sha256(png).hexdigest() != PNG_SHA: return done(False, "calibration_corrupt")
        audit["fixture_sha256"] = PNG_SHA
        audit["driver_sha256"] = hashlib.sha256(args.driver.read_bytes()).hexdigest()
        module = importlib.util.spec_from_file_location("diagnostic_frozen_driver", args.driver)
        driver = importlib.util.module_from_spec(module)
        module.loader.exec_module(driver)
        # Only crop_text() and its output sink. No Run constructor, adb, mocks, app or Android.
        witness = object.__new__(driver.Run)
        with tempfile.TemporaryDirectory(prefix="vexo-pixel-readiness-") as tmp:
            witness.out = Path(tmp)
            pic = witness.out / "synthetic-host-only.png"
            pic.write_bytes(png)
            per_scene = {}
            for scene, frame in FRAMES.items():
                txt = witness.crop_text(pic, frame)
                m = driver.measurements(scene, txt)
                others = [other for other in FRAMES if other != scene and driver.measurements(other, txt)]
                per_scene[scene] = {"own_values": bool(m), "cross_matches": others,
                                    "synthetic_ocr": " ".join(txt.split())[:160]}
                if scene in ("A", "B"):
                    per_scene[scene]["footer_in_driver"] = bool(m and m.get("footer") not in (None, "not exposed"))
                    expected = {"A": r"39\s*m\s*[^\w\s]?\s*24[.,]0\s*km",
                                "B": r"12\s*m\s*[^\w\s]?\s*4[.,]3\s*km"}[scene]
                    per_scene[scene]["footer_numbers_in_ocr"] = bool(re.search(expected, txt, re.I))
            audit["scenes"] = per_scene
        if any(per_scene[s]["cross_matches"] for s in FRAMES):
            return done(False, "outside_crop_matched_incorrect_scene")
        if not all(per_scene[s]["own_values"] for s in ("A","B")):
            return done(False, "positive_crop_or_eng_ocr_failed")
        if args.require_footer and not all(per_scene[s]["footer_in_driver"] for s in ("A","B")):
            return done(False, "requested_footer_not_recognized_by_driver")
        if args.require_neutral and not per_scene["N"]["own_values"]:
            return done(False, "requested_neutral_not_recognized_by_driver")
        return done(True, "witness_ready_for_requested_host_checks_only")
    except Exception as e:
        return done(False, "preflight_error_" + type(e).__name__)


if __name__ == "__main__":
    sys.exit(main())
