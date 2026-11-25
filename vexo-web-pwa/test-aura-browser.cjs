const {chromium}=require('playwright'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),fixture=require('./test-aura-fixture.cjs');
const date=d=>new Date(d-d.getTimezoneOffset()*60000).toISOString().slice(0,10);
(async()=>{
 const server=spawn(process.execPath,[__dirname+'/server.cjs'],{stdio:'ignore'});let browser;
 try{
  for(let i=0;i<30;i++){try{const r=await fetch('http://127.0.0.1:8765/');if(r.ok)break}catch{}await new Promise(r=>setTimeout(r,200));}
  browser=await chromium.launch({headless:true});
  const ctx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2});
  await ctx.addInitScript(()=>{window.__voiceCalls=[];window.VexoVoice={speak:x=>window.__voiceCalls.push(x),stop(){},listen(){window.__voiceCalls.push('listen')}};});
  const errors=[],requests=[];await ctx.route('https://vexo-aura-flash-bridge-xs69.onrender.com/aura/v3',async route=>{
   const headers={'access-control-allow-origin':'*','access-control-allow-methods':'POST,OPTIONS','access-control-allow-headers':'content-type'};
   if(route.request().method()==='OPTIONS')return route.fulfill({status:204,headers,body:''});
   const b=route.request().postDataJSON();requests.push(b);assert.equal(b.protocol,3);assert.ok(!('history'in b)&&!('finance'in b));
   if(b.question==='Como está o panorama?')return route.fulfill({status:200,headers,contentType:'application/json',body:JSON.stringify({protocol:3,text:JSON.stringify({intent:'detalhes',period:'hoje',platform:'todos',metrics:[],compareMetric:'corridas',reply:''})})});
   return route.fulfill({status:504,headers,contentType:'application/json',body:JSON.stringify({error:'gemini_timeout'})});
  });
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
  const frame=async id=>(await page.locator('#'+id).elementHandle()).contentFrame();
  const swipe=async(from,to)=>{const f=await frame(from);await f.evaluate(()=>{const b=document.body,t=(x)=>new Touch({identifier:1,target:b,clientX:x,clientY:200});b.dispatchEvent(new TouchEvent('touchstart',{bubbles:true,touches:[t(330)],changedTouches:[t(330)]}));b.dispatchEvent(new TouchEvent('touchend',{bubbles:true,cancelable:true,touches:[],changedTouches:[t(70)]}));});await page.locator('#'+to).waitFor({state:'visible'});await page.waitForFunction(id=>{const f=document.getElementById(id);return f.contentDocument?.readyState==='complete'&&f.contentWindow.location.pathname.endsWith(id+'.html')},to);};
  const goAura=async()=>{for(const [from,to] of [['generator','driver'],['driver','fuel'],['fuel','finance'],['finance','aura']])await swipe(from,to);return frame('aura')};
  await page.goto('http://127.0.0.1:8765/');await page.waitForFunction(()=>document.querySelector('#generator').contentDocument?.readyState==='complete');
  const today=new Date(),y=new Date(today);y.setDate(y.getDate()-1);
  await page.evaluate(s=>localStorage.setItem('vexo-data-v2',JSON.stringify(s)),fixture(date(today),date(y)));
  let a=await goAura();let passed=0;
  const ask=async(q,pattern)=>{const before=await a.locator('.msg.user').count();await a.locator('#question').fill(q);await a.locator('#send').click();await a.waitForFunction(n=>document.querySelectorAll('.msg.aura').length>n,before,{timeout:15000});const last=await a.locator('.msg.aura').last().innerText();assert.match(last,pattern,q+' => '+last);passed++;return last;};
  await ask('Quanto ganhei hoje?',/209,20/);
  await ask('Detalha mais',/Uber: 4; 99: 5/);
  await ask('99 ou Uber ?',/Uber 4 \| 99 5/);
  await ask('Quantos km em corrida eu rodei?',/103,38 km/);
  await ask('Tempo de corrida?',/3h 00min/);
  await ask('E na 99?',/99: 1h 45min/);
  await ask('E ontem?',/99: 0h 00min/);
  await ask('E a outra?',/Uber: 0h 30min/);
  assert.equal(requests.length,0);passed++;
  await ask('Quanto ganhei e quantos km rodei hoje?',/209,20[\s\S]*103,38/);
  await ask('Como está o panorama?',/209,20/);assert.equal(requests[0].context.intent,'multi');passed++;
  await ask('E o que você acha disso?',/HTTP 504/);
  await ask('Tempo de corrida?',/3h 00min/);
  await a.locator('#voice').click();await ask('Quanto ganhei hoje?',/209,20/);assert.ok(await a.evaluate(()=>window.__voiceCalls.some(x=>x.includes('209,20'))));passed++;
  await a.locator('#mic').click();assert.ok(await a.evaluate(()=>window.__voiceCalls.includes('listen')));await a.evaluate(()=>window.vexoAuraRecognized('Quantos km?'));assert.equal(await a.locator('#question').inputValue(),'Quantos km?');passed+=2;
  const old=await a.locator('.msg.aura').count();await page.reload();await page.waitForFunction(()=>document.querySelector('#generator').contentDocument?.readyState==='complete');a=await goAura();assert.equal(await a.locator('.msg.aura').count(),old);passed++;
  await ask('E na Uber?',/Uber: R\$[\s\u00a0]*99,00/);
  await ask('Quais informações vc tem acesso das corridas?',/Início: 9\/9/);
  await ask('Quais horários foram feitos as corridas?',/08:00[\s\S]*16:18/);
  await ask('Horário da corrida e o dia',/08:00[\s\S]*16:18/);
  await ask('E na Uber?',/de 4/);
  await ask('Qual foi a corrida mais cara hoje?',/30,00/);
  assert.equal(requests.length,2);passed++;
  assert.ok(await a.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);passed+=2;
  console.log('Browser mobile: '+passed+' verificações aprovadas; '+requests.length+' chamadas simuladas ao Gemini; navegação, UI, voz simulada e persistência.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
