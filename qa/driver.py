#!/usr/bin/env python3
"""One already-running dedicated API 35 AVD. No build, install, grants, remote, or injected data."""
import concurrent.futures, datetime, json, os, re, shutil, struct, subprocess, sys, time, unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

SOURCE='com.vexo.qa.pixels'
SETTINGS='com.android.settings'
SYS=('com.android.systemui','com.google.android.permissioncontroller','com.android.permissioncontroller','android')
LABEL='Vexo Aurora'
def norm(v):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',v) if not unicodedata.combining(c)).casefold().split())
def vals(n): return [v for v in (n.get('text',''),n.get('content-desc','')) if v]
def alltext(root,pkg):
    return ' '.join(x for n in root.iter('node') if n.get('package')==pkg and n.get('password')!='true' for x in vals(n))
def bounds(v):
    m=re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]',v or '')
    if not m:return None
    l,t,r,b=map(int,m.groups());return (l,t,r,b) if l>=0 and t>=0 and r>l and b>t else None
def overlay_text(root,pkg,frame):
    if not frame or root is None:return ''
    l,t,r,b=frame;values=[]
    for n in root.iter('node'):
        q=bounds(n.get('bounds'))
        if n.get('package')==pkg and n.get('visible-to-user')!='false' and q and q[0]>=l and q[1]>=t and q[2]<=r and q[3]<=b:
            values.extend(vals(n))
    return ' '.join(values)
