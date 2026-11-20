#!/usr/bin/env python3
"""Android verification on the dedicated, offline emulator. No OCR or capture action."""
import os
import sys
import re
import json
import hashlib
from pathlib import Path
import r13_product_flow as baseline


def driver(r12):
    class Turno(baseline.product_driver(r12)):
        def run(self):
            self.product_stages.update(prior_settings='NOT_RUN', upgrade='NOT_RUN', draft='NOT_RUN',
                                       fuel_preserved='NOT_RUN', turno_reopen='NOT_RUN', closure_draft='NOT_RUN', manual_totals='NOT_RUN', saved_reopen='NOT_RUN')
            ok = False
            try:
                self.revision('prior', 'VEXO_R18_PRIOR', 4)
                self.launcher()
                self.state('welcome-terms','Seu primeiro acesso ao Vexo','Termos de uso')
                self.tap('accept-terms-check','Aceito os Termos de uso desta minuta.','entry-accept',scroll=True)
                self.tap('accept-terms-continue','Aceitar e continuar','entry-continue',scroll=True)
                self.product_stages['first_terms']='OBSERVED_AND_ACCEPTED'
                self.state('welcome-data','E aí, motora?','Entrar no Vexo')
                self.tap('welcome-direct-entry','Entrar no Vexo')
                self.state('prior-main','Treino OCR',photo=False)
                self.sh('input','keyevent','KEYCODE_BACK')
                self.state('prior-central','Painel do motorista',photo=False)
                try:
                    self.tap('prior-config','Configurações',bottom=True)
                    self.state('prior-settings','Combustível','Consumo médio',photo=False)
                    self.fill('prior-fuel','km','Consumo médio','13.25',prior_calibrated=True)
                    self.sh('input','keyevent','KEYCODE_BACK')
                    self.tap('prior-save-config','Salvar valores',scroll=True)
                    self.state('prior-verified','Valores salvos no aparelho.',photo=False)
                    self.verify_field('prior-settings-value','km','Consumo médio','13,25')
                    self.product_stages['prior_settings']='PASS'
                except r12.Failure as exc:
                    self.product_stages['prior_settings']='INCONCLUSIVE'
                    self.ev('prior-settings-observer','INCONCLUSIVE',reason=str(exc))
                self.revision('candidate','VEXO_R18_CANDIDATE',5,replacing=True)
                home,_ = self.reopen('upgrade-home','Painel do motorista','Meu turno','Iniciar turno')
                self.no_simulator(home,'upgrade-home')
                self.product_stages['upgrade']='PASS'
                if self.product_stages['prior_settings']=='PASS':
                    try:
                        self.tap('open-config','Configurações',bottom=True)
                        self.verify_field('upgrade-config-value','km','Consumo médio','13,25')
                        self.product_stages['fuel_preserved']='PASS'
                    except r12.Failure as exc:
                        self.product_stages['fuel_preserved']='INCONCLUSIVE'
                        self.ev('upgrade-fuel-observer','INCONCLUSIVE',reason=str(exc))
                    self.reopen('upgrade-back-home','Iniciar turno','Meu turno')
                self.no_projection('upgrade')
                try:
                    self.open_rent('draft-first')
                    self.fill('draft-amount','plano-base','Aluguel mensal','1500')
                    self.reopen('draft-reopen','Meu turno','Iniciar turno')
                    self.open_rent('draft-second')
                    self.verify_field('draft-value','plano-base','Aluguel mensal','1.500,00')
                    self.product_stages['draft']='PASS'
                except r12.Failure as exc:
                    self.product_stages['draft']='INCONCLUSIVE'
                    self.ev('plan-draft-observer','INCONCLUSIVE',reason=str(exc))
                self.reopen('turno-inicio','Meu turno','Iniciar turno')
                self.tap('turno-start','Iniciar turno')
                self.state('turno-started','Em andamento','Turno iniciado','Fechar turno')
                self.reopen('turno-resumed','Em andamento','Turno iniciado','Fechar turno')
                self.product_stages['turno_reopen']='PASS'
                self.tap('turno-open-close','Fechar turno')
                self.state('turno-step-ganhos','Recebimentos em reais','Uber','99','Continuar')
                self.fill('enter-t-uber','t-uber','Uber','150.50',fresh=True)
                self.reopen('turno-draft-resumed','Em andamento','Fechar turno')
                self.tap('turno-draft-open','Fechar turno')
                self.verify_field('saved-close-draft','t-uber','Uber','150.50')
                self.product_stages['closure_draft']='PASS'
                self.fill('enter-t-nove','t-nove','99','69.50',fresh=True)
                self.next_step('turno-ganhos-continue')
                self.state('turno-step-gastos','Gastos','Combustível','Outros gastos','Continuar')
                self.fill('enter-t-fuel','t-fuel','Combustível (R$)','45',fresh=True)
                self.fill('enter-t-extra','t-extra','Outros gastos (R$)','15',fresh=True)
                self.next_step('turno-gastos-continue')
                self.state('turno-step-km','Quilômetros','Quilômetros rodados','Salvar e fechar')
                self.fill('enter-t-km','t-km','Quilômetros rodados','100',fresh=True)
                self.sh('input','keyevent','KEYCODE_BACK')
                self.tap('turno-save','Salvar e fechar',scroll=True)
                totals=('Último turno fechado','R$ 220,00','R$ 60,00','R$ 160,00','R$ 1,60/km')
                self.state('turno-closed',*totals)
                self.product_stages['manual_totals']='PASS'
                self.reopen('turno-persisted','Iniciar turno',*totals)
                self.no_projection('finish')
                self.product_stages['saved_reopen']='PASS'
                ok = self.product_stages['draft']=='PASS' and self.product_stages['fuel_preserved']=='PASS'
            except (r12.Failure, ValueError, OSError) as exc:
                print('R18_DIAGNOSTIC: '+self.safe_reason(exc), flush=True
                )
                phase=self.st if re.fullmatch(r'[a-z0-9-]{1,45}', self.st or '') else 'unknown'
                print('R18_PHASE: '+phase, flush=True)
                self.ev('r18-turno','INCONCLUSIVE',reason=str(exc))
                try:self.shot('turno-inconclusive')
                except r12.Failure:pass
            self.write('driver-result.json',json.dumps(dict(product_stages=self.product_stages))+'\n')
            return 0 if ok else 1

        def safe_reason(self, exc):
            detail=str(exc)
            categories={
                'ADB timeout': 'adb_timeout',
                'ADB (': 'adb_command_failed',
                'expected an empty': 'clean_install_precondition',
                'APK installation not confirmed': 'install_no_success',
                'APK could not be identified': 'installed_path_invalid',
                'installed APK differs': 'installed_hash_mismatch',
                'version code did not match': 'version_mismatch',
                'product state missing': 'state_missing',
            }
            for text,label in categories.items():
                if text in detail:return label
            return 'ui_or_device_check' if isinstance(exc,r12.Failure) else 'driver_error'

        def reopen(self,stage,*texts):
            self.sh('am','force-stop',self.pkg)
            self.sh('am','start','-n',self.pkg+'/com.trackingracing.AuroraActivity')
            return self.state(stage,*texts)

        def no_simulator(self,root,stage):
            content=self.content(root)
            hidden=('Treino OCR','Simulador de ofertas','Ler uma oferta no Vexo','OCR em outros apps')
            if any(baseline.norm(label) in content for label in hidden):
                raise r12.Failure(stage+': a simulator or OCR control is visible in the manual home')

        def next_step(self,stage):
            self.sh('input','keyevent','KEYCODE_BACK')
            self.tap(stage,'turno-next',self.pkg+':id/turno-next','Continuar',scroll=True)

        def revision(self,stage,var,version,replacing=False):
            path=Path(os.environ[var]); digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
            if not replacing and ('package:'+self.pkg) in self.sh('pm','list','packages',self.pkg).splitlines():
                raise r12.Failure('expected an empty disposable device')
            self.ev(stage+'-install-start','PASS')
            args=['-r'] if replacing else []
            answer=self.cmd('install',*args,'--streaming',str(path),timeout=170).decode()
            if 'Success' not in answer:raise r12.Failure('APK installation not confirmed')
            self.ev(stage+'-install-return','PASS')
            row=self.sh('pm','path',self.pkg).strip()
            match=re.fullmatch(r'package:(/[\w./=+~-]+/base\.apk)',row)
            if not match:raise r12.Failure('APK could not be identified')
            actual=self.sh('sha256sum',match[1],timeout=20).split()[0]
            if actual!=digest:raise r12.Failure('installed APK differs from QA file')
            pkg=self.sh('dumpsys','package',self.pkg,timeout=20)
            if not re.search(r'\bversionCode='+str(version)+r'\b',pkg):raise r12.Failure('version code did not match')
            self.ev(stage+'-installed','PASS')

        def open_rent(self,stage):
            self.tap(stage+'-plan','Rever meu plano',scroll=True)
            self.tap(stage+'-begin','Começar')
            self.tap(stage+'-work','Já rodo')
            self.tap(stage+'-rent','Alugado')
            self.state(stage+'-screen','Quanto custa o aluguel?',photo=False)

        def edit(self,root,id,label):
            fields=[]
            for node in root.iter('node'):
                if node.get('package')!=self.pkg or node.get('visible-to-user')=='false':continue
                rid=node.get('resource-id','').split('/')[-1]
                is_edit=node.get('class','').endswith(('EditText','AutoCompleteTextView')) or node.get('editable')=='true'
                if not is_edit and (rid!=id or node.get('focusable')!='true'):continue
                desc=baseline.norm(node.get('content-desc','') or node.get('hint',''))
                bounds=r12.bounds(node.get('bounds'))
                if bounds and (rid==id or desc==baseline.norm(label) or (desc.startswith(baseline.norm(label)+' ') and label!='99')):
                    fields.append((node,((bounds[0]+bounds[2])//2,(bounds[1]+bounds[3])//2)))
            return fields[0] if len(fields)==1 else None

        def fill(self,stage,id,label,value,fresh=False,prior_calibrated=False):
            try:
                _,key,(_,point)=self.product_observe(stage,lambda root:self.edit(root,id,label),seconds=9 if prior_calibrated else 22,scroll=not prior_calibrated)
            except r12.Failure:
                if not prior_calibrated:raise
                # Fixed 720x1280 QA-only frame from the original R17 screenshot.
                # Use only with matched old layout, screen size, section, and both field labels.
                expected=('Configurações','Consumo médio (km/L)','Preço por litro (R$)','Salvar valores')
                if self.sh('wm','size').strip().splitlines()[-1].split()[-1]!='720x1280':raise
                _,key=self.state('prior-fuel-layout',*expected,seconds=15,photo=False)
                point=(194,852)
                self.ev('prior-fuel-visual-calibration','PASS')
            self.act(key,point,stage)
            if not fresh:self.sh('input','keycombination','KEYCODE_CTRL_LEFT','KEYCODE_A')
            self.sh('input','text',value)

        def verify_field(self,stage,id,label,expected):
            def check(root):
                result=self.edit(root,id,label)
                if result is None:return None
                node,_=result
                return expected in ' '.join(node.get(k,'') for k in ('text','content-desc'))
            _,key,_=self.product_observe(stage,check,seconds=22,scroll=True)
            self.shot(stage)
            self.ev(stage,'PASS',xml=key+'.xml',png=stage+'.png')

    return Turno


if __name__=='__main__':
    sys.exit(driver(baseline.r12_module())().run())
