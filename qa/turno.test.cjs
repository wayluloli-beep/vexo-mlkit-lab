const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const assets=path.join(process.env.VEXO_SOURCE_DIR||path.join(__dirname,'..','aurora'),'app/src/main/assets/aurora');
const hour=3600000;
function memory(map=new Map()) { return {getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)}; }
function core(){const ctx=vm.createContext({window:{}});vm.runInContext(fs.readFileSync(path.join(assets,'turno.js'),'utf8'),ctx);return ctx.window.VexoTurno;}
function plan(storage){const ctx=vm.createContext({window:{},localStorage:storage});const code=fs.readFileSync(path.join(assets,'onboarding.html'),'utf8').match(/<script id="vexo-gain-plan">([\s\S]*?)<\/script>/)[1];vm.runInContext(code,ctx);return ctx.window.VexoGainPlan;}

test('rascunho parcial sobrevive à reabertura, sem tocar no plano ativo nem gravar exemplos',()=>{
 const store=memory();const api=plan(store);api.saveProfile({goal:'2.000,00',fuel:'150,00'});
 assert.equal(api.saveDraft({goal:'2.500,00',fuel:'',offerValue:'16,70',type:'rent'}),true);
 const reopened=plan(store).restore({goal:'',fuel:'',offerValue:'outro'});
 assert.equal(reopened.goal,'2.500,00');assert.equal(reopened.fuel,'');assert.equal(reopened.offerValue,'outro');
 assert.equal(JSON.parse(store.getItem('vexo.gain-profile.v1')).goal,'2.000,00');
 assert.equal(api.saveProfile({goal:'2.500,00',fuel:'200,00'}),true);
 assert.equal(api.hasDraft(),false);
});

test('conta em centavos e reinício do turno. 220 − 60 = 160, 8h e 100km',()=>{
 const api=core(),store=memory(),now=1770000000000;
 const started=api.begin(store,now);assert.equal(started.active.startedAt,now);
 const reopened=core();assert.equal(reopened.read(store).active.startedAt,now);
 reopened.begin(store,now+hour);
 assert.equal(reopened.read(store).active.startedAt,now);
 const item=reopened.close(store,{uber:'150,50',nove:'69,50',outros:'',fuel:'45,00',extra:'15',km:'100'},now+8*hour);
 assert.equal(item.received,22000);assert.equal(item.spent,6000);assert.equal(item.net,16000);
 assert.equal(item.perHour,2000);assert.equal(item.perKm,160);
 assert.equal(reopened.read(store).active,null);assert.equal(reopened.read(store).history.length,1);
 assert.equal(reopened.today(reopened.read(store),now+8*hour).net,16000);
});

test('sem km não inventa média; valor zero é válido e prejuízo não some',()=>{
 const api=core(),store=memory(),now=1770000000000;
 api.begin(store,now);
 const item=api.close(store,{uber:'0',fuel:'12,50',km:''},now+2*hour);
 assert.equal(item.net,-1250);assert.equal(item.perHour,-625);assert.equal(item.perKm,null);
 assert.equal(item.km,null);
});

test('entrada inválida, relógio invertido e toque duplo não alteram o histórico',()=>{
 const api=core(),store=memory(),now=1770000000000;api.begin(store,now);
 for(const data of [{},{uber:'-20'},{uber:'1.2.3,45'},{uber:'30',km:'-10'},{uber:'30',extra:'1e3'}])
   assert.throws(()=>api.close(store,data,now+hour));
 assert.throws(()=>api.close(store,{uber:'30'},now-1));
 const first=api.close(store,{uber:'1.234,56',extra:'34,56'},now+hour);
 assert.equal(first.net,120000);
 assert.throws(()=>api.close(store,{uber:'10'},now+hour));
 assert.equal(api.read(store).history.length,1);
});

test('falha de escrita ou armazenamento ilegível não apaga turno',()=>{
 const api=core(),store=memory(),now=1770000000000;api.begin(store,now);
 const volatile={...store,setItem:()=>{throw Error('quota');}};
 assert.throws(()=>api.close(volatile,{uber:'30'},now+hour));
 assert.equal(api.read(store).active.startedAt,now);
 store.setItem(api.key,'bad-json');
 assert.throws(()=>api.begin(store,now));assert.equal(store.getItem(api.key),'bad-json');
});

test('Android manda o perfil já aceito à Central, sem rota pro simulador',()=>{
 const script=fs.readFileSync(path.join(assets,'index.html'),'utf8').match(/<script id="vexo-startup">([\s\S]*?)<\/script>/)[1];
 const key='vexo.entry.sequence.x4',disclosure='vexo.entry.disclosure.v1';
 function route(phase,accepted) {
   const nav=[];
   const localStorage=memory(new Map([[key,phase],[disclosure,accepted?'vexo-termos-minuta-2026-11-20':null]]));
   vm.runInNewContext(script,{localStorage,location:{replace:p=>nav.push(p)},matchMedia:()=>({matches:true})});
   return nav;
 }
 assert.deepEqual(route('app',true),['./central.html']);
 assert.deepEqual(route('interview',true),['./onboarding.html']);
 assert.deepEqual(route('app',false),['./onboarding.html']);
 assert.deepEqual(route(null,false),['./onboarding.html']);
});

test('falha ao salvar perfil não ativa meta; falha nativa restaura perfil anterior e deixa rascunho',()=>{
 const storage=memory(),key='vexo.gain-profile.v1';const api=plan(storage);
 api.saveProfile({goal:'anterior'});api.saveDraft({goal:'novo'});
 const blocked=plan({...storage,setItem(){throw Error('quota');}});
 let writes=0;assert.equal(blocked.commitProfile({goal:'novo'},2500,{setHourlyGoalCents(){writes++;return true;}}),false);assert.equal(writes,0);
 assert.equal(api.commitProfile({goal:'novo'},2500,{setHourlyGoalCents(){return false;}}),false);
 assert.equal(JSON.parse(storage.getItem(key)).goal,'anterior');assert.equal(api.hasDraft(),true);
 assert.equal(api.commitProfile({goal:'novo'},2500,{setHourlyGoalCents(){return true;}}),true);
 assert.equal(api.hasDraft(),false);
});
