"""Rescue allowlisted clean-AVD screenshots and a short video to the same private QA ref."""
import base64
import hashlib
import http.client
import json
import math
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REPO = 'wayluloli-beep/vexo-mlkit-lab'
BRANCH = 'vexo-live-aurora-r12-once'
ROUND = 'r12'
TAG = 'R12_RETENTION'
API = '/repos/' + REPO
LIMIT = 1536 * 1024
VIDEO_NAME = 'vexo-fluxo.mp4'
VIDEO_LIMIT = 4 * 1024 * 1024
MP4_BRANDS = {b'isom', b'iso2', b'iso4', b'iso5', b'iso6', b'mp41', b'mp42', b'avc1', b'3gp4', b'3gp5', b'3gp6'}
CHUNK = 192 * 1024
MIN_FRAMES = 2
MAX_SECONDS = 180
SCENES = ('A', 'B', 'N', 'A2', 'B2', 'C', 'D', 'OCCLUDED', 'OCCLUSION', 'RESTORED', 'GALLERY')
PNG_NAMES = tuple('scene-'+s+phase+'.png' for s in SCENES for phase in ('-early','-review')) + (
             'projection-consent-visible.png', 'stop-external-confirmed.png', 'overlay-after-tap.png', 'disclosure-visible.png',
             *('failure-fixture_'+s+'.png' for s in SCENES),
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
            raise ValueError('incomplete_mp4_box')
        size, kind = struct.unpack_from('>I4s', data, start)
        header = 8
        if size == 1:
            if end - start < 16:
                raise ValueError('incomplete_extended_mp4_box')
            size = struct.unpack_from('>Q', data, start + 8)[0]
            header = 16
        elif size == 0:
            size = end - start
        if not header <= size <= end - start:
            raise ValueError('mp4_box_outside_container')
        yield kind, start + header, start + size
        start += size


def mp4_top(data):
    if not data or len(data) > VIDEO_LIMIT:
        raise ValueError('empty_or_large')
    top = list(boxes(data, 0, len(data)))
    kinds = [kind for kind, _, _ in top]
    need(kinds and kinds[0] == b'ftyp' and kinds.count(b'ftyp') == 1, 'missing_or_duplicate_ftyp')
    _, start, end = top[0]
    need(end - start >= 8 and (end - start) % 4 == 0, 'invalid_ftyp')
    need(kinds.count(b'moov') == 1, 'missing_or_duplicate_moov')
    need(any(kind == b'mdat' and end > start for kind, start, end in top), 'missing_mdat')
    return top


def single_child(data, parent, kind):
    entries = [(s, e) for k, s, e in boxes(data, *parent) if k == kind]
    need(len(entries) == 1, 'nonunique_mp4_child')
    return entries[0]


def container_fallback(data, top):
    """Conservative single-track recorder fallback. Validates sample tables, not decoded pictures."""
    need(all(k in {b'ftyp', b'free', b'skip', b'wide', b'moov', b'mdat'} for k, _, _ in top),
         'nonstandard_top_level_box')
    movie = next((s, e) for k, s, e in top if k == b'moov')
    track = single_child(data, movie, b'trak')
    mh, mh_end = single_child(data, movie, b'mvhd')
    need(mh_end - mh >= 20 and data[mh] in (0, 1), 'invalid_movie_header')
    if data[mh] == 0:
        scale, duration = struct.unpack_from('>II', data, mh+12)
    else:
        need(mh_end - mh >= 32, 'invalid_movie_header')
        scale, duration = struct.unpack_from('>IQ', data, mh+20)
    need(scale > 0 and 0 < duration / scale <= MAX_SECONDS, 'invalid_duration')
    media = single_child(data, track, b'mdia')
    h, h_end = single_child(data, media, b'hdlr')
    need(h_end - h >= 12 and data[h+8:h+12] == b'vide', 'not_video_only')
    sample = single_child(data, single_child(data, media, b'minf'), b'stbl')
    a, b = single_child(data, sample, b'stsz')
    need(b - a >= 12, 'invalid_sample_size_table')
    size, frames = struct.unpack_from('>II', data, a+4)
    need(MIN_FRAMES <= frames <= 24000, 'invalid_frame_count')
    if size == 0:
        need(b - a == 12 + 4 * frames, 'truncated_sample_size_table')
        sizes = struct.unpack_from(f'>{frames}I', data, a+12)
        need(all(sizes), 'empty_video_sample')
    else:
        sizes = (size,)*frames
    mdat = [(s, e) for k, s, e in top if k == b'mdat']
    need(sum(sizes) <= sum(e - s for s, e in mdat), 'sample_data_truncated')
    stco = [(k, s, e) for k, s, e in boxes(data, *sample) if k in (b'stco', b'co64')]
    need(len(stco) == 1 and stco[0][2] - stco[0][1] >= 8, 'invalid_chunk_offset_table')
    kind, a, b = stco[0]
    n = struct.unpack_from('>I', data, a+4)[0]
    step, offset_fmt = (4, 'I') if kind == b'stco' else (8, 'Q')
    need(0 < n <= frames and b - a == 8 + n * step, 'invalid_chunk_count')
    offsets = struct.unpack_from(f'>{n}{offset_fmt}', data, a+8)
    a, b = single_child(data, sample, b'stsc')
    need(b - a >= 8, 'invalid_sample_to_chunk_table')
    count = struct.unpack_from('>I', data, a+4)[0]
    need(0 < count <= n and b - a == 8 + count * 12, 'invalid_sample_to_chunk_count')
    mapping = list(struct.iter_unpack('>III', data[a+8:b]))
    need(mapping[0][0] == 1 and all(0 < f <= n and c > 0 and t == 1 for f,c,t in mapping)
         and all(x[0] < y[0] for x, y in zip(mapping, mapping[1:])), 'invalid_sample_to_chunk_mapping')
    j = pos = 0
    ranges = []
    for i, start in enumerate(offsets, 1):
        if j+1 < count and i == mapping[j+1][0]:
            j += 1
        end_pos = pos + mapping[j][1]
        need(end_pos <= frames, 'sample_count_mismatch')
        end = start + sum(sizes[pos:end_pos])
        need(any(lo <= start < end <= hi for lo, hi in mdat), 'chunk_outside_mdat')
        ranges.append((start, end))
        pos = end_pos
    need(pos == frames, 'sample_count_mismatch')
    ranges.sort()
    need(all(x[1] <= y[0] for x,y in zip(ranges,ranges[1:])), 'overlapping_chunks')
    return {'frames':frames, 'duration_s':round(duration/scale, 3)}


def valid_mp4(data):
    try:
        return bool(container_fallback(data, mp4_top(data)))
    except (ValueError, struct.error):
        return False


def local_command(args):
    # Do not pass the write token or dump native error text. ISO-BMFF input is a private copy on disk.
    env = {'PATH':os.defpath, 'LC_ALL':'C'}
    return subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, env=env, timeout=24)


