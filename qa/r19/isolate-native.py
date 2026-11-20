from pathlib import Path
import hashlib
import shutil
import sys

qa = Path(__file__).resolve().parent
source = Path(sys.argv[1]).resolve()
root = source / "app/src"
overlays = qa / "android-overlay"
expected = qa / "product-r19-manual.sha256"

if not (source / "app/build.gradle.kts").is_file():
    raise SystemExit("not a materialized Aurora source")
main = root / "main/java/com/trackingracing"
tests = root / "test/java/com/trackingracing"
for directory, old_marker in ((main, "ScreenCaptureService.kt"), (tests, "AuroraWebCaptureTest.kt")):
    if not (directory / old_marker).is_file():
        raise SystemExit("expected R19 native tree before isolation")
    if any(not f.is_file() or f.suffix != ".kt" for f in directory.iterdir()):
        raise SystemExit("unexpected native tree layout")
    for f in directory.iterdir():
        f.unlink()
(root / "main/res/xml/file_paths.xml").unlink()
for f in sorted(overlays.rglob("*")):
    if f.is_file():
        dest = source / f.relative_to(overlays)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dest)

actual = {
    f.relative_to(source).as_posix(): hashlib.file_digest(f.open("rb"), "sha256").hexdigest()
    for f in source.rglob("*") if f.is_file()
}
declared = {}
for line in expected.read_text().splitlines():
    digest, relative = line.split("  ", 1)
    declared[relative] = digest
if actual != declared:
    raise SystemExit("manual candidate tree or bytes do not match reviewed snapshot")
print("R19_QA:ANDROID_MANUAL_SOURCE_CHECKED")
