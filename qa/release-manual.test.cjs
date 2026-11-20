const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const src=path.join(process.env.VEXO_SOURCE_DIR||path.join(__dirname,'..','aurora'),'app/src/main');
const dir=path.join(src,'assets','aurora');
const get=name=>fs.readFileSync(path.join(dir,name),'utf8');

test('manual product ships no ride fixtures or demo offer entry',()=>{
 const manifest=fs.readFileSync(path.join(src,'AndroidManifest.xml'),'utf8');
 assert.doesNotMatch(manifest,/Simulador99Activity|ScreenCaptureService|SYSTEM_ALERT_WINDOW|FOREGROUND_SERVICE_MEDIA_PROJECTION/);
 assert.doesNotMatch(get('index.html')+get('central.html')+get('onboarding.html'),/99Pop|Aceitar por|Oferta simulada|Ler uma oferta no Vexo|data-action="externo"/);
 for(const p of ['../simulador99.html','../lab99-os-asco.js','referencias-99.html','overlay-r12.html'])assert.equal(fs.existsSync(path.join(dir,p)),false,p);
 assert.match(get('central.html'),/id="turno-action"[^>]*>Iniciar turno/);
});

test('closure presents gains, expenses, km and review once each, with matching assets',()=>{
 const html=get('central.html');
 for(const name of ['turno.js','turno-ui.js','central.js','product-flags.js','feedback.js']){
  assert.ok(html.includes(`src="${name}"`));new vm.Script(get(name));
 }
 const steps=[...html.matchAll(/<fieldset data-turn-step="(\d)"[^>]*>([\s\S]*?)<\/fieldset>/g)];
 assert.deepEqual(steps.map(i=>i[1]),['1','2','3']);
 assert.match(steps[0][2],/name="uber"[\s\S]*name="nove"/);
 assert.match(steps[1][2],/name="fuel"[\s\S]*name="extra"/);
 assert.match(steps[2][2],/name="km"[\s\S]*Ver a conta/);
 assert.doesNotMatch(steps[1][2],/name="km"/);
});

test('cost examples never write the active profile or meta even if the form is complete',()=>{
 const html=get('onboarding.html'),start=html.indexOf('planEnter.onclick='),end=html.indexOf('window.addEventListener("vexo:android-back"',start);
 assert.ok(start>=0&&end>start);
 const callbacks={rate:0,commit:0};const planEnter={};const routes=[];
 const ctx={planEnter,busy:false,page:'plan',exampleOnly:true,entryDisclosure:{hasAccepted:()=>true},tally:()=>({}),s:{},
   window:{VexoAndroidOcr:{},VexoGainPlan:{fromTally:()=>{callbacks.rate++;return 2500;},activate:()=>{callbacks.commit++;return true;},saveProfile:()=>true,commitProfile:()=>{callbacks.commit++;return true;}}},
   localStorage:{setItem(){}},launchSequenceKey:'key',location:{replace:x=>routes.push(x)}};
 vm.runInNewContext(html.slice(start,end),ctx);planEnter.onclick();
 assert.deepEqual(callbacks,{rate:0,commit:0});assert.deepEqual(routes,['./index.html']);
});
