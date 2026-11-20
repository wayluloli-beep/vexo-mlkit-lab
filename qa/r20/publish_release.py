#!/usr/bin/env python3
"""Publish a signed R20 APK in a prerelease of the user's private repository."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote

REPO="wayluloli-beep/vexo-mlkit-lab"
BRANCH="vexo-r20-ocr-full"
APK_NAME="Vexo-R20-teste.apk"

def request(host,method,path,token,body=None,ctype="application/json"):
    conn=http.client.HTTPSConnection(host,timeout=150)
    headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"Vexo-Private-R20-APK"
    }
    if isinstance(body,dict):
        body=json.dumps(body,separators=(",",":")).encode()
    if body is not None:
        headers["Content-Type"]=ctype
    try:
        conn.request(method,path,body=body,headers=headers)
        response=conn.getresponse()
        output=response.read(1024*1024)
        if response.status<200 or response.status>=300:
            try: msg=json.loads(output).get("message","unknown")
            except Exception: msg="unknown"
            raise ValueError(f"GitHub {host} status {response.status}: {msg[:180]}")
        return json.loads(output)
    finally: conn.close()

def main():
    e=os.environ
    sha=e["GITHUB_SHA"]
    if e["GITHUB_REPOSITORY"]!=REPO or e["GITHUB_REF"]!="refs/heads/"+BRANCH:
        raise ValueError("unexpected repository or branch")
    if e.get("GITHUB_RUN_ATTEMPT")!="1" or not re.fullmatch("[0-9a-f]{40}",sha):
        raise ValueError("wrong run")
    if e.get("GITHUB_API_URL")!="https://api.github.com":
        raise ValueError("wrong GitHub API")
    token=e["GH_TOKEN"]
    path=Path(e["RUNNER_TEMP"])/"vexo-test-delivery"/APK_NAME
    if not path.is_file() or path.is_symlink():
        raise ValueError("APK missing")
    binary=path.read_bytes()
    if not 0<len(binary)<95*1024*1024 or binary[:4]!=b"PK\x03\x04":
        raise ValueError("invalid APK bytes")
    digest=hashlib.sha256(binary).hexdigest()
    meta=request("api.github.com","GET","/repos/"+REPO,token)
    if meta.get("private") is not True or meta.get("full_name")!=REPO:
        raise ValueError("repo not private")
    ref=request("api.github.com","GET","/repos/"+REPO+"/git/ref/heads/"+BRANCH,token)
    if ref.get("object",{}).get("sha")!=sha:
        raise ValueError("source branch moved")
    tag="vexo-r20-test-"+sha[:12]+"-"+e["GITHUB_RUN_ID"]
    rel=request("api.github.com","POST","/repos/"+REPO+"/releases",token,{
        "tag_name":tag,
        "target_commitish":sha,
        "name":"Vexo R20 — APK privado de teste",
        "body":"Edição de teste do Vexo com OCR ML Kit e balão preservados, tela inicial dia vazia e menu lateral. Sem simulador de corridas 99 dentro do app. Não testado com corridas reais da 99.",
        "draft":False,
        "prerelease":True
    })
    asset=request("uploads.github.com","POST","/repos/"+REPO+"/releases/"+str(rel["id"])+"/assets?name="+quote(APK_NAME),token,binary,"application/vnd.android.package-archive")
    if asset.get("name")!=APK_NAME or asset.get("size")!=len(binary) or asset.get("state")!="uploaded":
        raise ValueError("uploaded size or state does not match")
    if asset.get("digest") and asset.get("digest")!="sha256:"+digest:
        raise ValueError("uploaded digest differs")
    url="https://github.com/"+REPO+"/releases/download/"+tag+"/"+APK_NAME
    if asset.get("browser_download_url")!=url:
        raise ValueError("unexpected download URL")
    print("VEXO_R20_APK_READY bytes="+str(len(binary))+" sha256="+digest+" url="+url)
    print("VEXO_R20_RELEASE_PAGE "+rel["html_url"])

if __name__=="__main__":
    try: main()
    except (ValueError,KeyError,OSError,http.client.HTTPException) as e:
        print("VEXO_R20_PUBLISH_STOP "+str(e)[:230],file=sys.stderr)
        sys.exit(1)
