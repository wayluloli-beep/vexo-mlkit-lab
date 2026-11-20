#!/usr/bin/env python3
"""Real Android UI via ADB. R12 still owns system consent, external timing and stop."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata


def norm(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text)
                            if not unicodedata.combining(c)).casefold().split())


def launcher_component(raw, pkg):
    rows = [row.strip() for row in raw.splitlines()
            if re.fullmatch(re.escape(pkg) + r'/[a-zA-Z_][.\w]*|' +
                            re.escape(pkg) + r'/\.[a-zA-Z_][.\w]*', row.strip())]
    return rows[0] if len(rows) == 1 else None


def click_of(root, pkg, *names, bottom=False, allow_detail=False):
    parents = {child: node for node in root.iter() for child in node}
    wanted = {norm(x) for x in names}
    choices = set()
    for node in root.iter('node'):
        if node.get('package') != pkg or node.get('visible-to-user') == 'false' or node.get('password') == 'true':
            continue
        texts = set(norm(node.get(k, '')) for k in ('text', 'content-desc', 'resource-id'))
        if not wanted.intersection(texts) and not (allow_detail and any(
                value.startswith(label + ' ') for value in texts for label in wanted)):
            continue
        while node is not None and node.get('package') == pkg and node.get('enabled') != 'false':
            attrs = node.attrib
            if attrs.get('clickable') == 'true' or attrs.get('class') in (
                    'android.widget.Spinner', 'android.widget.CheckBox', 'android.widget.RadioButton'):
                m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', attrs.get('bounds', ''))
                if m:
                    l, t, r, b = map(int, m.groups())
                    if l < r and t < b:
                        choices.add(((l+r)//2, (t+b)//2))
                break
            node = parents.get(node)
    if bottom and choices:
        y = max(point[1] for point in choices)
        choices = {point for point in choices if point[1] == y}
    return next(iter(choices)) if len(choices) == 1 else None


def local_metrics(text):
    return all(re.search(pattern, norm(text)) for pattern in (
        r'(?<!\d)1[,.]34\s*(?:/\s*)?km\b', r'(?<!\d)29[,.]29\s*(?:/\s*)?(?:h|hr)\b'))


def is_local_result(text):
    value = norm(text)
    return (local_metrics(value) and 'pop' in value
            and bool(re.search(r'(?<!\d)8[,.]30(?!\d)', value)))


def local_scope(root, pkg):
    marker = 'balao ocr local'
    keys = ('text', 'content-desc')
    for n in root.iter('node'):
        if n.get('package') != pkg or n.get('visible-to-user') == 'false':
            continue
        attrs = [norm(n.get(k, '')) for k in keys]
        if not any(a == marker or a.startswith(marker + ' ') for a in attrs):
            continue
        return ' '.join(x for child in n.iter('node') if child.get('package') == pkg
                        for k in keys if (x := child.get(k, '')))
    return ''


LOCAL_TAG = re.compile(r'\bVexoLocalOcr\s*:\s*(pixels src=(pixelcopy|web_draw)|parsed kind=(pop|negocia)|dispatched kind=offer) cap=(\d+)\s*$')


def native_chain(raw):
    observed = {}
    for row in raw.splitlines():
        m = LOCAL_TAG.search(row)
        if not m:
            continue
        token, source, kind, stamp = m.groups()
        cap = int(stamp)
        if source:
            observed[cap] = (source, False)
        elif kind and cap in observed:
            observed[cap] = (observed[cap][0], kind == 'pop')
        elif token == 'dispatched kind=offer' and cap in observed and observed[cap][1]:
            return observed[cap][0], cap
    return None


def r12_module():
    default = Path(__file__).resolve().parents[3]/'r12'/'driver.py'
    spec = importlib.util.spec_from_file_location("vexo_r12_real_driver", os.environ.get('VEXO_R12_DRIVER', str(default)))
    if not spec or not spec.loader:
        raise RuntimeError('R12 Android driver not found')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def product_driver(r12):
    class ProductRun(r12.Run):
        def __init__(self):
            selected = os.environ['SERIAL']
            # R12 originally only admitted its dedicated GitHub port. R13 local uses another dedicated AVD.
            if selected not in ('emulator-5554', 'emulator-5556'):
                raise r12.Failure('target must be a dedicated emulator on 5554 or 5556')
            os.environ['SERIAL'] = 'emulator-5554'
            try:
                super().__init__()
            finally:
                os.environ['SERIAL'] = selected
            self.serial = selected
            self.product_ok = False
            self.product_stages = dict.fromkeys(('launcher', 'first_terms', 'welcome_and_example',
                                                 'central_navigation', 'local_ocr'), 'NOT_RUN')

        def content(self, root):
            return norm(r12.alltext(root, self.pkg))

        def scroll_app(self, root, key):
            candidates = [r12.bounds(node.get('bounds')) for node in root.iter('node')
                          if node.get('package') == self.pkg and node.get('class') == 'android.webkit.WebView']
            return self._scroll_webview(candidates, key)

        def _scroll_webview(self, candidates, key):
            frames = [frame for frame in candidates if frame and frame[3]-frame[1]>280]
            if not frames:
                return False
            l,t,r,b = max(frames, key=lambda a: (a[2]-a[0])*(a[3]-a[1]))
            x = (3*l+r)//4
            self.sh('input','swipe',x,(t+4*b)//5,x,(3*t+2*b)//5,420,timeout=12)
            self.ev('scroll','ACTION',xml=key+'.xml')
            return True

        def product_observe(self, stage, selector, seconds=55, scroll=False):
            self.st = stage
            deadline = time.monotonic()+seconds
            last_error = 'matching visible Android UI node not observed'
            moved = 0
            while time.monotonic() < deadline:
                try:
                    root,key = self.xml(stage)
                    result = selector(root)
                    if result:
                        return root,key,result
                    if scroll and moved < 5 and self.scroll_app(root,key):
                        moved += 1
                except r12.Failure as exc:
                    last_error = str(exc)
                    if 'ANR' in last_error:
                        raise
                time.sleep(.25)
            raise r12.Failure(stage+': '+last_error)

        def state(self, stage, *texts, seconds=55, photo=True):
            root,key,_ = self.product_observe(stage,lambda root: all(norm(v) in self.content(root) for v in texts),seconds)
            pic = self.shot(stage).name if photo else None
            self.ev(stage,'PASS',xml=key+'.xml',png=pic)
            return root,key

        def tap(self, stage, *labels, seconds=55, scroll=False, bottom=False, package=None):
            pkg = package or self.pkg
            root,key,xy = self.product_observe(stage,lambda root: click_of(root,pkg,*labels,bottom=bottom),seconds,scroll)
            self.act(key,xy,stage)
            return root,key

        def tap_select(self, stage, control, value):
            root,key,_ = self.product_observe(stage,lambda r: norm(control) in self.content(r))
            options = []
            for node in root.iter('node'):
                if node.get('package') == self.pkg and node.get('class') == 'android.widget.Spinner':
                    frame = r12.bounds(node.get('bounds'))
                    if frame: options.append((frame,node))
            if not options:
                # WebView may express the associated label and selected value on the clickable element.
                self.tap(stage+'-open',control)
            else:
                index = {'Quais ofertas testar': 0, 'Tempo da oferta na tela': 1}[control]
                ordered = sorted(options,key=lambda row: (row[0][1],row[0][0]))
                if len(ordered) < 3:
                    raise r12.Failure(stage+': could not establish ordered three-control WebView settings group')
                l,t,r,b = ordered[index][0]
                self.act(key,((l+r)//2,(t+b)//2),stage+'-open')
            self.tap(stage+'-choose',value)

        def no_projection(self, label):
            proj = self.sh('dumpsys','media_projection',timeout=18)
            service = self.sh('dumpsys','activity','services',self.pkg,timeout=18)
            self.write(label+'-projection.txt',proj)
            self.write(label+'-services.txt',service)
            if (r12.projection_state(proj,self.pkg) is not False or not r12.services_readable(service)
                    or r12.service_exists(service,self.pkg)):
                raise r12.Failure(label+': unexpected or unparseable external Android state')

        @contextmanager
        def clip(self, name, seconds=180):
            dest = '/sdcard/VexoQa-'+name+'.mp4'
            err = (self.out/(name+'-screenrecord.txt')).open('wb')
            base = [self.adb,'-s',self.serial]
            self.cmd('shell','rm','-f',dest,timeout=10)
            proc = subprocess.Popen(base+['shell','screenrecord','--size','480x854','--bit-rate','500000',
                                        '--time-limit',str(seconds),dest],stdout=err,stderr=err)
            try:
                time.sleep(1.0)
                yield
            finally:
                try:
                    if proc.poll() is None:
                        self.cmd('shell','pkill','-2','-x','screenrecord',timeout=8,check=False)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        proc.wait(timeout=5)
                    rc = subprocess.run(base+['pull',dest,str(self.out/(name+'.mp4'))],
                                        timeout=30,capture_output=True).returncode
                    p=self.out/(name+'.mp4')
                    self.ev(name,'CLIP_COLLECTED' if rc==0 and p.exists() and p.stat().st_size>1024 else 'CLIP_NOT_PROVEN')
                except (subprocess.SubprocessError,r12.Failure) as exc:
                    self.ev(name,'CLIP_NOT_PROVEN',reason=str(exc)[:150])
                finally:
                    err.close()
                    self.cmd('shell','rm','-f',dest,timeout=10,check=False)

        def launcher(self):
            self.st='native-launcher'
            raw=self.sh('cmd','package','resolve-activity','--brief','-a','android.intent.action.MAIN',
                        '-c','android.intent.category.LAUNCHER',self.pkg,timeout=20)
            self.write('launcher-resolve.txt',raw)
            component=launcher_component(raw,self.pkg)
            if component is None:
                raise r12.Failure('installed candidate did not resolve one MAIN/LAUNCHER component')
            self.cmd('logcat','-c',timeout=10)
            output=self.sh('am','start','-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER',
                           '-n',component,timeout=20)
            self.write('launcher-start.txt',output)
            if ('Starting:' not in output or 'Error:' in output):
                raise r12.Failure('Android could not launch the installed Vexo APK')
            self.ev('native-launcher','PASS',component=component)
            self.product_stages['launcher']='PASS'
            # Never invoke the skip button. The real video should progress before welcome.
            # Screencaps do not wait for WebView accessibility idle while the animation plays.
            for n in range(1,4):
                try: self.shot('launch-motion-%02d'%n)
                except r12.Failure: pass
                time.sleep(.4)

        def first_entry(self):
            page,_,witness=self.product_observe('initial-welcome',lambda root: (
                'terms' if 'seu primeiro acesso ao vexo' in self.content(root) else
                'welcome' if any(norm(s) in self.content(root) for s in ('E aí, motora?','Quanto precisa sobrar no bolso?','Boas-vindas')) else None))
            if witness=='terms':
                self.shot('welcome-terms')
                self.ev('entry-disclosure','OBSERVED',png='welcome-terms.png')
                self.tap('accept-terms-check','Aceito os Termos de uso desta minuta.','entry-accept',scroll=True)
                self.tap('accept-terms-continue','Aceitar e continuar','entry-continue',scroll=True)
                self.product_stages['first_terms']='OBSERVED_AND_ACCEPTED'
            else:
                self.ev('entry-disclosure','NOT_OBSERVED',reason='initial UI already showed welcome')
                self.product_stages['first_terms']='NOT_OBSERVED'
            root,key,_=self.product_observe('welcome-data',lambda root: any(
                norm(s) in self.content(root) for s in ('E aí, motora?','Quanto precisa sobrar no bolso?','Boas-vindas')))
            pic=self.shot('welcome-data')
            self.ev('welcome-data','PASS',xml=key+'.xml',png=pic.name)
            self.tap('welcome-begin','Começar')
            self.state('welcome-data-choice','Já roda por aplicativo?')
            self.tap('welcome-without-data','Só quero testar','Testar sem preencher')
            self.state('welcome-plan-preview','Confira seu plano')
            self.tap('welcome-enter','Ir para o aplicativo',scroll=True)
            self.state('main-after-welcome','Treino OCR')
            self.product_stages['welcome_and_example']='PASS'

        def central(self):
            def state(r):
                text=self.content(r)
                if ('painel do motorista' in text or all(x in text for x in
                    ('inicio','configuracoes','ajuda','informacoes'))): return 'central'
                if click_of(r,self.pkg,'Meus atalhos'): return 'shortcuts'
                if click_of(r,self.pkg,'Abrir Menu de Ganhos e Solicitações Visualizadas'): return 'menu'
                return None
            _,_,at = self.product_observe('open-central',state)
            if at=='menu':
                self.tap('main-open-menu','Abrir Menu de Ganhos e Solicitações Visualizadas')
            if at!='central':
                self.tap('main-open-shortcuts','Meus atalhos',scroll=True)
            root,_,_=self.product_observe('central-opened',lambda root: state(root)=='central')
            if 'painel do motorista' not in self.content(root):
                self.tap('central-top-home','Início',bottom=True)
            self.state('central-home','Painel do motorista')

        def navigation(self):
            self.central()
            self.tap('central-open-config','Configurações',bottom=True)
            self.state('central-config','Configurações','Combustível')
            self.tap('central-open-help','Ajuda',bottom=True)
            self.state('central-help','Ajuda','Como testar dentro do Vexo?')
            self.tap('central-open-about','Sobre','Informações',bottom=True)
            self.state('central-about','Google ML Kit no aparelho')
            self.sh('input','keyevent','KEYCODE_BACK')
            self.state('central-back-home','Painel do motorista')
            self.tap('central-return-main','Voltar à tela principal',scroll=True)
            self.state('main-returned','Treino OCR')
            self.product_stages['central_navigation']='PASS'

        def local_log(self):
            pid = self.sh('pidof','-s',self.pkg,timeout=12).strip()
            if not pid.isdecimal():
                raise r12.Failure('local Vexo process ID not available')
            raw=self.cmd('logcat','-d','-v','monotonic','--pid='+pid,'-t','2500','-s','VexoLocalOcr:I','*:S',timeout=17).decode('utf-8','replace')
            clean=''.join(row+'\n' for row in raw.splitlines() if LOCAL_TAG.search(row))
            self.write('local-ocr.log',clean)
            return native_chain(clean)

        def local(self):
            self.tap('local-open-training','Treino OCR')
            self.tap('local-open-training-options','Ajustar treino')
            self.tap_select('local-pop-only','Quais ofertas testar','Somente Pop')
            self.tap_select('local-pace-long','Tempo da oferta na tela','Longo · 12 segundos')
            self.tap('local-save-options','Concluir')
            self.no_projection('local-before')
            self.cmd('logcat','-c',timeout=14)
            root,key,_ = self.product_observe('local-before-ui',lambda root: click_of(root,self.pkg,'Iniciar treino'))
            pic=self.shot('local-before')
            self.write('local-before.xml',(self.out/(key+'.xml')).read_bytes())
            self.ev('local-before','OBSERVED',xml=key+'.xml',png=pic.name)
            if is_local_result(self.content(root)):
                raise r12.Failure('local result visible before start, not a fresh witness')
            self.tap('local-start','Iniciar treino')
            self.st='local-real-ocr'
            def local_witness(root):
                scope = local_scope(root,self.pkg)
                if local_metrics(scope) and is_local_result(self.content(root)):
                    return 'known_pop'
                if 'aguardando leitura' in norm(scope) and not (self.out/'local-idle.xml').exists():
                    return 'idle'
                return None
            try:
                until = time.monotonic()+62
                while time.monotonic()<until:
                    root,key,kind=self.product_observe('local-result-ui',local_witness,max(1,until-time.monotonic()))
                    if kind=='known_pop':break
                    self.write('local-idle.xml',(self.out/(key+'.xml')).read_bytes())
                    self.shot('local-idle')
                    self.ev('local-idle','OBSERVED',xml='local-idle.xml',png='local-idle.png')
                else:
                    raise r12.Failure('not enough time to observe known Pop metrics')
                self.write('local-result.xml',(self.out/(key+'.xml')).read_bytes())
                pic=self.shot('local-result')
                self.no_projection('local-result')
                chain=self.local_log()
                if chain is None: raise r12.Failure('visible OCR result has no matching native pixel, parse and dispatch witness')
                self.ev('local-real-ocr','PASS',xml=key+'.xml',png=pic.name,pixels=chain[0],cap=chain[1],
                        sha256=hashlib.sha256(pic.read_bytes()).hexdigest(),external_projection=False)
            finally:
                self.local_log()
            self.tap('local-end-training','Encerrar treino')
            self.state('local-training-stopped','Treino OCR')
            self.no_projection('local-stopped')
            self.product_stages['local_ocr']='PASS'

        def exit_local_if_visible(self):
            root,key=self.xml('local-safe-exit')
            choice=click_of(root,self.pkg,'Encerrar treino')
            if choice:
                self.act(key,choice,'end-inconclusive-local')
            else:
                modal=click_of(root,self.pkg,'Fechar')
                text=self.content(root)
                if modal and any(stage in text for stage in ('ajustar treino','iniciar treino')):
                    self.act(key,modal,'close-inconclusive-local-options')
            self.state('main-after-local-attempt','Treino OCR',seconds=20)
            self.no_projection('local-after-inconclusive')

        def app_button(self,label,seconds=31):
            if label=='stop_toggle':
                self.central()
            choices=('OCR em outros apps','OCR sobre outros apps','Parar OCR externo','Parar captura')
            def inspect(r):
                point=click_of(r,self.pkg,*choices,allow_detail=True)
                if point:return ('external',point)
                point=click_of(r,self.pkg,'Expandir Simulador 99')
                if point:return ('expand',point)
            root,key,value=self.product_observe(label,inspect,seconds)
            kind,point=value
            if kind=='expand':
                self.act(key,point,label+'-expand')
                root,key,point=self.product_observe(label+'-expanded',lambda r:click_of(r,self.pkg,*choices,allow_detail=True),seconds)
            self.shot(label+'-before')
            self.act(key,point,label)

        def consent(self):
            with self.clip('product-flow'):
                self.launcher()
                self.first_entry()
                self.navigation()
                try:
                    self.local()
                except r12.Failure as issue:
                    self.errs.append(('local-real-ocr',str(issue)))
                    self.product_stages['local_ocr']='INCONCLUSIVE'
                    self.ev('local-real-ocr','INCONCLUSIVE',reason=str(issue)[:300])
                    try:
                        self.shot('local-inconclusive')
                    except r12.Failure:
                        pass
                    self.exit_local_if_visible()
            self.product_ok=(self.product_stages['first_terms']=='OBSERVED_AND_ACCEPTED'
                             and self.product_stages['local_ocr']=='PASS')
            if os.environ.get('VEXO_PRODUCT_ONLY')=='1':
                raise r12.Failure('product-only mode: external flow not requested')
            self.central()
            # R12 asks for actual disclosure and Android permissions, and confirms active projection plus FGS.
            super().consent()

        def run(self):
            rc=super().run()
            status_path=self.out/'driver-result.json'
            status=json.loads(status_path.read_text())
            status['product_real_ocr_chain']=self.product_ok
            status['product_stages']=self.product_stages
            status['motion_review']='MANUAL_FRAME_REVIEW_REQUIRED'
            status['same_apk_witness']='device-apks.sha256'
            self.write('driver-result.json',json.dumps(status,ensure_ascii=False,indent=2)+'\n')
            return (0 if self.product_ok else 1) if os.environ.get('VEXO_PRODUCT_ONLY')=='1' else (rc or int(not self.product_ok))

    return ProductRun


if __name__ == '__main__':
    sys.exit(product_driver(r12_module())().run())
