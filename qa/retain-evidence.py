"""Rescue allowlisted clean-AVD screenshots and a short video to the same private QA ref."""
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
BRANCH = 'vexo-live-aurora-r9-once'
API = '/repos/' + REPO
LIMIT = 1536 * 1024
VIDEO_NAME = 'vexo-fluxo.mp4'
VIDEO_LIMIT = 4 * 1024 * 1024
CHUNK = 192 * 1024
PNG_NAMES = ('scene-A-review.png', 'scene-B-review.png', 'scene-N-review.png',
             'projection-consent-visible.png', 'stop-external-confirmed.png', 'overlay-after-tap.png', 'disclosure-visible.png',
             'failure-fixture_A.png', 'failure-fixture_B.png', 'failure-fixture_N.png',
             'failure-system_overlay.png', 'failure-system_projection.png',
             'failure-active_projection_service.png')
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


def boxes(data, start, end):
    """Yield the type and bounded body of each complete ISO BMFF box in a container."""
    while start < end:
        if end - start < 8:
            raise ValueError('incomplete MP4 box')
        size, kind = struct.unpack_from('>I4s', data, start)
        header = 8
        if size == 1:
            if end - start < 16:
                raise ValueError('incomplete extended MP4 box')
            size = struct.unpack_from('>Q', data, start + 8)[0]
            header = 16
        elif size == 0:
            size = end - start
        if not header <= size <= end - start:
            raise ValueError('MP4 box outside its container')
        yield kind, start + header, start + size
        start += size


def valid_mp4(data):
    """Accept one bounded, complete MP4 with exactly one video track and no audio."""
    if not data or len(data) > VIDEO_LIMIT:
        return False
    try:
        top = list(boxes(data, 0, len(data)))
        kinds = [kind for kind, _, _ in top]
        if not kinds or kinds[0] != b'ftyp' or kinds.count(b'ftyp') != 1 or kinds.count(b'moov') != 1:
            return False
        if any(kind not in {b'ftyp', b'free', b'skip', b'wide', b'moov', b'mdat'} for kind in kinds):
            return False
        _, start, end = top[0]
        if end - start < 8 or (end - start) % 4:
            return False
        brands = (data[start:start+4], *(data[i:i+4] for i in range(start+8, end, 4)))
        if not any(brand in {b'isom', b'iso2', b'iso5', b'iso6', b'avc1', b'mp41', b'mp42'} for brand in brands):
            return False
        if not any(kind == b'mdat' and end > start for kind, start, end in top):
            return False
        moov = next((start, end) for kind, start, end in top if kind == b'moov')
        tracks = [(start, end) for kind, start, end in boxes(data, *moov) if kind == b'trak']
        if len(tracks) != 1:
            return False
        media = [(start, end) for kind, start, end in boxes(data, *tracks[0]) if kind == b'mdia']
        if len(media) != 1:
            return False
        handlers = [(start, end) for kind, start, end in boxes(data, *media[0]) if kind == b'hdlr']
        if len(handlers) != 1:
            return False
        start, end = handlers[0]
        return end - start >= 12 and data[start+8:start+12] == b'vide'
    except (ValueError, struct.error):
        return False


def split_video(data):
    parts = []
    files = {}
    for index, offset in enumerate(range(0, len(data), CHUNK)):
        part = data[offset:offset+CHUNK]
        path = 'video/part-%03d.bin' % index
        files[path] = part
        parts.append({'index':index, 'path':path, 'bytes':len(part), 'sha256':hashlib.sha256(part).hexdigest()})
    manifest = {'version':1, 'filename':VIDEO_NAME, 'bytes':len(data),
                'sha256':hashlib.sha256(data).hexdigest(), 'parts':parts}
    files['video/manifest.json'] = (json.dumps(manifest, separators=(',',':'))+'\n').encode('ascii')
    return files


def collect(directory):
    d = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        chosen = {}
        for name in PNG_NAMES:
            content = read_at(d, name, LIMIT)
            if valid_png(content):
                chosen[name] = content
        video = read_at(d, VIDEO_NAME, VIDEO_LIMIT + 1)
        if valid_mp4(video):
            chosen.update(split_video(video))
        elif video is not None:
            print('R9_RETENTION: clip rejected; retaining eligible screenshots only')
        return chosen
    finally:
        os.close(d)


def api_call(token, method, path, body=None):
    # Fixed HTTPS destination, no redirects/proxies, no external helpers, no raw server/error body printed.
    c = http.client.HTTPSConnection('api.github.com', timeout=18)
    try:
        raw = None if body is None else json.dumps(body, separators=(',',':')).encode()
        c.request(method, path, raw, {'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                  'User-Agent':'Vexo-R9-private-QA-evidence', 'Content-Type':'application/json',
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
        print('R9_RETENTION: no eligible media; no remote write')
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
    dest = 'qa-evidence/r9/'+run+'-1/'
    for name, content in files.items():
        blob = api('POST', API+'/git/blobs', {'encoding':'base64','content':base64.b64encode(content).decode('ascii')})
        expected_blob = hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        need(blob.get('sha')==expected_blob, 'unexpected Git blob')
        entries.append({'path':dest+name,'mode':'100644','type':'blob','sha':expected_blob})
    tree = api('POST', API+'/git/trees', {'base_tree':base['tree']['sha'], 'tree':entries})
    need(HEX.fullmatch(tree.get('sha','')), 'invalid new tree')
    commit = api('POST', API+'/git/commits', {'message':'Retain R9 clean AVD evidence [skip ci]', 'tree':tree['sha'], 'parents':[sha]})
    need(HEX.fullmatch(commit.get('sha','')), 'invalid new commit')
    check_head()
    updated = api('PATCH', API+'/git/refs/heads/'+BRANCH, {'sha':commit['sha'], 'force':False})
    need(updated.get('ref')=='refs/heads/'+BRANCH and updated.get('object',{}).get('sha')==commit['sha'], 'unconfirmed ref update')
    png_count = sum(name.endswith('.png') for name in files)
    part_count = sum(name.endswith('.bin') for name in files)
    print('R9_RETENTION: '+str(png_count)+' PNG(s), '+str(part_count)+' video part(s) at '+dest+' commit '+commit['sha'])


if __name__=='__main__':
    try:
        main(os.environ)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:
        # Never echo a credential, a remote response, raw log content, or image data.
        message = str(exc) if type(exc) is ValueError and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__
        print('R9_RETENTION_STOP: '+message[:120], file=sys.stderr)
        sys.exit(1)
