"""Replay the verified R13 product delta over the official, layered R12 sources."""
import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

manifest = Path(__file__).parent
data = json.loads((manifest/'product-r13-manifest.json').read_text())
root = Path(sys.argv[1]).resolve(strict=True)

def digest(b):
    return hashlib.sha256(b).hexdigest()

def files():
    return {p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}

assert files()==data['base'], 'Expected checked R12 source tree'
chunks=sorted((manifest/'product-chunks').glob('chunk-*.b64'))
assert len(chunks)==data['parts']
payload=b''.join(base64.b64decode(p.read_bytes().strip(),validate=True) for p in chunks)
assert digest(payload)==data['bundle_sha256']
with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as t:
    members=t.getmembers()
    assert len(members)==len(set(m.name for m in members))==len(data['members'])
    assert set(m.name for m in members)==set(data['members'])
    content={}
    for m in members:
        assert m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts
        with t.extractfile(m) as f:
            b=f.read()
        assert digest(b)==data['members'][m.name]
        content[m.name]=b
    orig=root/'app/src/main/assets/aurora/index.html'
    dest=orig.with_name('overlay-r12.html')
    assert not dest.exists()
    shutil.copyfile(orig,dest)
    patch=content.pop('product.patch')
    subprocess.run(['patch','--quiet','--batch','--forward','-p1','-d',str(root)],input=patch,check=True)
    for name,b in content.items():
        target=root/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:
            f.write(b)
assert files()==data['target'], 'R13 product replay was not exact'
print('AURORA_QA:R13_PRODUCT_REPLAY_VERIFIED')