def probe_video(path, ffprobe):
    result = local_command([ffprobe, '-v', 'error', '-protocol_whitelist', 'file', '-f', 'mov', '-count_frames',
              '-show_entries', 'format=duration:stream=index,codec_type,codec_name,width,height,nb_read_frames:stream_disposition=attached_pic',
              '-of', 'json', str(path)])
    need(result.returncode == 0 and not result.stderr and len(result.stdout) <= 32*1024, 'ffprobe_decode_failed')
    d = json.loads(result.stdout)
    streams = d['streams']
    need(isinstance(streams,list) and 1 <= len(streams) <= 8, 'invalid_stream_count')
    need(all(s.get('codec_type') != 'audio' for s in streams), 'unexpected_audio')
    videos = [s for s in streams if s.get('codec_type') == 'video']
    need(len(videos) == 1, 'need_single_video')
    v = videos[0]
    need(v.get('codec_name') == 'h264' and not v.get('disposition',{}).get('attached_pic'), 'unexpected_video_codec')
    width, height, frames = int(v['width']), int(v['height']), int(v['nb_read_frames'])
    duration = float(d['format']['duration'])
    need(math.isfinite(duration) and 0 < duration <= MAX_SECONDS, 'invalid_duration')
    need(16 <= width <= 1920 and 16 <= height <= 1920 and MIN_FRAMES <= frames <= 24000, 'invalid_video_dimensions_or_frames')
    index = int(v['index'])
    need(0 <= index < 8, 'invalid_stream_index')
    return index, len(streams), {'width':width, 'height':height, 'frames':frames, 'duration_s':round(duration,3)}