def coords(root,pkg,names=(),rid=None,checked=None):
    """L05 fail-closed semantics: same observed package, exact label/id, one enabled clickable ancestor."""
    parents={c:p for p in root.iter() for c in p};wanted={norm(v) for v in names}
    found={}
    for n in root.iter('node'):
        if n.get('package')!=pkg or n.get('enabled')=='false' or n.get('visible-to-user')=='false' or n.get('password')=='true':continue
        if rid and n.get('resource-id','')!=rid:continue
        if wanted and not wanted.intersection(norm(v) for v in vals(n)):continue
        if not rid and not wanted:continue
        a=n
        while a is not None and a.get('package')==pkg and a.get('clickable')!='true' and a.get('enabled')!='false':a=parents.get(a)
        if a is None or a.get('package')!=pkg or a.get('enabled')=='false' or a.get('clickable')!='true':continue
        if checked is not None:
            checks=[n] if n.get('checkable')=='true' else [c for c in a.iter('node') if c.get('package')==pkg and c.get('checkable')=='true']
            if len(checks)!=1 or checks[0].get('checked')!=str(checked).lower():continue
        rect=bounds(a.get('bounds'))
        if rect:found[a]=rect
    if len(found)!=1:return None
    l,t,r,b=next(iter(found.values()));return ((l+r)//2,(t+b)//2)
def overlay_window(s,pkg,visible):
    sections=re.split(r'(?m)(?=^\s*Window #\d+ Window\{)',s)
    for w in sections:
        if not re.match(r'\s*Window #\d+ Window\{',w):continue
        if not re.search(r'(?<![\w.])'+re.escape(pkg)+r'(?![\w.])',w):continue
        if not re.search(r'(?:ty(?:pe)?\s*[=:]\s*(?:APPLICATION_OVERLAY|2038)\b|TYPE_APPLICATION_OVERLAY)',w,re.I):continue
        if visible and (not re.search(r'mHasSurface\s*=\s*true',w,re.I) or not re.search(r'isVisible\s*=\s*true|isOnScreen\s*=\s*true|mViewVisibility\s*=\s*0x0\b|mDrawState\s*=\s*HAS_DRAWN',w,re.I) or re.search(r'mViewVisibility\s*=\s*0x[48]\b',w)):continue
        m=re.search(r'(?:\bmFrame|\bframe)\s*=\s*(\[-?\d+,-?\d+\]\[-?\d+,-?\d+\])',w)
        return True,bounds(m[1]) if m else None
    return False,None
def projection_state(s,pkg):
    m=re.search(r'(?im)^\s*Media Projection\s*:\s*(.*)',s)
    if not m:return None
    v=m[1].strip()
    if v.lower()=='null' or v.lower()=='none':return False
    return True if re.search(r'(?<![\w.])'+re.escape(pkg)+r'(?![\w.])',v) else None
def foreground_service(s,pkg):
    sections=re.split(r'(?m)(?=^\s*\* ServiceRecord\{)',s)
    return any(re.search(r'ServiceRecord\{[^\n]*\b'+re.escape(pkg)+r'/[^}\s]*ScreenCaptureService',b) and re.search(r'isForeground\s*=\s*true|foregroundId\s*=\s*[1-9]\d*',b) for b in sections)
def service_exists(s,pkg):return bool(re.search(r'(?m)^\s*\* ServiceRecord\{[^\n]*\b'+re.escape(pkg)+r'/[^}\s]*ScreenCaptureService',s))
def metric(scene,text):
    t=norm(text);t=re.sub(r'(?<=\d)[.,](?=\d)', '.', t)
    # Require discriminating live values (absent from A/B pixel artwork) inside the verified overlay.
    marker='ocr real' in t or 'maximizar historico de corridas' in t
    if not marker:return False
    if scene=='N':return 'aguardando leitura' in t and not any(x in t for x in ('56.46','63.00','57.24'))
    a,b,dur,dist={'A':('1.53','56.46','39m','24.0km'),'B':('2.93','63.00','12m','4.3km'),'D':('2.58','57.24','10m','3.7km')}[scene]
    num=lambda n: bool(re.search(r'(?<!\d)'+re.escape(n)+r'(?!\d)',t))
    compact=re.sub(r'\s+','',t)
    return num(a) and num(b) and (('/km' in compact and '/hr' in compact) or (dur in compact and dist in compact))
def parse_dump(raw):
    s=raw.decode('utf-8','replace')
    m=re.search(r'<(displays|hierarchy|windows)\b',s)
    if not m:raise ValueError('UI hierarchy missing: '+s[:130])
    tag=m[1];end='</'+tag+'>';j=s.rfind(end)
    if j<0:raise ValueError('incomplete hierarchy')
    return ET.fromstring(s[m.start():j+len(end)])
def foreground_fixture(w,a):
    return bool(re.search(r'(?im)^.*(?:mCurrentFocus|mFocusedApp)\s*=.*com\.vexo\.qa\.pixels/',w) or re.search(r'(?im)^.*(?:mResumedActivity|topResumedActivity|ResumedActivity)\s*[:=].*com\.vexo\.qa\.pixels/',a))
class Failure(Exception):pass

class Run:
    def __init__(self):
        self.adb=os.environ['ADB'];self.serial=os.environ['SERIAL'];self.pkg=os.environ['PKG'];self.out=Path(os.environ['OUT']);self.out.mkdir(parents=True,exist_ok=True)
        if self.serial!='emulator-5554' or self.pkg!='com.trackingracing':raise Failure('unrecognized dedicated target or package')
        self.start=time.monotonic();self.st='preflight';self.seq=0;self.granted=False;self.stop_ok=False;self.primary=False;self.results={};self.errs=[];self.last_xml=None
    def ev(self,stage,result,**kw):
        msg={'elapsed_s':round(time.monotonic()-self.start,2),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':stage,'status':result,**kw}
        with (self.out/'driver-events.jsonl').open('a') as f:f.write(json.dumps(msg,ensure_ascii=False)+'\n')
        print('LIVE:'+stage+':'+result,kw.get('reason',''),flush=True)
    def cmd(self,*args,timeout=9,check=True):
        try:q=subprocess.run([self.adb,'-s',self.serial,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        except subprocess.TimeoutExpired as e:raise Failure('ADB timeout '+str(args[:3])) from e
        if check and q.returncode:raise Failure('ADB '+str(args[:4])+': '+q.stderr.decode(errors='replace')[:160])
        return q.stdout
    def sh(self,*args,timeout=9):return self.cmd('shell',*args,timeout=timeout).decode(errors='replace')
    def write(self,label,s):
        (self.out/label).write_bytes(s if isinstance(s,bytes) else s.encode());return self.out/label
    def shot(self,label):
        data=self.cmd('exec-out','screencap','-p',timeout=8)
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data)<200:raise Failure('invalid screenshot')
        return self.write(label+'.png',data)
    def xml(self,stage,all_windows=False):
        self.seq+=1;label=f'{self.seq:03}-{stage}'
        raw=self.cmd('exec-out','uiautomator','dump',*(['--windows'] if all_windows else []),'/dev/tty',timeout=13)
        try:r=parse_dump(raw)
        except (ET.ParseError,ValueError) as e:
            self.write(label+'-dump-error.txt',raw[:1100]);raise Failure(str(e))
        self.write(label+'.xml',ET.tostring(r,encoding='utf-8',xml_declaration=True));self.last_xml=r
        if any(n.get('package') in ('android','com.android.systemui') and 'aerr_' in n.get('resource-id','') for n in r.iter('node')):raise Failure('ANR/error dialog')
        return r,label
    def observe(self,stage,fn,seconds=26):
        end=time.monotonic()+seconds;why='no matching control'
        while time.monotonic()<end:
            try:
                r,k=self.xml(stage);res=fn(r)
                if res:return r,k,res
            except Failure as e:
                why=str(e)
                if 'ANR' in why:raise
            time.sleep(.35)
        raise Failure(stage+': '+why)
    def act(self,k,point,what):
        # The only taps entered by the driver come from the immediately preceding parsed UI tree.
        self.sh('input','tap',*point);self.ev(what,'TAP',xml=k+'.xml',point=point);time.sleep(.35)
    def swipes(self,r,k,pkg):
        choices=sorted((v for n in r.iter('node') if n.get('package')==pkg and n.get('scrollable')=='true' and (v:=bounds(n.get('bounds')))),key=lambda x:(x[2]-x[0])*(x[3]-x[1]),reverse=True)
        if not choices:return False
        l,t,rr,b=choices[0];x=(l+rr)//2;self.sh('input','swipe',x,(4*b+t)//5,x,(b+4*t)//5,330);self.ev('settings_list','SCROLL',xml=k+'.xml',bounds=choices[0]);time.sleep(.35);return True
    def app_button(self,label,seconds=31):
        def inspect(r):
            d=coords(r,self.pkg,['OCR sobre outros apps'])
            if d:return ('ocr',d)
            e=coords(r,self.pkg,['Expandir Simulador 99'])
            if e:return ('expand',e)
        r,k,(kind,xy)=self.observe(label,inspect,seconds)
        if kind=='expand':
            self.act(k,xy,label+'_expand')
            r,k,xy=self.observe(label+'-expanded',lambda r:coords(r,self.pkg,['OCR sobre outros apps']),seconds)
        self.shot(label+'-before');self.act(k,xy,label)
    def systempkg(self,r):
        for p in SYS:
            t=norm(alltext(r,p))
            if 'vexo aurora' in t and any(v in t for v in ('screen','record','cast','share','tela','compartilh')):return p
    def settings(self):
        selected=False;changed=False;confirmed=False;backs=0;end=time.monotonic()+75
        while time.monotonic()<end:
            try:r,k=self.xml('overlay-settings')
            except Failure as e:
                if 'ANR' in str(e):raise
                time.sleep(.4);continue
            if self.systempkg(r):
                if not changed or not confirmed:raise Failure('projection shown without an observed off→on Settings switch')
                return
            st=norm(alltext(r,SETTINGS))
            if not st:time.sleep(.5);continue
            has_label=norm(LABEL) in st
            checks=[n for n in r.iter('node') if n.get('package')==SETTINGS and n.get('enabled')!='false' and n.get('checkable')=='true' and (n.get('class','').endswith('Switch') or 'switch' in n.get('resource-id','').lower() or n.get('class','').endswith('CompoundButton'))]
            if has_label and len(checks)==1 and any(v in st for v in ('display over','appear on top','sobrepor','sobre outros','over other apps')):
                n=checks[0]
                if n.get('checked')=='false' and not changed:
                    rid=n.get('resource-id');names=vals(n) or ['Allow display over other apps','Permit drawing over other apps']
                    xy=coords(r,SETTINGS,rid=rid,checked=False) if rid else coords(r,SETTINGS,names,checked=False)
                    if not xy:raise Failure('overlay switch not uniquely actionable')
                    self.shot('overlay-off');self.act(k,xy,'overlay_real_switch');changed=True;continue
                if n.get('checked')=='true':
                    if not changed:raise Failure('overlay permission was pre-granted; clean proof unavailable')
                    confirmed=True;self.shot('overlay-on');self.ev('overlay_permission','PASS',xml=k+'.xml');self.sh('input','keyevent','4');backs+=1;time.sleep(.45);continue
            if confirmed:
                if backs>=4:raise Failure('could not return from Settings')
                self.sh('input','keyevent','4');backs+=1;time.sleep(.45);continue
            xy=coords(r,SETTINGS,[LABEL])
            if xy and not selected:self.act(k,xy,'settings_requester');selected=True;continue
            if not selected and self.swipes(r,k,SETTINGS):continue
            time.sleep(.45)
        raise Failure('overlay permission controls did not complete')
    def consent(self):
        self.st='open_app';self.sh('am','start','-n',self.pkg+'/com.trackingracing.AuroraActivity')
        self.app_button('external_entry')
        self.st='app_disclosure'
        r,k,xy=self.observe('disclosure',lambda r:coords(r,self.pkg,['Continuar']) if 'ativar ocr externo' in norm(alltext(r,self.pkg)) else None)
        self.shot('disclosure-visible');self.act(k,xy,'disclosure_continue')
        self.st='system_overlay';self.settings();self.st='system_projection'
        def yes(r):
            p=self.systempkg(r)
            if not p:return None
            xy=coords(r,p,['Start now','Start recording','Start sharing','Share screen','Share entire screen','Share','Iniciar agora','Compartilhar tela','Começar agora'])
            return (p,xy) if xy else None
        r,k,(p,xy)=self.observe('projection-prompt',yes,18)
        txt=norm(alltext(r,p))
        if re.search(r'\ba single app\b|\bone app\b',txt) and not re.search(r'entire screen|whole screen',txt):raise Failure('system asks for a single app; expected whole display')
        self.shot('projection-consent-visible');self.act(k,xy,'system_projection_positive');self.granted=True
        self.st='active_projection_service'
        for _ in range(11):
            proj=self.sh('dumpsys','media_projection');svc=self.sh('dumpsys','activity','services',self.pkg)
            self.write('active-projection.txt',proj);self.write('active-services.txt',svc)
            if projection_state(proj,self.pkg) is True and foreground_service(svc,self.pkg):
                self.ev('projection_and_fgs','PASS',owner=self.pkg);return
            time.sleep(.6)
        raise Failure('no currently owned projection plus active foreground service')
    def source(self):self.sh('am','start','-n',SOURCE+'/.PresenterActivity');time.sleep(.5)
    def scene(self,scene):
        label={'A':'Mostrar cena A','B':'Mostrar cena B','N':'Retirar cartão','D':'Mostrar cena de controle D'}[scene]
        r,k,xy=self.observe('select-'+scene,lambda r:coords(r,SOURCE,[label]),16)
        self.act(k,xy,'show_'+scene);self.shot('scene-'+scene+'-edge')
    def crop_text(self,pic,frame):
        if not frame:return ''
        l,t,r,b=frame;dst=pic.with_suffix('.crop.png')
        try:
            try:
                from PIL import Image
                with Image.open(pic) as im:
                    if r>im.width or b>im.height:return ''
                    area=im.crop((l,t,r,b)).convert('RGB');area.resize((area.width*3,area.height*3)).save(dst)
            except ImportError:
                conv=shutil.which('magick') or shutil.which('convert')
                if not conv:return ''
                subprocess.run([conv,str(pic),'-crop',f'{r-l}x{b-t}+{l}+{t}','+repage','-resize','300%',str(dst)],check=True,timeout=5,stderr=subprocess.DEVNULL)
            tess=shutil.which('tesseract')
            if not tess:return ''
            q=subprocess.run([tess,str(dst),'stdout','-l','eng','--psm','6'],capture_output=True,text=True,timeout=6)
            self.write(dst.name+'.txt',q.stdout);return q.stdout
        except (OSError,ValueError,subprocess.SubprocessError):return ''
    def probe(self,scene,seconds):
        end=time.monotonic()+seconds;seen=False;err=''
        while time.monotonic()<end:
            try:
                r,k=self.xml('paint-'+scene,True)
            except Failure as e:
                if 'ANR' in str(e):raise
                err=str(e);r=None;self.seq+=1;k=f'{self.seq:03}-paint-{scene}'
            wm=self.sh('dumpsys','window','windows');act=self.sh('dumpsys','activity','activities')
            self.write(k+'-windows.txt',wm);self.write(k+'-resumed.txt','\n'.join(l for l in act.splitlines() if 'ResumedActivity' in l or 'mResumedActivity' in l))
            has,frame=overlay_window(wm,self.pkg,True)
            pic=self.shot(k);seen|=has
            if has and foreground_fixture(wm,act):
                txt=overlay_text(r,self.pkg,frame)
                self.write(k+'-overlay-xml-text.txt',txt)
                if metric(scene,txt):
                    self.ev('overlay_'+scene,'PASS',via='UiAutomator owner + exact metrics + visible WM overlay',xml=k+'.xml',png=pic.name,frame=frame);return True
                txt=self.crop_text(pic,frame)
                if metric(scene,txt):
                    self.ev('overlay_'+scene,'PASS',via='WM rect cropped from screen + OCR',png=pic.name,frame=frame);return True
            time.sleep(.4)
        raise Failure('no populated matching owner-bound balloon; window_seen='+str(seen)+' '+err)
    def stop(self):
        self.st='stop_real'
        before=self.sh('dumpsys','media_projection');before_svc=self.sh('dumpsys','activity','services',self.pkg)
        self.write('before-stop-projection.txt',before);self.write('before-stop-services.txt',before_svc)
        if projection_state(before,self.pkg) is not True or not foreground_service(before_svc,self.pkg):
            raise Failure('capture not live immediately before stop; cannot claim a successful stop action')
        self.sh('am','start','-n',self.pkg+'/com.trackingracing.AuroraActivity');self.app_button('stop_toggle',21)
        # Return to the external surface: hiding while the Aurora activity is foreground is not a stop.
        self.source()
        for i in range(8):
            wm=self.sh('dumpsys','window','windows');svc=self.sh('dumpsys','activity','services',self.pkg);proj=self.sh('dumpsys','media_projection');act=self.sh('dumpsys','activity','activities')
            self.write('stop-windows.txt',wm);self.write('stop-services.txt',svc);self.write('stop-projection.txt',proj)
            if (projection_state(proj,self.pkg) is False and not service_exists(svc,self.pkg) and not overlay_window(wm,self.pkg,False)[0] and foreground_fixture(wm,act)):
                self.shot('stop-external-confirmed');self.stop_ok=True;self.ev('stop','PASS');return
            time.sleep(.6)
        raise Failure('stop not established: empty current projection + no FGS/service/window + external foreground required')
    def run(self):
        try:
            self.st='preflight'
            if self.cmd('get-state').strip()!=b'device' or self.sh('getprop','sys.boot_completed').strip()!='1':raise Failure('dedicated AVD not ready')
            if self.sh('getprop','ro.build.version.sdk').strip()!='35':raise Failure('wrong Android API')
            for p in [self.pkg,SOURCE]:
                if 'package:' not in self.sh('pm','path',p):raise Failure('missing installed '+p)
            proj=self.sh('dumpsys','media_projection');self.write('baseline-projection.txt',proj)
            if projection_state(proj,self.pkg) is not False:raise Failure('baseline projection not verifiably empty')
            self.ev('preflight','PASS');self.consent();self.st='fixture_A';self.source();self.scene('A');self.probe('A',52)
            self.primary=True;self.results['A']='PASS'
            for scene in ('B','N'):
                if time.monotonic()-self.start>215:self.results[scene]='SKIPPED_TO_RESERVE_STOP';continue
                try:self.st='fixture_'+scene;self.scene(scene);self.probe(scene,19);self.results[scene]='PASS'
                except Exception as e:self.results[scene]='INCONCLUSIVE';self.ev('optional_'+scene,'INCONCLUSIVE',reason=str(e)[:300])
        except Exception as e:
            self.errs.append((self.st,str(e)));self.ev(self.st,'FAIL_OR_INCONCLUSIVE',reason=str(e)[:450])
            try:
                self.shot('failure-'+self.st)
                self.write('failure-focus.txt',self.sh('dumpsys','window','windows'))
                self.write('failure-crash.txt',self.sh('logcat','-b','crash','-d','-t','60'))
            except Exception:pass
        finally:
            if self.granted:
                try:self.stop()
                except Exception as e:self.errs.append(('stop',str(e)));self.ev('stop','INCONCLUSIVE',reason=str(e)[:450])
            passed=self.primary and self.stop_ok
            out={'primary_chain':'PASS' if passed else 'NOT_PROVEN','A':self.primary,'stop':self.stop_ok,'variants':self.results,'errors':self.errs,'gallery':'NOT_RUN','stop_extent':'Observed Android service, current projection and window removal on external foreground; not internal history persistence.'}
            self.write('driver-result.json',json.dumps(out,ensure_ascii=False,indent=2));self.ev('driver',out['primary_chain'])
        return 0 if passed else 1
if __name__=='__main__':sys.exit(Run().run())
