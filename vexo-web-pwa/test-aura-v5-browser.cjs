const {chromium}=require('playwright'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),fixture=require('./test-aura-fixture.cjs');
(async()=>{const server=spawn(process.execPath,[__dirname+'/server.cjs'],{stdio:'ignore'});let browser;try{
 for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:8765/')).ok)break}catch{}await new Promise(r=>setTimeout(r,150))}
 browser=await chromium.launch({headless:true});const ctx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 await ctx.addInitScript(()=>{window.__voice=[];window.VexoVoice={speak:x=>window.__voice.push(x),stop:()=>window.__voice.push('STOP'),listen:id=>{window.__listen=id},copyDebug:x=>window.__copy=x};});
 const requests=[],errors=[];let retry=0;
 await ctx.route('https://vexo-aura-flash-bridge-xs69.onrender.com/aura/v5',async route=>{
 const headers={'access-control-allow-origin':'*','access-control-allow-methods':'POST,OPTIONS','access-control-allow-headers':'content-type'};
 if(route.request().method()==='OPTIONS')return route.fulfill({status:204,headers,body:''});
 const b=route.request().postDataJSON();requests.push(b);assert.deepEqual(Object.keys(b).sort(),['attempt','context','protocol','question','request_id']);assert.equal(b.protocol,5);
 const respond=(plan,status=200)=>route.fulfill({status,headers,contentType:'application/json',body:JSON.stringify(status===200?{protocol:5,plan}:{error:'unavailable'})});
 const sim=(fare_brl,distance_km,duration_min)=>({intent:'SIMULATE_RIDE',ride_simulation:{fare_brl,distance_km,duration_min,ride_platform:'UNKNOWN'}});
 if(b.question==='Simula 30 reais 12 km 25 min')return respond(sim(30,12,25));
 if(b.question==='E 15 km?'){assert.equal(b.context.active_ride_simulation.fare_brl,30);return respond(sim(30,15,25))}
 if(b.question==='E por 35?')return respond({intent:'CLARIFY',clarification_reason:'AMBIGUOUS_UNIT'});
 if(['Reais','Em reais.','Minutos','km'].includes(b.question))return respond({intent:'OUT_OF_SCOPE'});
 if(b.question==='Falha')return respond(null,503);
 if(b.question==='Recupera'&&retry++===0)return respond(null,503);
 if(b.question==='Recupera')return respond(sim(30,15,25));
 if(b.question==='Resposta atrasada'){await new Promise(r=>setTimeout(r,1800));try{await respond(sim(99,22,25))}catch{}return}
 if(b.question==='Contrato inválido')return respond({...sim(30,12,25),conceptual_topic:'x'});
 if(b.question==='Quanto ganhei hoje?'){const day=new Date().toLocaleDateString('en-CA');return respond({intent:'QUERY_DATA',data_queries:[{domain:'FINANCE',metric:'GROSS_REVENUE',start_date:day,end_date:day,query_platform:'ALL'}]})}
 return respond({intent:'OUT_OF_SCOPE'});
 });
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8765/aura.html');
 const today=new Date().toLocaleDateString('en-CA'),y=new Date();y.setDate(y.getDate()-1);
 await page.evaluate(s=>localStorage.setItem('vexo-data-v2',JSON.stringify(s)),fixture(today,y.toLocaleDateString('en-CA')));
 let n=0;const ask=async(q,pattern)=>{await page.locator('#question').fill(q);await page.locator('#send').click();await page.waitForFunction(()=>!document.querySelector('#send').disabled);assert.match(await page.locator('.msg.aura').last().innerText(),pattern);n++};
 const memory=()=>page.evaluate(()=>localStorage.getItem('vexo-aura-session-v5'));
 await ask('Simula 30 reais 12 km 25 min',/Margem estimada/);await ask('E 15 km?',/15 km/);const prior=await memory();
 const beforeGuard=requests.length;await ask('E por 35?',/unidade/);assert.equal(await memory(),prior);assert.equal(requests.length,beforeGuard);n++;
 const count=requests.length;await ask('Em reais.',/35,00 · 15 km · 25 min/);assert.equal(requests.length,count);n++;
 assert.equal(JSON.parse(await memory()).active_ride_simulation.fare_brl,35);n++;
 await ask('Simula 30 reais 12 km 25 min',/Margem estimada/);await ask('E 15 km?',/15 km/);assert.equal(await memory(),prior);
 await ask('E por 35?',/unidade/);
 await ask('Falha',/Rede instável/);assert.equal(await memory(),prior);assert.equal(requests.filter(x=>x.question==='Falha').length,2);n++;
 const beforeUnit=requests.length;await ask('Reais',/Qual valor/);assert.equal(await memory(),prior);assert.equal(requests.length,beforeUnit);n++;
 await ask('E por 35?',/unidade/);const voiceCount=requests.length;await page.locator('#mic').click();await page.evaluate(()=>window.vexoAuraRecognized('Reais.',window.__listen));await page.waitForFunction(()=>!document.querySelector('#send').disabled);assert.equal(requests.length,voiceCount);assert.equal(JSON.parse(await memory()).active_ride_simulation.fare_brl,35);n++;
 await ask('Simula 30 reais 12 km 25 min',/Margem estimada/);await ask('E 15 km?',/15 km/);
 await ask('Recupera',/Margem estimada/);assert.equal(requests.filter(x=>x.question==='Recupera').length,2);n++;
 await ask('Contrato inválido',/Não consegui validar/);assert.equal(await memory(),prior);n++;
 await ask('Quanto ganhei hoje?',/209,20/);
 const original=await memory(),before40=requests.length;await ask('E por 40?',/unidade/);assert.equal(await memory(),original);assert.equal(requests.length,before40);n++;
 await ask('Minutos.',/30,00 · 15 km · 40 min/);assert.equal(requests.length,before40);assert.equal(JSON.parse(await memory()).active_ride_simulation.duration_min,40);n++;
 const before50=requests.length,after40=await memory();await ask('E por 50?',/unidade/);assert.equal(requests.length,before50);assert.equal(await memory(),after40);n++;
 await ask('Quanto ganhei hoje?',/209,20/);assert.equal(requests.length,before50+1);const afterFinance=await memory();await ask('Reais.',/Qual valor/);assert.equal(requests.length,before50+1);assert.equal(await memory(),afterFinance);n++;
 await ask('Simula 30 reais 12 km 25 min',/Margem estimada/);await ask('E 15 km?',/15 km/);
 await page.locator('#question').fill('Resposta atrasada');await page.locator('#send').click();await page.waitForFunction(()=>document.querySelector('#send').disabled);
 await page.locator('#mic').click();await page.evaluate(()=>window.vexoAuraRecognized('E 15 km?',window.__listen));await page.waitForFunction(()=>!document.querySelector('#send').disabled);await page.waitForTimeout(1900);
 assert.match(await page.locator('.msg.aura').last().innerText(),/15 km/);assert.ok(!await page.locator('.msg.aura').filter({hasText:'99,00 · 22'}).count());n++;
 const logs=await page.evaluate(()=>JSON.parse(window.vexoAuraDebugLogs()));assert.ok(logs.some(x=>x.status_rede==='LOCAL_CLARIFICATION'&&x.request_timing.length===0));assert.ok(logs.some(x=>x.status_rede==='CANCELED'));assert.ok(logs.some(x=>x.texto_stt==='E 15 km?'&&x.status_rede==='OK'));assert.ok(await page.evaluate(()=>window.__voice.includes('STOP')&&window.__voice.some(x=>x.includes('Margem estimada'))));n+=3;
 await page.reload();assert.equal(JSON.parse(await memory()).active_ride_simulation.distance_km,15);n++;
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);n+=2;
 console.log('Mobile v5 browser: '+n+' checks passed; upstream mocked; no physical STT/TTS');
 }finally{if(browser)await browser.close();server.kill()}})().catch(e=>{console.error(e);process.exitCode=1});