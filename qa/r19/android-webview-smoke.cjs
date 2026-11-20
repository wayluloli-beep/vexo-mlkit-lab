'use strict';
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {setTimeout: sleep} = require('node:timers/promises');
const adbPath = process.env.ADB;
const serial = 'emulator-5554', pkg = 'com.trackingracing.aurora';
const origin = 'https://appassets.androidplatform.net';
let port, ws, seq = 0, phase = 'startup';
const pending = new Map();

function adb(...args) {
  return execFileSync(adbPath, ['-s', serial, ...args], {timeout: 120000, encoding: 'utf8'}).trim();
}

function clean() {
  if (ws) { ws.close(); ws = null; }
  if (port) { try { adb('forward', '--remove', 'tcp:' + port); } catch (_) {} port = null; }
}

async function poll(fn, seconds=25) {
  const deadline = Date.now() + seconds*1000;
  let last;
  while (Date.now() < deadline) {
    try { const result = await fn(); if (result) return result; } catch (e) { last = e; }
    await sleep(260);
  }
  throw Error('timeout in ' + phase + (last ? ': ' + last.message : ''));
}

async function open() {
  clean();
  adb('shell', 'am', 'start', '-n', pkg + '/com.trackingracing.AuroraActivity');
  const pid = await poll(() => { const v=adb('shell','pidof',pkg); return /^\d+$/.test(v) && v; });
  port = adb('forward','tcp:0','localabstract:webview_devtools_remote_' + pid);
  assert.match(port, /^\d{1,5}$/);
  const target = await poll(async () => {
    const rsp = await fetch('http://127.0.0.1:' + port + '/json/list', {signal:AbortSignal.timeout(1800)});
    const items = await rsp.json();
    const pages = items.filter(p => p.type==='page' && p.url.startsWith(origin + '/aurora/'));
    return pages.length===1 && pages[0];
  }, 42);
  const remote = new URL(target.webSocketDebuggerUrl);
  assert.match(remote.pathname, /^\/devtools\/page\/[a-zA-Z0-9_-]+$/);
  ws = new WebSocket('ws://127.0.0.1:' + port + remote.pathname);
  await new Promise((resolve,reject)=>{
    const alarm = setTimeout(() => reject(Error('WebView Debug socket unavailable')), 7000);
    ws.addEventListener('open', () => {clearTimeout(alarm);resolve();}, {once:true});
    ws.addEventListener('error', () => {clearTimeout(alarm);reject(Error('WebView Debug socket error'));}, {once:true});
  });
  ws.addEventListener('message', ({data})=>{
    const reply = JSON.parse(data);
    const slot = pending.get(reply.id);
    if (!slot) return;
    clearTimeout(slot.alarm);
    pending.delete(reply.id);
    if (reply.error) slot.reject(Error(reply.error.message)); else slot.resolve(reply.result);
  });
}

function call(method, params) {
  const id=++seq;
  return new Promise((resolve,reject)=>{
    const alarm = setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},7000);
    pending.set(id,{resolve,reject,alarm});
    ws.send(JSON.stringify({id,method,params}));
  });
}
async function evaluate(expression) {
  const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:false});
  if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description || 'WebView evaluation failed');
  return result.result?.value;
}
const query=s => 'document.querySelector(' + JSON.stringify(s) + ')';
const visible=s => '('+query(s)+')?.getClientRects().length > 0';
const val=s => evaluate('('+query(s)+')?.value');
const text=s => evaluate('('+query(s)+')?.innerText');
const counts=()=>evaluate('window.VexoTurno.read(window.VexoTurnoStorage || localStorage)');
const expect=(a,b)=>assert.equal(a,b);
async function click(s) {
  await poll(()=>evaluate(visible(s)+' && !('+query(s)+').disabled'));
  await evaluate(query(s)+'.click()');
}
async function type(s,value) {
  await poll(()=>evaluate(visible(s)));
  await evaluate('(()=>{const field='+query(s)+'; field.focus(); field.select();})()');
  await call('Input.insertText',{text:value});
  expect(await val(s),value);
}
async function relaunch(selector) {
  clean();
  adb('shell','am','force-stop',pkg);
  await open();
  await poll(()=>evaluate(visible(selector)));
}
async function mark(name, fn) {
  phase=name;
  await fn();
  console.log('VEXO_WEBVIEW: '+name+' PASS');
}

