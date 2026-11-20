#!/usr/bin/env python3
"""One already-running dedicated API 35 AVD. No build, install, grants, remote, or injected data."""
import concurrent.futures, datetime, hashlib, json, os, re, shutil, struct, subprocess, sys, time, unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

SOURCE='com.vexo.qa.pixels'
SETTINGS='com.android.settings'
SYS=('com.android.systemui','com.google.android.permissioncontroller','com.android.permissioncontroller','android')
LABEL='Vexo Aurora'
SCENE_SAMPLES={'A':(('early',6.2),('final',9.6)),
               'B':(('early',6.2),('final',9.6)),
               'N':(('early',2.0),('final',5.2))}
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
def overlay_window(s,pkg,visible,uid=None):
    for w in re.split(r'(?m)(?=^[ \t]*Window #\d+ Window\{)',s):
        if not re.match(r'\s*Window #\d+ Window\{',w):continue
        line=w.splitlines()[0];m=re.search(r'(?m)^\s*(?:mOwnerUid=[^\n]*?\s+)?package=([\w.]+)|\bmOwnerUid=\d+[^\n]*?\bpackage=([\w.]+)',w)
        if not m:m=re.search(r'\bpackage=([\w.]+)\s+(?:appop=|perm=|mOwnerUid=)',w)
        # Some releases write metadata as a standalone package=... next to mAttrs.
        if not m:m=re.search(r'(?m)(?:^|[ \t])package=([\w.]+)(?=[ \t\n]|$)',w)
        owner=next((x for x in m.groups() if x),None) if m else None
        u=re.search(r'\bmOwnerUid=(\d+)',w);actual=int(u[1]) if u else None
        if owner is not None and owner!=pkg:continue
        if uid is not None and actual is not None and int(uid)!=actual:continue
        if owner!=pkg and not (uid is not None and actual==int(uid) and re.search(r'\bu\d+\s+'+re.escape(pkg)+r'(?=[}/\s])',line)):continue
        if not re.search(r'(?:ty(?:pe)?\s*[=:]\s*(?:APPLICATION_OVERLAY|2038)\b|TYPE_APPLICATION_OVERLAY)',w,re.I):continue
        if visible and (not re.search(r'mHasSurface\s*=\s*true',w,re.I) or not re.search(r'isVisible\s*=\s*true|isOnScreen\s*=\s*true|mViewVisibility\s*=\s*0x0\b|mDrawState\s*=\s*HAS_DRAWN',w,re.I) or re.search(r'mViewVisibility\s*=\s*0x[48]\b|\b(?:isVisible|isOnScreen)\s*=\s*false',w,re.I)):continue
        f=re.search(r'(?:\bmFrame|\bframe)\s*=\s*(\[-?\d+,-?\d+\]\[-?\d+,-?\d+\])',w)
        return True,bounds(f[1]) if f else None
    return False,None
def projection_state(s,pkg):
    m=re.search(r'(?im)^\s*Media Projection\s*:\s*(.*)',s)
    if not m:return None
    v=m[1].strip()
    if v.lower()=='null' or v.lower()=='none':return False
    return True if re.search(r'(?<![\w.])'+re.escape(pkg)+r'(?![\w.])',v) else None
def services_readable(s):
    return bool(re.search(r'(?im)^\s*ACTIVITY MANAGER SERVICES\b',s)) and not re.search(r'permission denial|exception|error:|can.t find service',s,re.I)
def foreground_service(s,pkg):
    for b in re.split(r'(?m)(?=^[ \t]*\* ServiceRecord\{)',s):
        if re.search(r'ServiceRecord\{[^\n]*\b'+re.escape(pkg)+r'/[^}\s]*ScreenCaptureService',b):
            if re.search(r'\b(?:mIsForeground|isForeground)\s*=\s*false',b,re.I):continue
            if re.search(r'\b(?:mIsForeground|isForeground)\s*=\s*true|foregroundId\s*=\s*[1-9]\d*',b,re.I):return True
    return False
def service_exists(s,pkg):return bool(re.search(r'(?m)^\s*\* ServiceRecord\{[^\n]*\b'+re.escape(pkg)+r'/[^}\s]*ScreenCaptureService',s))
def measurements(scene,text):
    t=re.sub(r'(?<=\d)[.,](?=\d)','.',norm(text))
    if 'ocr real' not in t and 'maximizar historico de corridas' not in t:return None
    # Neighboring rendered spans or an OCR line form a number+unit pair. Do not accept a bag of numbers and units.
    unit=lambda token:re.findall(r'(?<![\w.])(\d+(?:\.\d+)?)\s*/\s*'+token+r'\b',t)
    km,hr=unit('km'),unit('hr')
    if scene=='N':
        if not ('aguardando leitura' in t and not km and not hr and not re.search(r'\d\s*%\s*lucro|\d\s*★',t)):return None
        if not all(re.search(r'[—–−-]\s*'+x,t) for x in (r'/\s*km\b',r'/\s*hr\b',r'★',r'lucro\b')):return None
        return {'rows':'four blank placeholders','state':'Aguardando leitura'}
    a,b,dur,dist={'A':('1.53','56.46','39','24.0'),'B':('2.93','63.00','12','4.3'),'D':('2.58','57.24','10','3.7')}[scene]
    if not km or not hr or set(km)!={a} or set(hr)!={b}:return None
    foot=re.findall(r'(?<!\d)(\d+)\s*m\s*[•·| -]?\s*(\d+(?:\.\d+)?)\s*km\b',t)
    if foot and any(v!=(dur,dist) for v in foot):return None
    return {'value_per_km':km[0],'value_per_hr':hr[0],'footer':(foot[0] if foot else 'not exposed')}
