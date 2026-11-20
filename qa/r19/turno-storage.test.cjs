const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {join}=require('node:path');
const path=join(process.env.VEXO_SOURCE_DIR || join(__dirname,'../aurora'),'app/src/main/assets/aurora');
const key='vexo.turno-manual.v1';
const old=JSON.stringify({active:{startedAt:100,draft:{uber:'150,50'}},history:[]});
function mount(native, legacy = old) {
  const local={getItem:k=>k===key?legacy:null,setItem:(k,v)=>{if(k===key)legacy=v;}};
  const ctx=vm.createContext({window:{VexoAndroidOcr:native},localStorage:local});
  for(const name of ['turno.js','turno-storage.js'])vm.runInContext(fs.readFileSync(join(path,name),'utf8'),ctx);
  return {core:ctx.window.VexoTurno, store:ctx.window.VexoTurnoStorage || local, local};
}
test('real Android writes are confirmed before updating draft and history and replace the legacy browser copy',()=>{
  let disk='', commit=true;
  const native={readManualTurn:()=>disk,writeManualTurn:raw=>{if(commit)disk=raw;return commit;}};
  let app=mount(native);
  assert.equal(app.core.read(app.store).active.draft.uber,'150,50');
  app.core.saveDraft(app.store,{uber:'150,50',nove:'69,50',fuel:'60',km:'100'});
  assert.equal(app.local.getItem(key),old);
  app=mount(native,null);
  assert.equal(app.core.read(app.store).active.draft.nove,'69,50');
  commit=false;
  assert.throws(()=>app.core.close(app.store,{uber:'150,50',nove:'69,50',fuel:'60',km:'100'},3600100),/armazenamento/);
  assert.equal(app.core.read(app.store).history.length,0);
  commit=true;
  app.core.close(app.store,{uber:'150,50',nove:'69,50',fuel:'60',km:'100'},3600100);
  app=mount(native,null);
  const row=app.core.read(app.store).history[0];
  assert.equal(row.net,16000);
  assert.equal(row.perKm,160);
  assert.equal(row.perHour,16000);
});
test('native read errors never fall back to the potentially stale legacy turn',()=>{
  const app=mount({readManualTurn:()=>null,writeManualTurn:()=>true});
  assert.throws(()=>app.core.read(app.store),/armazenamento/);
});
test('browser preview can still run without an Android bridge',()=>{
  const app=mount(undefined);
  app.core.saveDraft(app.store,{uber:'12,50'});
  assert.equal(JSON.parse(app.local.getItem(key)).active.draft.uber,'12,50');
});