async function run() {
  assert(adbPath && /^\//.test(adbPath),'expected the runner Android SDK adb');
  assert.equal(adb('shell','getprop','sys.boot_completed'),'1');
  assert.equal(adb('shell','settings','get','global','airplane_mode_on'),'1');
  const prior = process.argv[2], candidate = process.argv[3];
  await mark('r18-normal-entry-fuel-active-turn', async()=>{
    assert.match(adb('install',prior),/Success/);
    await open();
    if (await evaluate(visible('#opening-continue'))) await click('#opening-continue');
    await click('#entry-accept');
    await click('#entry-continue');
    await click('[data-action="enter-welcome"]');
    await click('nav [data-page="config"]');
    await type('#km','13,25');
    await click('#fuel button[type="submit"]');
    expect(await evaluate('window.VexoAndroidOcr.kmPerLiter()'),13.25);
    await click('nav [data-page="inicio"]');
    await click('#turno-action');
    await click('#turno-action');
    await type('#t-uber','150,50');
    expect((await counts()).active.draft.uber,'150,50');
    // A legacy build cannot retrofit an unflushed write. Prove the old copy
    // survived an orderly reopen before testing migration of persisted data.
    adb('shell','input','keyevent','KEYCODE_HOME');
    await sleep(8000);
    await relaunch('#turno-action');
    expect((await counts()).active.draft.uber,'150,50');
    clean();
  });
  await mark('r19-upgrade-retains-entry-fuel-turn-draft',async()=>{
    assert.match(adb('install','-r',candidate),/Success/);
    assert.match(adb('shell','dumpsys','package',pkg),/\bversionCode=6\b/);
    await open();
    await poll(()=>evaluate(visible('#h-inicio')));
    expect(await evaluate('window.VexoAndroidOcr.kmPerLiter()'),13.25);
    expect((await counts()).active.draft.uber,'150,50');
  });
  await mark('r19-real-plan-local-25-per-hour',async()=>{
    await click('#inicio [data-action="plano"]');
    await click('#screen [data-action="begin"]');
    await click('#screen [data-choice="yes"]');
    await click('#screen [data-choice="rent"]');
    await type('#plano-base','2600');
    await click('#screen form button[type="submit"]');
    await type('#plano-fuel','520');
    await click('#screen form button[type="submit"]');
    await type('#plano-goal','2080');
    await click('#screen form button[type="submit"]');
    await click('#plan-enter');
    await poll(()=>evaluate(visible('#turno-action')));
    expect(await evaluate('window.VexoAndroidOcr.hourlyGoalCents()'),2500);
    assert.match(await text('#goal-value'),/25,00/);
  });
  await mark('r19-turn-220-60-160-100km',async()=>{
    await click('#turno-action');
    expect(await val('#t-uber'),'150,50');
    await type('#t-nove','39,50');
    await type('#t-indrive','30');
    // No sleep before the forced stop on the new native writer.
    await relaunch('#turno-action');
    await click('#turno-action');
    expect(await val('#t-uber'),'150,50');
    expect(await val('#t-nove'),'39,50');
    expect(await val('#t-indrive'),'30');
    await click('#turno-payment summary');
    await type('#t-cash','65');
    await type('#t-pix','100');
    await click('#turno-next');
    await type('#t-fuel','45');
    await type('#t-extra','15');
    await click('#turno-next');
    await type('#t-km','100');
    await click('#turno-reserve summary');
    await type('#t-reserve-rate','0,25');
    await click('#turno-confirm');
    await poll(()=>evaluate(visible('#turno-last')));
    const {active,history}=await counts();
    expect(active,null);
    expect(history.length,1);
    const row=history[0];
    assert.deepEqual([row.received,row.spent,row.net,row.km,row.perKm,row.entries.indrive],[22000,6000,16000,100,160,3000]);
    assert.deepEqual([row.cashFlow.cash,row.cashFlow.pix,row.cashFlow.unclassified,row.cashFlow.reserve],[6500,10000,5500,2500]);
    assert.match(await text('#turno-last-values'),/220,00.*60,00.*160,00/);
    assert.match(await text('#turno-last-rates'),/1,60\/km/);
  });
  await mark('r19-force-stop-and-reopen-saves-turn-and-plan',async()=>{
    await relaunch('#turno-last');
    assert.match(await text('#turno-last-values'),/160,00/);
    expect((await counts()).history.length,1);
    expect(await evaluate('window.VexoAndroidOcr.hourlyGoalCents()'),2500);
    expect(await evaluate('window.VexoAndroidOcr.kmPerLiter()'),13.25);
    await click('#privacy-toggle');
    expect(await evaluate('document.documentElement.hasAttribute("data-vexo-values-hidden")'),true);
    await relaunch('#privacy-toggle');
    expect(await evaluate('document.documentElement.hasAttribute("data-vexo-values-hidden")'),true);
  });
}
run().catch(e=>{console.error('VEXO_WEBVIEW: '+phase+' FAIL '+e.message);process.exitCode=1;}).finally(clean);
