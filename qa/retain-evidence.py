#!/usr/bin/env python3
"""Save allowlisted synthetic QA prints to the same private R14 branch, even on test failure."""
import base64
import hashlib
import http.client
import json
import os
import re
import stat
import struct
import sys
import zlib
from pathlib import Path

REPO = 'wayluloli-beep/vexo-mlkit-lab'
BRANCH = 'vexo-product-r14-bound-once'
ROUND = 'r14'
TAG = 'R14_RETENTION'
API = '/repos/' + REPO
LIMIT = 1536 * 1024
SCENES = ('A', 'B', 'N', 'A2', 'B2', 'C', 'D', 'OCCLUDED', 'OCCLUSION', 'RESTORED', 'GALLERY')
PNG_NAMES = tuple('scene-'+s+phase+'.png' for s in SCENES for phase in ('-early','-review')) + (
             'projection-consent-visible.png', 'stop-external-confirmed.png', 'overlay-after-tap.png', 'disclosure-visible.png',
             *('failure-fixture_'+s+'.png' for s in SCENES),
             'failure-system_overlay.png', 'failure-system_projection.png',
             'failure-active_projection_service.png')
# Only synthetic clean-AVD screen captures from known product checkpoints. No video, raw input,
# UI-tree dumps, full logcat, installer streams, images selected by arbitrary glob, or credentials.
PRODUCT_PNG_NAMES = (
    'launch-motion-01.png', 'launch-motion-02.png', 'launch-motion-03.png',
    'welcome-terms.png', 'welcome-data.png', 'welcome-data-choice.png', 'welcome-plan-preview.png',
    'central-home.png', 'central-config.png', 'central-help.png', 'central-about.png',
    'central-back-home.png', 'main-returned.png', 'local-before.png', 'local-idle.png',
    'local-result.png', 'local-training-stopped.png', 'local-first-card.png', 'local-next-card.png', 'local-next-stale.png',
    'failure-native-launcher.png', 'failure-initial-welcome.png', 'failure-welcome-data.png',
    'failure-central-home.png', 'failure-local-real-ocr.png', 'failure-local-result-ui.png',
    'failure-local-open-training.png', 'failure-local-open-training-options.png', 'failure-local-pop-only-open.png', 'failure-local-pace-long-open.png', 'local-inconclusive.png',
)
HEX = re.compile(r'[0-9a-f]{40}\Z')


def need(condition, why):
    if not condition:
        raise ValueError(why)


def read_at(directory, name, limit):
    if not name or '/' in name or name in ('.', '..'):
        return None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except OSError:
        return None
    with os.fdopen(fd, 'rb') as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 0 < st.st_size < limit:
            return None
        data = f.read(limit)
        return data if len(data) == st.st_size else None


def valid_png(data):
    # ADB screencap on this dedicated 720x1280 AVD uses 8-bit RGB/RGBA, non-interlaced.
    # Reject textual/unknown chunks, malformed deflate data and trailing bytes. Upload original bytes.
    if not data or not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) >= LIMIT:
        return False
    i, header, payload = 8, None, bytearray()
    meta = {b'sRGB': 1, b'gAMA': 4, b'cHRM': 32, b'pHYs': 9, b'sBIT': None}
    try:
        while i + 12 <= len(data):
            size, kind = struct.unpack_from('>I4s', data, i)
            end = i + 12 + size
            if end > len(data):
                return False
            part = memoryview(data)[i+8:end-4]
            if zlib.crc32(part, zlib.crc32(kind)) != struct.unpack_from('>I', data, end-4)[0]:
                return False
            if kind == b'IHDR':
                if i != 8 or size != 13:
                    return False
                w,h,depth,color,cm,fm,interlace = struct.unpack('>IIBBBBB', part)
                if (w,h,depth,cm,fm,interlace)!=(720,1280,8,0,0,0) or color not in (2,6):
                    return False
                header = (w,h,3 if color==2 else 4)
            elif not header:
                return False
            elif kind == b'IDAT':
                payload.extend(part)
            elif kind == b'IEND':
                if size or end != len(data) or not payload:
                    return False
                w,h,channels = header
                stride = 1 + w*channels
                stream = zlib.decompressobj()
                pixels = stream.decompress(payload, stride*h+1)
                return (len(pixels)==stride*h and stream.eof and not stream.unused_data
                        and not stream.unconsumed_tail and max(pixels[::stride]) <= 4)
            elif kind not in meta or size != (header[2] if kind==b'sBIT' else meta[kind]):
                return False
            i = end
    except (ValueError, struct.error, zlib.error):
        return False
    return False


def collect(directory):
    try:
        d = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {}
    try:
        chosen = {}
        for name in dict.fromkeys(PRODUCT_PNG_NAMES + PNG_NAMES):
            content = read_at(d, name, LIMIT)
            if valid_png(content):
                chosen[name] = content
        return chosen
    finally:
        os.close(d)


