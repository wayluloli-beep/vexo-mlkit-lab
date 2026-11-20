#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
cd "$repo"
[[ $# -eq 1 && -d $1 ]]
work=$(cd "$1" && pwd -P)
[[ -z $(find "$work" -mindepth 1 -print -quit) ]]
report() { printf 'R19_QA:%s\n' "$1"; }
[[ $(git ls-tree -r --name-only HEAD qa/payload | wc -l) == 24 ]]
printf '%s  %s\n' '1f1e08574699aabab795687db1816a5962d033652879b21d924cfc590d50199d' "$work/payload.tar.gz" > "$work/payload-check"
printf '%s  %s\n' '60ee91f33f41194f8514e926e4dbb692961cee2cd7fd983a45366b644facf7d9' qa/qa-source.sha256 | sha256sum --strict --check --status
cat qa/payload/chunk-* > "$work/payload.tar.gz"
sha256sum --strict --check --status "$work/payload-check"
mkdir -p "$work/src"
python3 - "$work/payload.tar.gz" "$work/src" <<'PY'
from pathlib import Path
import sys, tarfile
with tarfile.open(sys.argv[1], 'r:gz') as t:
    members = t.getmembers()
    names = [m.name for m in members]
    assert len(set(names)) == len(names) == 67
    assert all(m.isfile() and (m.name.startswith('aurora/') or m.name.startswith('fixtures/')) for m in members)
    assert all('..' not in Path(m.name).parts for m in members)
    t.extractall(sys.argv[2], filter='data')
PY
(cd "$work/src" && sha256sum --strict --check --status "$repo/qa/qa-source.sha256")
report R19_BASE_PAYLOAD_CHECKED

python3 qa/apply-checked-product.py "$work/src/aurora"
report PRODUCT_OVERLAY_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r10.patch
(cd "$work/src/aurora" && sha256sum --strict --check "$repo/qa/product-r10.sha256")
report FRESHNESS_PATCH_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r11.patch
(cd "$work/src/aurora" && sha256sum --strict --check "$repo/qa/product-r11.sha256")
report PREWARM_PATCH_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r12.patch
(cd "$work/src/aurora" && sha256sum --strict --check "$repo/qa/product-r12.sha256")
report PENDING_NEWEST_FRAME_PATCH_CHECKED
PYTHONDONTWRITEBYTECODE=1 python3 qa/apply-r13-product.py "$work/src/aurora"
report R13_PRODUCT_LAYER_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r14.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$repo/qa/product-r14.sha256")
report R14_CAPTURE_ID_LAYER_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r15.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$repo/qa/product-r15.sha256")
report R15_WARM_LAYER_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r16.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$repo/qa/product-r16.sha256")
report R16_CROP_LAYER_CHECKED
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r17.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$repo/qa/product-r17.sha256")
report R17_WELCOME_CHECKED
node qa/extract-vehicle.cjs "$work/src/aurora/app/src/main/assets/aurora/index.html" "$work/src/aurora/app/src/main/assets/aurora/veiculo.html"
cp qa/r18-added/* "$work/src/aurora/app/src/main/assets/aurora/"
while IFS= read -r path; do
  [[ $path == app/src/main/* && $path != *..* && -f $work/src/aurora/$path ]]
  rm -- "$work/src/aurora/$path"
done < qa/aurora-r18-removed.txt
patch --quiet --batch --forward -d "$work/src/aurora" -p1 < qa/aurora-r18.patch
(cd "$work/src/aurora" && sha256sum --strict --check --status "$repo/qa/product-r18.sha256" && [[ $(find . -type f | wc -l) == $(wc -l < "$repo/qa/product-r18.sha256") ]])
report R18_PRODUCT_CHECKED
dest="$work/src/aurora/app/src/main/assets/aurora"
for path in qa/r19/assets/*; do
  [[ -f $path ]]
  cp -- "$path" "$dest/"
done
patch --quiet --batch --forward -d "$dest" -p1 < qa/r19/onboarding.patch
python3 - "$dest/veiculo.html" <<'PYVEHICLE'
from pathlib import Path
import sys
p=Path(sys.argv[1])
raw=p.read_bytes()
assert raw.count(b'</head>') == 1
p.write_bytes(raw.replace(b'</head>', b'<link rel="stylesheet" href="comfort.css"><script defer src="comfort.js"></script></head>', 1))
PYVEHICLE
(check=$repo/qa/r19/product-r19.sha256
 cd "$work/src/aurora"
 sha256sum --strict --check --status "$check"
 [[ $(find . -type f | wc -l) == $(wc -l < "$check") ]])
report R19_PRODUCT_CHECKED