def metric(scene,text):return measurements(scene,text) is not None
def parse_dump(raw):
    s=raw.decode('utf-8','replace')
    m=re.search(r'<(displays|hierarchy|windows)\b',s)
    if not m:raise ValueError('UI hierarchy missing: '+s[:130])
    tag=m[1];end='</'+tag+'>';j=s.rfind(end)
    if j<0:raise ValueError('incomplete hierarchy')
    return ET.fromstring(s[m.start():j+len(end)])
def foreground_fixture(w,a):
    focus=re.search(r'(?im)^\s*mCurrentFocus\s*=([^\n]*)',w)
    fw=bool(re.search(r'\bu\d+\s+com\.vexo\.qa\.pixels/',focus[1])) if focus else None
    if fw is False:return False
    resumed=bool(re.search(r'(?im)^.*(?:mResumedActivity|topResumedActivity|ResumedActivity)\s*[:=].*com\.vexo\.qa\.pixels/',a))
    return fw is True or (fw is None and resumed)
def overlay_op(raw):
    s=raw.lower()
    if not s.strip() or re.search(r'permission denial|unknown operation|\berror\b|exception',s):return 'unknown'
    values=re.findall(r'(?:system_alert_window|system:alert_window)\s*:\s*(allow(?:ed)?|default|ignore|deny|errored|foreground)\b',s)
    if values:
        vals={('allow' if v=='allowed' else v) for v in values if v!='default'}
        return next(iter(vals)) if len(vals)==1 else ('default' if not vals else 'unknown')
    m=re.search(r'default mode\s*:\s*(default|allow|ignore|deny)\b',s)
    return m[1] if m else ('default' if 'no operations' in s else 'unknown')

def settings_activity(s,pkg):
    # Only bind the current resumed ActivityRecord, never its caller or earlier Intent.
    match=re.search(r'(?im)^.*?(?:topResumedActivity|mResumedActivity|ResumedActivity)\s*[:=]\s*ActivityRecord\{([\da-f]+)\s+u\d+\s+([\w.$]+/[\w.$]+)',s)
    if not match:return {}
    token,component=match.groups();top=component.split('/')[0];attrs={'settings':top==SETTINGS,'component':component,'target':False,'detail':False}
    if top!=SETTINGS:return attrs
    block=re.search(r'(?ims)^\s*\*?\s*Hist\s*#\d+\s*:\s*ActivityRecord\{'+re.escape(token)+r'\b.*?(?=^\s*\*?\s*Hist\s*#\d+\s*:|^\s*\* Task\{|\Z)',s)
    intents=[line for line in (block[0].splitlines() if block else []) if re.match(r'^\s*(?:Intent\s*\{|intent\s*=\s*Intent\s*\{)',line,re.I)]
    direct=bool(intents and re.search(r'\bdat=package:'+re.escape(pkg)+r'(?=[\s}])',intents[0]))
    # Android 11+: list activity receives package: but ignores it. Never let that authorize a switch.
    list_activity=bool(re.search(r'\$(?:OverlaySettingsActivity|ManageApplicationsActivity)\b',component))
    attrs.update(target=direct and not list_activity,detail=bool(re.search(r'AppDrawOverlay|DrawOverlayDetails',component,re.I)),list_activity=list_activity)
    return attrs

def perm_words(text):
    t=norm(text)
    return bool(re.search(r'(?:display|draw(?:ing)?|appear)(?:\s+\w+){0,5}\s+(?:over|on top)|on top of other apps|sobrepo|sobre otr[oa]s|sobre outr[oa]s|exibir sobre|aparecer sobre',t))
def change_label(text):
    t=norm(text)
    return perm_words(t) and bool(re.search(r'\b(?:allow(?:ing)?|permit(?:ir)?|enable|autorizar|pode|permitir)\b',t))