def prepare_video(data, find_tool=shutil.which):
    """Prefer decoded validation. Remux supported Android variants without creating frames."""
    report = {'version':1, 'status':'rejected', 'input_bytes':len(data) if data else 0}
    if data is None:
        report.update(status='unavailable', reason='missing_unsafe_or_over_limit')
        return None, report
    stage = 'container'
    try:
        top = mp4_top(data)
        ffprobe, ffmpeg = find_tool('ffprobe'), find_tool('ffmpeg')
        if not ffprobe:
            stage = 'fallback_no_ffprobe'
            details = container_fallback(data, top)
            report.update(status='accepted', method='container_only', **details)
            return data, report
        with tempfile.TemporaryDirectory(prefix='vexo-video-', dir='/tmp') as tmp:
            source = Path(tmp)/'original.mp4'
            source.write_bytes(data)
            stage = 'ffprobe_input'
            index, tracks, details = probe_video(source, ffprobe)
            # Preserve byte-identical input only when it is the expected simple recorder container.
            if tracks == 1 and valid_mp4(data):
                report.update(status='accepted', method='ffprobe_original', **details)
                return data, report
            stage = 'remux'
            need(ffmpeg is not None, 'ffmpeg_missing_for_remux')
            out = Path(tmp)/'remuxed.mp4'
            converted = local_command([ffmpeg, '-nostdin', '-v', 'error', '-xerror', '-protocol_whitelist', 'file',
                         '-f', 'mov', '-i', str(source), '-map', '0:'+str(index), '-c:v', 'copy', '-an', '-sn', '-dn',
                         '-map_metadata', '-1', '-map_chapters', '-1', '-movflags', '+faststart', '-fs', str(VIDEO_LIMIT+1),
                         '-f', 'mp4', str(out)])
            need(converted.returncode == 0 and not converted.stderr and out.is_file(), 'ffmpeg_remux_failed')
            need(0 < out.stat().st_size <= VIDEO_LIMIT, 'remuxed_over_limit')
            remuxed = out.read_bytes()
            stage = 'ffprobe_remuxed'
            need(valid_mp4(remuxed), 'remuxed_container_invalid')
            _, tracks_out, details_out = probe_video(out, ffprobe)
            need(tracks_out == 1 and all(details_out[k] == details[k] for k in ('frames','width','height')), 'remux_changed_video_frames')
            report.update(status='accepted', method='ffprobe_remuxed_no_reencode', **details_out)
            return remuxed, report
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, struct.error, subprocess.SubprocessError) as e:
        # Only stable reason strings generated locally; never propagate parser/stdout/stderr text.
        reason = str(e) if type(e) is ValueError and re.fullmatch('[a-z0-9_]{1,64}', str(e)) else type(e).__name__
        report.update(stage=stage, reason=reason)
        return None, report