def api_call(token, method, path, body=None):
    # Fixed HTTPS destination, no redirects/proxies, no external helpers, no raw server/error body printed.
    c = http.client.HTTPSConnection('api.github.com', timeout=18)
    try:
        raw = None if body is None else json.dumps(body, separators=(',',':')).encode()
        c.request(method, path, raw, {'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                  'User-Agent':'Vexo-R14-private-QA-evidence', 'Content-Type':'application/json',
                  'X-GitHub-Api-Version':'2022-11-28'})
        r = c.getresponse()
        need(200 <= r.status < 300, 'GitHub API status %d (%s)' % (r.status, method))
        result = r.read(1024*1024+1)
        need(len(result) <= 1024*1024, 'oversized GitHub response')
        return json.loads(result)
    finally:
        c.close()


def main(env, call=api_call):
    need(env.get('GITHUB_REPOSITORY')==REPO and env.get('GITHUB_REF')=='refs/heads/'+BRANCH, 'wrong repo/ref')
    need(env.get('GITHUB_SERVER_URL','https://github.com')=='https://github.com' and
         env.get('GITHUB_API_URL','https://api.github.com')=='https://api.github.com', 'wrong GitHub host')
    sha = env.get('GITHUB_SHA','')
    run = env.get('GITHUB_RUN_ID','')
    need(HEX.fullmatch(sha) and re.fullmatch(r'[1-9][0-9]{0,19}', run) and env.get('GITHUB_RUN_ATTEMPT')=='1','invalid run/revision')
    token = env.get('GH_TOKEN') or env.get('GITHUB_TOKEN')
    need(token, 'missing scoped token')
    expected = Path(env['RUNNER_TEMP']) / 'vexo-live-evidence'
    directory = Path(env.get('VEXO_EVIDENCE_DIR') or expected)
    need(expected.is_absolute() and directory == expected, 'wrong evidence directory')
    files = collect(directory)
    if not files:
        print(TAG+': no eligible media; no remote write')
        return
    def api(method, path, body=None):
        return call(token, method, path, body)
    owner = api('GET', '/users/'+REPO.split('/')[0])
    need(owner.get('login','').lower()==REPO.split('/')[0], 'unexpected owner')
    repo = api('GET', API)
    need(repo.get('private') is True and repo.get('full_name','').lower()==REPO and
         repo.get('owner',{}).get('id') == owner.get('id') and owner.get('id') and repo.get('default_branch')!=BRANCH,
         'not the expected private repository/owner')
    if env.get('GITHUB_REPOSITORY_ID'):
        need(str(repo.get('id'))==env['GITHUB_REPOSITORY_ID'], 'repository ID mismatch')
    ref = API+'/git/ref/heads/'+BRANCH
    def check_head():
        r=api('GET', ref)
        need(r.get('ref')=='refs/heads/'+BRANCH and r.get('object',{}).get('type')=='commit'
             and r['object'].get('sha')==sha, 'branch HEAD differs from job SHA')
    check_head()
    base = api('GET', API+'/git/commits/'+sha)
    need(base.get('sha')==sha and HEX.fullmatch(base.get('tree',{}).get('sha','')), 'invalid base commit/tree')
    entries = []
    dest = 'qa-evidence/'+ROUND+'/'+run+'-1/'
    for name, content in files.items():
        blob = api('POST', API+'/git/blobs', {'encoding':'base64','content':base64.b64encode(content).decode('ascii')})
        expected_blob = hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        need(blob.get('sha')==expected_blob, 'unexpected Git blob')
        entries.append({'path':dest+name,'mode':'100644','type':'blob','sha':expected_blob})
    tree = api('POST', API+'/git/trees', {'base_tree':base['tree']['sha'], 'tree':entries})
    need(HEX.fullmatch(tree.get('sha','')), 'invalid new tree')
    commit = api('POST', API+'/git/commits', {'message':'Retain R14 clean AVD evidence [skip ci]', 'tree':tree['sha'], 'parents':[sha]})
    need(HEX.fullmatch(commit.get('sha','')), 'invalid new commit')
    check_head()
    updated = api('PATCH', API+'/git/refs/heads/'+BRANCH, {'sha':commit['sha'], 'force':False})
    need(updated.get('ref')=='refs/heads/'+BRANCH and updated.get('object',{}).get('sha')==commit['sha'], 'unconfirmed ref update')
    print(TAG+': '+str(len(files))+' PNG(s) at '+dest+' commit '+commit['sha'])


if __name__=='__main__':
    try:
        main(os.environ)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:
        # Never echo a credential, a remote response, raw log content, or image data.
        message = str(exc) if type(exc) is ValueError and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__
        print(TAG+'_STOP: '+message[:120], file=sys.stderr)
        sys.exit(1)