def overlay_control(root,pkg,activity,lineage,op):
    """No writes. Pair the localized overlay preference and the identified app before producing a single coordinate."""
    def res(action,why,**data):return {'action':action,'reason':why,**data}
    parents={c:p for p in root.iter() for c in p}
    def own(n):return n.get('package')==SETTINGS or (n.get('package')=='android' and any(p.get('package')==SETTINGS for p in ancestors(n)))
    def ancestors(n):
        while (n:=parents.get(n)) is not None:yield n
    def usable(n):return all(x.get('enabled')!='false' and x.get('visible-to-user')!='false' and x.get('password')!='true' for x in (n,*ancestors(n)))
    def label(n):return ' '.join(vals(n))
    def role(n):
        return (n.get('checkable')=='true' or bool(re.search(r'switch|toggle|checkbox|compoundbutton',n.get('class','')+' '+n.get('resource-id',''),re.I)))
    def xy(n):
        q=bounds(n.get('bounds'));return ((q[0]+q[2])//2,(q[1]+q[3])//2) if q else None
    def clickable(n):
        for a in (n,*ancestors(n)):
            if a.tag!='node' or not own(a) or not usable(a):return None
            if a.get('clickable')=='true' and xy(a):return a
        return None
    ns=[n for n in root.iter('node') if own(n)]
    text=' '.join(norm(label(n)) for n in ns)
    if not ns or activity.get('settings') is False:return res('wait','not_settings_foreground')
    if any(v in text for v in ('restricted setting','setting is restricted','this feature has been turned off','configuracao restrita','for your security, this setting')):return res('blocked','os_restriction')
    if not perm_words(text):return res('wait','no_overlay_permission_title')
    target_name=norm(LABEL)
    owners=[n for n in ns if norm(n.get('text','')) in (target_name,norm(pkg)) or norm(n.get('content-desc',''))==target_name]
    header_names=[norm(label(n)) for n in ns if re.search(r'/(?:entity_header_title|app_name|app_title)$',n.get('resource-id','')) and label(n)]
    if header_names and not any(target_name in v or norm(pkg) in v for v in header_names):return res('wait','different_app_header')
    explicit=[n for n in ns if any(change_label(v) for v in vals(n))]
    row_candidates=[]
    for n in owners:
        btn=clickable(n)
        if btn is not None and any(re.search(r'listview|recyclerview',a.get('class',''),re.I) or a.get('scrollable')=='true' for a in ancestors(btn)):
            row_candidates.append(btn)
    row_candidates=list(dict.fromkeys(row_candidates))
    if not explicit and row_candidates and not activity.get('detail'):
        if len(row_candidates)!=1:return res('wait','ambiguous_app_rows')
        return res('app','verified_settings_list_row',xy=xy(row_candidates[0]))
    if not explicit and not (activity.get('detail') or (owners and not row_candidates and header_names)):
        # Non-scrollable list on a very small installation. Exact app row + generic title only permits opening navigation.
        plain=list(dict.fromkeys(x for n in owners if (x:=clickable(n)) is not None))
        if len(plain)==1 and not activity.get('target'):return res('app','single_app_item',xy=xy(plain[0]))
        return res('scroll' if not owners else 'wait','list_or_transition')
    prior=bool(lineage and explicit and activity.get('settings') is True and not row_candidates and not activity.get('list_activity'))
    identity='tree_app' if (owners or any(target_name in x for x in header_names)) else ('top_target_intent' if activity.get('target') else ('verified_list_to_named_detail' if prior else ''))
    if not identity:return res('wait','app_identity_not_bound')
    # Prefer the nearest permission row; do not pick random toggles in a list or other controls.
    targets=[]
    for n in explicit:
        if not usable(n):continue
        wrapper=clickable(n)
        if wrapper is None:continue
        # MainSwitchBar/Compose row can itself be a button or expose a Switch child without an ID.
        switches=[c for c in wrapper.iter('node') if own(c) and role(c)]
        if any(not usable(c) for c in switches):return res('blocked','disabled_switch')
        real=[c for c in switches if c.get('checkable')=='true']
        if not real:real=[c for c in switches if re.search(r'switch|checkbox|compoundbutton',c.get('class',''),re.I)]
        if len(real)>1 and any(x not in list(y.iter()) and y not in list(x.iter()) for x in real for y in real):return res('wait','multiple_widgets_in_row')
        indicator=real[-1] if real else None
        button=clickable(indicator) if indicator is not None else wrapper
        if button is not None:targets.append((button,indicator))
    if not targets and explicit and not any(usable(n) for n in explicit):return res('blocked','disabled_named_preference')
    if not targets:
        # Text/indicator can be siblings in a non-clickable layout. Only an unambiguous app-specific details screen is allowed.
        raw=[n for n in ns if role(n) and usable(n) and (n.get('checkable')=='true' or re.search(r'(?:Switch|CheckBox|CompoundButton)$',n.get('class',''),re.I))]
        real=[n for n in raw if not any(c in raw for c in list(n.iter())[1:])]
        if len(real)==1 and (explicit or activity.get('detail') or header_names):
            button=clickable(real[0])
            if button is not None:targets=[(button,real[0])]
    if not targets:return res('wait','no_label_bound_actionable_toggle')
    unique={id(t):t for t,_ in targets}
    if len(unique)!=1:return res('wait','ambiguous_named_permission_rows')
    button,indicator=next(((b,n) for b,n in targets if n is not None),targets[0])
    # Only a real checkable semantic carries reliable checked=false; UIAutomator emits false for every TextView.
    if indicator is not None and indicator.get('checkable')=='true' and indicator.get('checked') in ('true','false'):
        state='on' if indicator.get('checked')=='true' else 'off';source='xml'
    else:
        state='on' if op=='allow' else ('off' if op in ('default','deny','ignore','errored') else 'unknown');source='appop'
    return res('switch','identified_permission_row',identity=identity,source=source,state=state,xy=xy(button))

def distilled_settings(root,activity,op,d):
    summary=[];pkgs=set();roles=[]
    for n in root.iter('node'):
        p=n.get('package','')
        if re.fullmatch(r'[A-Za-z0-9_.]{1,90}',p):pkgs.add(p)
        if p not in (SETTINGS,'android') or n.get('password')=='true':continue
        ts=vals(n);interesting=any(perm_words(v) or norm(LABEL) in norm(v) or 'restricted setting' in norm(v) or norm(v) in ('allowed','not allowed','on','off','allow','not permitted') for v in ts)
        role=n.get('checkable')=='true' or bool(re.search(r'switch|toggle|checkbox|compound',n.get('class','')+' '+n.get('resource-id',''),re.I))
        if not (interesting or role):continue
        # Keep only the known app name, system permission/role labels and widget structure, not arbitrary app lists or UI payloads.
        shown=[]
        for v in ts:
            if norm(LABEL) in norm(v):shown.append(LABEL)
            elif perm_words(v) or 'restricted setting' in norm(v) or norm(v) in ('allowed','not allowed','on','off','allow','not permitted'):
                shown.append(re.sub(r'[^\w /.,():+-]',' ',v)[:80])
        row={'t':shown,'id':n.get('resource-id','')[-65:],'cl':n.get('class','').split('.')[-1][:28],'flags':''.join(c if n.get(k)=='true' else '-' for k,c in [('clickable','C'),('checkable','K'),('checked','Y'),('enabled','E')]),'box':n.get('bounds','')[:36]}
        if role:roles.append(row)
        elif len(summary)<5:summary.append(row)
    return {'packages':sorted(pkgs)[:8],'activity':activity.get('component','unknown'),'intent_target':activity.get('target',False),'detail_activity':activity.get('detail',False),'op':op,'decision':d,'nodes':(roles[:5]+summary)[:10]}

# AOSP Android 15 r1 and QPR (r6/r16). These are *separate* resource roles.
PROJ_OS='com.android.systemui'
PROJ_SPIN={PROJ_OS+':id/screen_share_mode_spinner',PROJ_OS+':id/screen_share_mode_options'}
PROJ_TITLE=PROJ_OS+':id/screen_share_dialog_title'
PROJ_WARNING=PROJ_OS+':id/text_warning'
PROJ_MODERN={'start','inicio','share screen','compartilhar tela','start now','iniciar agora'}
PROJ_LEGACY={'start now','iniciar agora','comecar agora'}
PROJ_WHOLE={'entire screen','whole screen','your entire screen','share entire screen','share your entire screen','tela cheia','tela inteira','compartilhar a tela inteira'}
PROJ_SINGLE={'a single app','one app','single app','share one app','um unico app','um app','compartilhar um app'}
PROJ_ACTIONS=PROJ_MODERN|PROJ_LEGACY|{'next','proxima','cancel','cancelar'}
def projection_foreground(activity,windows):
    """Accept the actual OS permission Activity from current state, never a historical record."""
    comp=r'([\w.$]+/[\w.$]+)'
    top=re.search(r'(?im)^\s*(?:topResumedActivity|mResumedActivity|ResumedActivity)\s*[:=]\s*ActivityRecord\{[^}\n]*?\bu\d+\s+'+comp,activity)
    f=re.search(r'(?im)^\s*mCurrentFocus\s*=\s*([^\n]+)',windows)
    mw=re.search(r'\bu\d+\s+'+comp,f[1]) if f else None
    at=top[1] if top else None; focus=mw[1] if mw else None
    proper=lambda c:bool(c and c.split('/')[0]==PROJ_OS and c.split('/',1)[1].rsplit('.',1)[-1]=='MediaProjectionPermissionActivity')
    # Some builds do not export an identifiable mCurrentFocus, but do show the exact current permission Activity.
    explicit_other=bool((focus and not proper(focus)) or (at and not proper(at)) or (f and re.match(r'null\b',f[1],re.I)))
    return {'ok':bool((proper(at) or proper(focus)) and not explicit_other),'owner':PROJ_OS if proper(at) or proper(focus) else None,'activity':at or 'unknown','focus':focus or 'unknown'}
def proj_texts(n):return [norm(v).strip() for v in vals(n) if v]
def proj_titles_app(n):
    # AOSP inserts the complete app label as the final title argument. A longer app label is a different requester.
    lead=(r'(?:'
          r'(?:start (?:recording or casting|casting or recording)|share (?:your |the )?screen) with'
          r'|(?:iniciar (?:a )?gravacao ou transmissao|comecar a gravar ou transmitir|compartilhar (?:(?:a sua|sua|a) )?tela) com(?: o (?:app|aplicativo))?'
          r')')
    for t in proj_texts(n):
        t=re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]','',t).strip()
        if re.fullmatch(lead+r'\s+["“«]?'+re.escape(norm(LABEL))+r'["”»]?\s*[?!.]?',t):return True
    return False