def can_preserve_original(data, diagnostics):
    """Retain bounded native-container bytes for private examination only, never as playable proof."""
    if not data or diagnostics.get('status') != 'rejected':
        return False
    if diagnostics.get('stage') != 'fallback_no_ffprobe':
        return False  # Never retain a clip that was actually decoded and rejected.
    try:
        top = mp4_top(data)
        _, a, b = top[0]
        brands = [data[a:a+4], *(data[i:i+4] for i in range(a+8, b, 4))]
        if not any(k in MP4_BRANDS for k in brands):
            return False
        movie = next((a, b) for k, a, b in top if k == b'moov')
        handlers = []
        for k, a, b in boxes(data, *movie):
            if k != b'trak':
                continue
            for tag, p, q in boxes(data, a, b):
                if tag != b'mdia':
                    continue
                for role, u, v in boxes(data, p, q):
                    if role == b'hdlr':
                        need(v-u >= 12, 'truncated_track_handler')
                        handlers.append(data[u+8:u+12])
        # The dedicated screenrecord command asks for no audio. Refuse any declared audio track;
        # allow vendor data/metadata tracks for local review if the container has exactly one video.
        return handlers.count(b'vide') == 1 and b'soun' not in handlers
    except (ValueError, struct.error):
        return False


def split_video(data, validation=None, raw=False):
    parts = []
    files = {}
    directory = 'video-raw' if raw else 'video'
    filename = 'vexo-fluxo.raw.mp4' if raw else VIDEO_NAME
    for index, offset in enumerate(range(0, len(data), CHUNK)):
        part = data[offset:offset+CHUNK]
        path = '%s/part-%03d.bin' % (directory, index)
        files[path] = part
        parts.append({'index':index, 'path':path, 'bytes':len(part), 'sha256':hashlib.sha256(part).hexdigest()})
    manifest = {'version':1, 'filename':filename, 'bytes':len(data),
                'sha256':hashlib.sha256(data).hexdigest(), 'parts':parts}
    if validation is not None:
        manifest['validation'] = validation
    files[directory+'/manifest.json'] = (json.dumps(manifest, separators=(',',':'))+'\n').encode('ascii')
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
        saved, diagnostics = prepare_video(video)
        if saved is not None:
            chosen.update(split_video(saved, diagnostics))
        elif can_preserve_original(video, diagnostics):
            diagnostics.update(status='pending_local_verification', method='raw_native_container_for_private_diagnosis')
            chosen.update(split_video(video, diagnostics, raw=True))
        if chosen or video is not None:
            chosen['video/diagnostics.json'] = (json.dumps(diagnostics, separators=(',',':'))+'\n').encode('ascii')
        print(TAG+': clip '+json.dumps(diagnostics, separators=(',',':')))
        return chosen
    finally:
        os.close(d)


def api_call(token, method, path, body=None):
    # Fixed HTTPS destination, no redirects/proxies, no external helpers, no raw server/error body printed.
    c = http.client.HTTPSConnection('api.github.com', timeout=18)
    try:
        raw = None if body is None else json.dumps(body, separators=(',',':')).encode()
        c.request(method, path, raw, {'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                  'User-Agent':'Vexo-R12-private-QA-evidence', 'Content-Type':'application/json',
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
    commit = api('POST', API+'/git/commits', {'message':'Retain R12 clean AVD evidence [skip ci]', 'tree':tree['sha'], 'parents':[sha]})
    need(HEX.fullmatch(commit.get('sha','')), 'invalid new commit')
    check_head()
    updated = api('PATCH', API+'/git/refs/heads/'+BRANCH, {'sha':commit['sha'], 'force':False})
    need(updated.get('ref')=='refs/heads/'+BRANCH and updated.get('object',{}).get('sha')==commit['sha'], 'unconfirmed ref update')
    png_count = sum(name.endswith('.png') for name in files)
    part_count = sum(name.startswith('video/') and name.endswith('.bin') for name in files)
    raw_count = sum(name.startswith('video-raw/') and name.endswith('.bin') for name in files)
    print(TAG+': '+str(png_count)+' PNG(s), '+str(part_count)+' video part(s), '+str(raw_count)+' pending raw part(s) at '+dest+' commit '+commit['sha'])


if __name__=='__main__':
    try:
        main(os.environ)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:
        # Never echo a credential, a remote response, raw log content, or image data.
        message = str(exc) if type(exc) is ValueError and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__
        print(TAG+'_STOP: '+message[:120], file=sys.stderr)
        sys.exit(1)
