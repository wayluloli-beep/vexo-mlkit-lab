#!/usr/bin/env python3
"""Retain a verified, one-off APK in its own private download branch."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

REPO = 'wayluloli-beep/vexo-mlkit-lab'
BRANCH = 'vexo-r19-apk-download'
API = '/repos/' + REPO
DEST = 'qa-downloads/Vexo-R19-teste.apk'
HEX = re.compile(r'[0-9a-f]{40}\Z')

def need(ok, label):
    if not ok:
        raise ValueError(label)

def run(env):
    sha = env['GITHUB_SHA']
    need(env['GITHUB_REPOSITORY'] == REPO and env['GITHUB_REF'] == 'refs/heads/' + BRANCH, 'unexpected repo or ref')
    need(env['GITHUB_SERVER_URL'] == 'https://github.com' and env['GITHUB_API_URL'] == 'https://api.github.com', 'wrong GitHub host')
    need(env['GITHUB_RUN_ATTEMPT'] == '1' and HEX.fullmatch(sha), 'wrong revision or attempt')
    token = env['GH_TOKEN']
    path = Path(env['RUNNER_TEMP']) / 'vexo-test-delivery' / 'Vexo-R19-teste.apk'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        attrs = os.fstat(f.fileno())
        need(stat.S_ISREG(attrs.st_mode) and attrs.st_nlink == 1 and 0 < attrs.st_size < 45 * 1024 * 1024, 'unexpected APK')
        payload = f.read(attrs.st_size + 1)
        need(len(payload) == attrs.st_size and payload.startswith(b'PK\x03\x04') and zipfile.is_zipfile(path), 'malformed APK')
    digest = hashlib.sha256(payload).hexdigest()
    expected_blob = hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()

    def request(method, route, data=None):
        c = http.client.HTTPSConnection('api.github.com', timeout=70)
        try:
            headers = {'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                       'User-Agent':'Vexo-private-test-APK', 'X-GitHub-Api-Version':'2022-11-28'}
            body = json.dumps(data,separators=(',',':')).encode() if data is not None else None
            if body is not None:
                headers['Content-Type'] = 'application/json'
            c.request(method, route, body=body, headers=headers)
            response = c.getresponse()
            need(200 <= response.status < 300, f'GitHub status {response.status} ({method})')
            raw = response.read(1048577)
            need(len(raw) <= 1048576, 'unexpected GitHub response length')
            return json.loads(raw)
        finally:
            c.close()

    metadata = request('GET', API)
    need(metadata.get('private') is True and metadata.get('full_name','').lower() == REPO
         and str(metadata.get('id')) == env['GITHUB_REPOSITORY_ID']
         and metadata.get('default_branch') != BRANCH, 'private repository verification failed')
    ref = API + '/git/ref/heads/' + BRANCH

    def same_head():
        row = request('GET', ref)
        need(row.get('ref') == 'refs/heads/' + BRANCH and row['object']['sha'] == sha, 'branch moved during build')
    same_head()
    base = request('GET', API+'/git/commits/'+sha)
    need(base['sha'] == sha and HEX.fullmatch(base['tree']['sha']), 'unexpected source revision')
    blob = request('POST', API+'/git/blobs', {'content':base64.b64encode(payload).decode('ascii'),'encoding':'base64'})
    need(blob.get('sha') == expected_blob, 'uploaded APK checksum differs')
    tree = request('POST', API+'/git/trees', {'base_tree':base['tree']['sha'], 'tree':[
        {'path':DEST,'mode':'100644','type':'blob','sha':expected_blob},
        {'path':DEST+'.sha256','mode':'100644','type':'blob','content':digest+'  Vexo-R19-teste.apk\n'},
    ]})
    need(HEX.fullmatch(tree.get('sha','')), 'invalid download tree')
    commit = request('POST', API+'/git/commits', {'message':'Retain the signed private testing APK [skip ci]','tree':tree['sha'],'parents':[sha]})
    need(HEX.fullmatch(commit.get('sha','')), 'invalid APK commit')
    same_head()
    updated = request('PATCH', API+'/git/refs/heads/'+BRANCH, {'sha':commit['sha'],'force':False})
    need(updated.get('object',{}).get('sha') == commit['sha'] and updated.get('ref') == 'refs/heads/'+BRANCH, 'APK branch update unverified')
    print(f'VEXO_APK_READY: {commit["sha"]} {expected_blob} {len(payload)} {digest} {DEST}')

if __name__ == '__main__':
    try:
        run(os.environ)
    except (ValueError, KeyError, OSError, http.client.HTTPException) as e:
        detail = str(e) if type(e) is ValueError else type(e).__name__
        print('VEXO_APK_RETENTION_STOP: '+detail[:120],file=sys.stderr)
        sys.exit(1)