def projection_choice(root,fg):
    def no(reason,mode=None,scope='unknown'):return {'action':'wait','reason':reason,'mode':mode,'scope':scope}
    if not fg.get('ok') or fg.get('owner')!=PROJ_OS:return no('request_activity_not_current')
    parents={c:p for p in root.iter() for c in p}
    def visible(n,enabled=False):
        while n is not None and n.tag=='node':
            if n.get('visible-to-user')=='false' or n.get('password')=='true' or (enabled and n.get('enabled')=='false'):return False
            n=parents.get(n)
        return True
    ns=[n for n in root.iter('node') if n.get('package')==PROJ_OS and visible(n)]
    if not ns:return no('no_systemui_nodes')
    nodes=lambda pred:[n for n in ns if pred(n.get('resource-id',''))]
    mt=nodes(lambda rid:rid==PROJ_TITLE);sp=nodes(lambda rid:rid in PROJ_SPIN);warn=nodes(lambda rid:rid==PROJ_WARNING)
    modern=bool(mt or sp or warn);mode='advanced' if modern else 'legacy'
    titles=mt if modern else nodes(lambda rid:rid in ('android:id/alertTitle',PROJ_OS+':id/alertTitle','android:id/title'))
    if len(titles)!=1 or not proj_titles_app(titles[0]):return no('requester_not_in_unique_system_title',mode)
    if modern:
        if len(warn)!=1 or not any(proj_texts(c) for c in warn[0].iter('node')):return no('system_warning_missing',mode)
        if len(sp)!=1 or not sp[0].get('class','').endswith('.Spinner'):return no('no_unique_known_scope_spinner',mode)
        # Read the actual closed Spinner value; do not use the selected-scope text as a button or the warning as the selection.
        stable=[n for n in sp[0].iter('node') if n.get('package')==PROJ_OS and visible(n,True)]
        labels={v for n in stable for v in proj_texts(n)}
        whole=bool(labels&PROJ_WHOLE);single=bool(labels&PROJ_SINGLE)
        if not whole or single:return no('single_or_ambiguous_scope' if single else 'scope_not_identified',mode,'single_or_ambiguous' if single else 'unknown')
        allowed=PROJ_MODERN
    else:
        msg=nodes(lambda rid:rid in ('android:id/message',PROJ_OS+':id/message'))
        words=' '.join(v for n in msg for v in proj_texts(n))
        if len(msg)!=1 or not re.search(r'(all (?:of )?(?:the )?(?:information|content).{0,100}(?:screen|display)|anything (?:that is )?visible on (?:your|the) screen|tod[oa]s? (?:as |o |os )?(?:informac|conteud).{0,110}tela|tudo (?:o que|que).{0,65}tela)',words):return no('legacy_no_explicit_full_display_warning',mode)
        allowed=PROJ_LEGACY
    buttons=nodes(lambda rid:rid=='android:id/button1')
    if len(buttons)!=1:return no('positive_id_missing_or_duplicate',mode,'entire')
    b=buttons[0];cls=b.get('class','').rsplit('.',1)[-1]
    if cls not in ('Button','AppCompatButton','MaterialButton') or b.get('clickable')!='true' or b.get('enabled')!='true' or not visible(b,True):return no('positive_not_clickable_enabled_button',mode,'entire')
    labels={v for n in b.iter('node') if n.get('package')==PROJ_OS and visible(n,True) for v in proj_texts(n)}
    yes=labels&allowed
    if len(yes)!=1 or labels&{'next','proxima','cancel','cancelar'} or any(v in PROJ_WHOLE|PROJ_SINGLE for v in labels):return no('positive_label_not_known_for_full_capture',mode,'entire')
    box=bounds(b.get('bounds'))
    if not box:return no('positive_bounds_invalid',mode,'entire')
    return {'action':'confirm','reason':'named_system_positive','mode':mode,'scope':'entire','rid':'android:id/button1','class':cls,'label':next(iter(yes)),'xy':((box[0]+box[2])//2,(box[1]+box[3])//2)}
def projection_summary(root,fg,decision):
    ns=[];known=PROJ_SPIN|{PROJ_TITLE,PROJ_WARNING,'android:id/button1','android:id/button2','android:id/button3','android:id/alertTitle','android:id/message'}
    packages=set()
    if root is not None:
        for n in root.iter('node'):
            p=n.get('package','')
            if p in (PROJ_OS,'android',SETTINGS,SOURCE,'com.trackingracing'):packages.add(p)
            if p!=PROJ_OS or n.get('password')=='true':continue
            rid=n.get('resource-id','')
            txt=sorted({t for c in n.iter('node') if c.get('package')==PROJ_OS for t in proj_texts(c) if t in PROJ_ACTIONS|PROJ_SINGLE|PROJ_WHOLE}) if rid in PROJ_SPIN|{'android:id/button1','android:id/button2','android:id/button3'} else []
            if rid in known or (n.get('class','').endswith('.Button') and n.get('clickable')=='true'):
                ns.append({'id':rid if rid in known else 'other_button','class':re.sub(r'[^\w.]','',n.get('class',''))[-52:],'flags':''.join(c if n.get(k)=='true' else '-' for k,c in [('enabled','E'),('clickable','C'),('selected','S')]),'label_or_option':txt,'requester':bool(rid in (PROJ_TITLE,'android:id/alertTitle') and proj_titles_app(n)),'bounds':str(bounds(n.get('bounds')))[:48]})
    return {'packages':sorted(packages),'activity':fg.get('activity','unknown'),'focus':fg.get('focus','unknown'),'owner_verified':fg.get('ok',False),'scope':decision.get('scope','unknown'),'mode':decision.get('mode'),'decision':decision.get('action'),'reason':decision.get('reason'),'controls':ns[:10]}

class Failure(Exception):pass

class Run:
    def __init__(self):
        self.adb=os.environ['ADB'];self.serial=os.environ['SERIAL'];self.pkg=os.environ['PKG'];self.out=Path(os.environ['OUT']);self.out.mkdir(parents=True,exist_ok=True)
        if self.serial!='emulator-5554' or self.pkg!='com.trackingracing':raise Failure('unrecognized dedicated target or package')
        self.start=time.monotonic();self.st='preflight';self.seq=0;self.granted=False;self.stop_ok=False;self.primary=False;self.results={};self.errs=[];self.last_xml=None;self.reviews={};self.samples={}
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
        self.sh('input','tap',*point);ack=time.monotonic()
        self.ev(what,'TAP',xml=k+'.xml',point=point,tap_ack_s=round(ack-self.start,3));time.sleep(.35)
        return ack
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
        selected=0;tapped=False;confirmed=False;backs=0;before='unknown';last_op='unknown'
        last_nav=0;last_back=0;detail_scrolls=0;end=time.monotonic()+94;last=None;k='none';last_decision={}
        def op_read():
            try:return overlay_op(self.sh('cmd','appops','get',self.pkg,'SYSTEM_ALERT_WINDOW',timeout=5))
            except Failure:return 'unknown'
        def current():
            try:
                a=settings_activity(self.sh('dumpsys','activity','activities',timeout=6),self.pkg)
                w=self.sh('dumpsys','window','displays',timeout=5)
                m=re.search(r'(?m)^\s*mCurrentFocus\s*=\s*Window\{[^}\n]*?\bu\d+\s+([\w.$]+/[\w.$]+)',w)
                if m:
                    a['focused']=m[1]
                    if m[1].split('/')[0]!=SETTINGS:a['settings']=False
                    elif a.get('settings') is not True:a={'settings':True,'component':m[1],'focused':m[1]}
                return a
            except Failure:return {}
        def trace(r,k,a,op,d,event='SNAPSHOT'):
            x=distilled_settings(r,a,op,d) if r is not None else {'activity':a.get('component','unknown'),'op':op,'decision':d,'nodes':[]}
            x.update(xml=k,selected=selected,tapped=tapped,confirmed=confirmed,focused=a.get('focused','unknown'))
            print('LIVE:settings_diagnostics:'+event+':'+json.dumps(x,ensure_ascii=True,separators=(',',':')),flush=True)
            with (self.out/'settings-diagnostics.jsonl').open('a') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n')
        def approve(source,op,xml):
            nonlocal confirmed
            if not confirmed:
                confirmed=True
                self.ev('overlay_permission','PASS',xml=xml+'.xml',before=before,after=op,source=source)
                print('LIVE:overlay_permission:OBSERVED:'+json.dumps({'app':self.pkg,'source':source,'before':before,'after':op,'xml':xml+'.xml','screenshot':'overlay-after-tap.png'}),flush=True)
        try:
            initial=op_read()
            self.ev('overlay_initial_op','OBSERVED',reason=initial)
            if initial=='allow':raise Failure('pre-granted overlay permission on the named package; clean click not provable')
            while time.monotonic()<end:
                try:r,k=self.xml('overlay-settings')
                except Failure as e:
                    if 'ANR' in str(e):raise
                    last_decision={'action':'wait','reason':'incomplete_tree'};time.sleep(.4);continue
                last=r;a=current();op=op_read();last_op=op
                if self.systempkg(r):
                    if not tapped or (not confirmed and (before not in ('default','ignore','deny','errored') or op!='allow')):
                        raise Failure('system projection visible without a verified Settings off→on transition')
                    if not confirmed:self.shot('overlay-after-tap');approve('named_Settings_click_then_AppOps_allow_and_system_advanced',op,k)
                    trace(r,k,a,op,{'action':'system_projection','reason':'system_requester_verified'});return
                # Lineage is a confirmed Settings app-list tap plus a separate named permission row in a *currently* focused Settings UI.
                d=overlay_control(r,self.pkg,a,bool(selected and a.get('settings') is True),op);last_decision=d
                trace(r,k,a,op,d)
                if d['action']=='blocked':raise Failure('Android restricted/disabled overlay preference: '+d['reason'])
                if confirmed:
                    if a.get('settings') is False or not any(n.get('package')==SETTINGS for n in r.iter('node')):time.sleep(.4);continue
                    if backs>=4:raise Failure('could not return from verified Settings')
                    if time.monotonic()-last_back<1.5:time.sleep(.3);continue
                    self.sh('input','keyevent','4');backs+=1;last_back=time.monotonic();time.sleep(.55);continue
                if d['action']=='switch':
                    if not tapped:
                        if d['state']=='on' or op=='allow':raise Failure('unexpected already-enabled switch; not a clean permission test')
                        if d['state']!='off' or op not in ('default','deny','ignore','errored'):
                            time.sleep(.35);continue
                        before=op;self.shot('overlay-off')
                        self.act(k,d['xy'],'overlay_real_switch');tapped=True
                        print('LIVE:overlay_real_switch:TARGET:'+json.dumps({'owner':SETTINGS,'app':self.pkg,'source':d['source'],'identity':d['identity'],'opBefore':before,'xml':k+'.xml','screenshot':'overlay-off.png','point':d['xy']}),flush=True)
                        continue
                    if d['state']=='on' and op=='allow':
                        self.shot('overlay-after-tap');approve(d['source']+'_on_and_AppOps_allow',op,k);continue
                    # May still be animating: never issue a second toggle.
                    time.sleep(.4);continue
                if tapped:
                    if op=='allow' and d['action']=='app' and a.get('settings') is True:
                        self.shot('overlay-after-tap');approve('named_Settings_click_then_AppOps_allow_and_list',op,k)
                    time.sleep(.4);continue
                if d['action']=='app' and (selected==0 or selected==1 and time.monotonic()-last_nav>8 and d['reason']=='verified_settings_list_row'):
                    self.act(k,d['xy'],'settings_requester');selected+=1;last_nav=time.monotonic();continue
                if d['action']=='scroll' and not selected and self.swipes(r,k,SETTINGS):continue
                if selected and not tapped and a.get('settings') is True and d['action'] in ('wait','scroll') and detail_scrolls<2 and time.monotonic()-last_nav>4 and self.swipes(r,k,SETTINGS):
                    detail_scrolls+=1;continue
                time.sleep(.4)
            raise Failure('overlay not completed; last='+last_decision.get('reason','no tree')+' before='+before+' after='+last_op+' taps='+str(int(tapped)))
        except Exception:
            trace(last,k,current(),op_read(),last_decision,'FAILURE_LAST_TREE');raise
    def confirm_system_projection(self):
        # Screen-share scope is read only. This driver never opens/changes the Spinner or presses Next.
        deadline=time.monotonic()+34;last=None;lastk='none';decision={'action':'wait','reason':'unobserved'}
        def read_current():
            am=self.sh('dumpsys','activity','activities',timeout=7);w=self.sh('dumpsys','window','displays',timeout=6)
            return projection_foreground(am,w)
        def trace(tag,root,k,fg,d):
            row=projection_summary(root,fg,d);row['xml']=k+'.xml' if k!='none' else None
            line=json.dumps(row,ensure_ascii=True,separators=(',',':'))
            print('LIVE:projection_diagnostics:'+tag+':'+line,flush=True)
            with (self.out/'projection-diagnostics.jsonl').open('a') as f:f.write(line+'\n')
        ready=False;fg={}
        try:
            while time.monotonic()<deadline:
                try:
                    r,k=self.xml('projection-prompt' if not ready else 'projection-confirm-fresh')
                    fg=read_current()
                except Failure as e:
                    decision={'action':'wait','reason':'ANR' if 'ANR' in str(e) else 'tree_or_current_activity_unavailable'}
                    trace('READ_ERROR',None,'none',{},decision)
                    if 'ANR' in str(e):raise
                    ready=False;time.sleep(.25);continue
                last,lastk=r,k;decision=projection_choice(r,fg)
                trace('CONTROL_READY' if decision['action']=='confirm' else 'OBSERVED',r,k,fg,decision)
                if decision['action']!='confirm':ready=False;time.sleep(.3);continue
                if not ready:
                    self.shot('projection-consent-visible');ready=True;continue
                # Revalidation after screenshot supplied a fresh positive button rect and the same host/scope.
                self.act(k,decision['xy'],'system_projection_positive');self.granted=True
                print('LIVE:projection_ui:POSITIVE_TOUCHED:'+json.dumps({'owner':PROJ_OS,'requester':LABEL,'activity':fg['activity'],'mode':decision['mode'],'scope':decision['scope'],'id':decision['rid'],'label':decision['label'],'xml':k+'.xml','screenshot':'projection-consent-visible.png'}),flush=True)
                return PROJ_OS,k
            raise Failure('verified system projection button unavailable: '+decision.get('reason','unknown'))
        except Exception:
            trace('FINAL',last,lastk,fg,decision);raise
    def consent(self):
        self.st='open_app';self.sh('am','start','-n',self.pkg+'/com.trackingracing.AuroraActivity')
        self.app_button('external_entry')
        self.st='app_disclosure'
        r,k,xy=self.observe('disclosure',lambda r:coords(r,self.pkg,['Continuar']) if 'ativar ocr externo' in norm(alltext(r,self.pkg)) else None)
        p=self.shot('disclosure-visible')
        copy=norm(alltext(r,self.pkg))
        self.ev('app_disclosure','OBSERVED',xml=k+'.xml',png=p.name,
                newer_storage_copy_visible='salvar texto e imagens' in copy and 'antes de voce exportar' in copy)
        self.act(k,xy,'disclosure_continue')
        self.st='system_overlay';self.settings();self.st='system_projection'
        p,k=self.confirm_system_projection()
        self.st='active_projection_service'
        for _ in range(11):
            proj=self.sh('dumpsys','media_projection');svc=self.sh('dumpsys','activity','services',self.pkg)
            self.write('active-projection.txt',proj);self.write('active-services.txt',svc)
            if projection_state(proj,self.pkg) is True and foreground_service(svc,self.pkg):
                self.ev('projection_and_fgs','PASS',owner=self.pkg)
                print('LIVE:projection_and_fgs:OBSERVED:'+json.dumps({'owner':self.pkg,'projection_current':True,'foreground_service':'ScreenCaptureService','system_prompt_package':p,'consent_xml':k+'.xml','source':'native system prompt + current Android dumps'}),flush=True);return
            time.sleep(.6)
        raise Failure('no currently owned projection plus active foreground service')
    def source(self):self.sh('am','start','-n',SOURCE+'/.PresenterActivity');time.sleep(.5)
    def scene(self,scene):
        label={'A':'Mostrar cena A','B':'Mostrar cena B','N':'Retirar cartão','D':'Mostrar cena de controle D'}[scene]
        r,k,xy=self.observe('select-'+scene,lambda r:coords(r,SOURCE,[label]),16)
        return self.act(k,xy,'show_'+scene),k
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
    def capture_scene_review(self,scene,tap_ack,k,sample='final',target_s=6.2):
        """Bracket the original ADB screenshot with ownership/focus from the real system."""
        stem='scene-'+scene+('-review' if sample=='final' else '-early')
        def state(phase):
            wm=self.sh('dumpsys','window','windows',timeout=5)
            act=self.sh('dumpsys','activity','activities',timeout=5)
            self.write(f'{stem}-{phase}-windows.txt',wm)
            self.write(f'{stem}-{phase}-resumed.txt','\n'.join(
                l for l in act.splitlines() if re.search(r'resumedActivity',l,re.I)))
            has,frame=overlay_window(wm,self.pkg,True,self.uid)
            digest_readable=bool(re.search(r'(?im)^\s*Window #\d+ Window\{',wm))
            return digest_readable and foreground_fixture(wm,act),has,frame

        # This is the sampling time, not ML Kit latency, time-to-updated-overlay or proof of accuracy.
        time.sleep(max(0,target_s-.55-(time.monotonic()-tap_ack)))
        before=state('before')
        time.sleep(max(0,target_s-(time.monotonic()-tap_ack)))
        shot_start=time.monotonic()
        pic=self.shot(stem)
        shot_finish=time.monotonic()
        after=state('after')
        raw=pic.read_bytes()
        if len(raw)<24 or raw[8:16]!=b'\x00\x00\x00\x0dIHDR':
            raise Failure('invalid PNG header for scene screenshot')
        screen=struct.unpack_from('>II',raw,16)
        visible=bool(before[1] and after[1] and before[2] and before[2]==after[2]
                     and before[2][2]<=screen[0] and before[2][3]<=screen[1])
        external=before[0] and after[0]
        no_overlay=not before[1] and not after[1]
        ready=bool(external and (visible or (scene=='N' and no_overlay)))
        info={
            'scene':scene,'sample':sample,'target_s':target_s,
            'screenshot':pic.name,'sha256':hashlib.sha256(raw).hexdigest(),
            'tap_xml':k+'.xml','tap_ack_s':round(tap_ack-self.start,3),
            'tap_to_screenshot_start_s':round(shot_start-tap_ack,3),
            'tap_to_screenshot_end_s':round(shot_finish-tap_ack,3),
            'foreground':SOURCE if external else None,'structural_ready':ready,
            'owner':self.pkg if visible else None,'owner_2038_visible':visible,
            'type':2038 if visible else None,'uid_expected':self.uid,'screen':list(screen),
            'overlay_frame':list(before[2]) if visible else None,
            'overlay_absent_both_dumps':no_overlay,
            'ocr_pixels_status':'REVIEW_REQUIRED' if ready else 'UNVERIFIED'
        }
        self.samples.setdefault(scene,{})[sample]=info
        if sample=='final':self.reviews[scene]=info
        print('LIVE:scene_'+scene+':REVIEW_CAPTURE:'+json.dumps(info),flush=True)
        self.ev('scene_'+scene,'STRUCTURAL_READY' if ready else 'INCONCLUSIVE',**info)
        return info

    def analyze_scene_review(self,scene,info):
        # Run the optional observer after stopping the real capture. It cannot short-circuit B or N.
        if not info['structural_ready']:
            return None
        if scene=='N' and info['overlay_absent_both_dumps']:
            return {'state':'overlay absent in both surrounding window dumps'}
        if not info['overlay_frame'] or not shutil.which('tesseract'):return None
        pic=self.out/info['screenshot']
        observed=self.crop_text(pic,info['overlay_frame'])
        result=measurements(scene,observed)
        if result is not None:
            print('LIVE:overlay_'+scene+':WITNESS:'+json.dumps(
                {'scene':scene,'sample':info.get('sample'),'owner':self.pkg,'type':2038,'foreground':SOURCE,
                 'via':'cropped real screen OCR','frame':info['overlay_frame'],
                 'observed':result,'screenshot':pic.name}),flush=True)
            self.ev('overlay_'+scene,'PASS',observed=result,png=pic.name)
        if result is None:
            different=next((other for other in ('A','B') if other!=scene and measurements(other,observed) is not None),None)
            if different:
                self.ev('overlay_'+scene,'OTHER_SCENE_OBSERVED',sample=info.get('sample'),observed_scene=different,png=pic.name)
                return {'unexpected_scene':different}
        return result

    def collect_native_timing(self):
        try:
            raw=self.cmd('logcat','-d','-v','monotonic','-t','1200','-s','VexoR10:V',timeout=8).decode('utf-8','replace')
            rows=[line for line in raw.splitlines() if re.search(r'\bVexoR10\s*:',line) and len(line)<=500]
            self.write('vexo-r10-native-timing.txt','\n'.join(rows)+'\n' if rows else '')
            self.ev('native_timing','COLLECTED' if rows else 'UNAVAILABLE',tag='VexoR10',lines=len(rows))
            return len(rows)
        except Failure as e:
            self.ev('native_timing','UNAVAILABLE',reason=str(e)[:150]);return 0
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
            if (projection_state(proj,self.pkg) is False and services_readable(svc) and not service_exists(svc,self.pkg) and re.search(r'(?im)^\s*Window #\d+ Window\{',wm) and not overlay_window(wm,self.pkg,False,getattr(self,'uid',None))[0] and foreground_fixture(wm,act)):
                self.shot('stop-external-confirmed');self.stop_ok=True;self.ev('stop','PASS')
                print('LIVE:stop:OBSERVED:'+json.dumps({'owner':self.pkg,'foreground':SOURCE,'current_projection':False,'service_record':False,'owner_2038_present':False,'active_before_action':True,'screenshot':'stop-external-confirmed.png'}),flush=True);return
            time.sleep(.6)
        raise Failure('stop not established: empty current projection + no FGS/service/window + external foreground required')
    def run(self):
        recording=False
        try:
            self.st='preflight'
            if self.cmd('get-state').strip()!=b'device' or self.sh('getprop','sys.boot_completed').strip()!='1':raise Failure('dedicated AVD not ready')
            if self.sh('getprop','ro.build.version.sdk').strip()!='35':raise Failure('wrong Android API')
            for p in [self.pkg,SOURCE]:
                if 'package:' not in self.sh('pm','path',p):raise Failure('missing installed '+p)
            uid_out=self.sh('cmd','package','list','packages','-U',self.pkg)
            um=re.search(r'(?m)^package:'+re.escape(self.pkg)+r'\s+uid:(\d+)\b',uid_out)
            self.uid=int(um[1]) if um else None
            proj=self.sh('dumpsys','media_projection');self.write('baseline-projection.txt',proj)
            if projection_state(proj,self.pkg) is not False:raise Failure('baseline projection not verifiably empty')
            self.ev('preflight','PASS');self.consent();self.st='open_external_fixture';self.source()
            self.write('record-external.ready','ready\n');recording=True;time.sleep(1.3)
            for scene in ('A','B','N'):
                try:
                    self.st='fixture_'+scene;ack,xml=self.scene(scene)
                    for sample,target in SCENE_SAMPLES[scene]:
                        try:self.capture_scene_review(scene,ack,xml,sample,target)
                        except Exception as e:
                            self.errs.append((self.st+'_'+sample,str(e)))
                            self.ev(self.st+'_'+sample,'INCONCLUSIVE',reason=str(e)[:300])
                            try:self.shot('failure-'+self.st)
                            except Exception:pass
                except Exception as e:
                    self.errs.append((self.st,str(e)));self.ev(self.st,'INCONCLUSIVE',reason=str(e)[:300])
                    try:self.shot('failure-'+self.st)
                    except Exception:pass
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
            if recording:self.write('record-external.done','done\n')
        timing_lines=self.collect_native_timing() if self.granted else 0
        verdicts={}
        for scene,plan in SCENE_SAMPLES.items():
            per={};verdicts[scene]=per
            for sample,_ in plan:
                info=self.samples.get(scene,{}).get(sample)
                if not info or not info['structural_ready']:
                    per[sample]='INCONCLUSIVE' if recording else 'NOT_RUN'
                    continue
                try:found=self.analyze_scene_review(scene,info)
                except Exception as e:
                    found=None;self.ev('optional_text_'+scene,'UNAVAILABLE',reason=str(e)[:200])
                per[sample]=('FAIL_OTHER_SCENE' if found and 'unexpected_scene' in found else
                             'PASS' if found is not None else 'VISUAL_REVIEW_REQUIRED')
            statuses=set(per.values())
            self.results[scene]=next(s for s in ('FAIL_OTHER_SCENE','INCONCLUSIVE','NOT_RUN','VISUAL_REVIEW_REQUIRED','PASS') if s in statuses)
        self.primary=self.results['A']=='PASS'
        collected=self.stop_ok and all(s not in ('INCONCLUSIVE','NOT_RUN') for per in verdicts.values() for s in per.values())
        chain=('FAIL_OTHER_SCENE' if 'FAIL_OTHER_SCENE' in self.results.values() else
               ('PASS' if all(s=='PASS' for s in self.results.values()) else 'VISUAL_REVIEW_REQUIRED') if collected else 'NOT_PROVEN')
        out={'primary_chain':chain,'collection_complete':collected,'A':self.primary,
             'stop':self.stop_ok,'variants':self.results,'scene_reviews':self.reviews,
             'scene_samples':self.samples,'sample_verdicts':verdicts,'native_timing_lines':timing_lines,
             'errors':self.errs,'gallery':'NOT_RUN','stop_extent':'Observed Android service, current projection and window removal on external foreground; not internal history persistence.'}
        self.write('driver-result.json',json.dumps(out,ensure_ascii=False,indent=2));self.ev('driver',chain)
        return 0 if collected and chain!='FAIL_OTHER_SCENE' else 1
if __name__=='__main__':sys.exit(Run().run())
