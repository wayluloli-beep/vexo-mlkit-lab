const {chromium}=require('playwright'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),fs=require('node:fs'),fixture=require('./test-aura-fixture.cjs');
(async()=>{const server=spawn(process.execPath,[__dirname+'/server.cjs'],{stdio:'ignore'});let browser;
try{
 for(let i=0;i<30;i++){try{if((await fetch('http://127.0.0.1:8765/')).ok)break}catch{}await new Promise(r=>setTimeout(r,200));}
 browser=await chromium.launch({headless:true});
 const ctx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,acceptDownloads:true});
 const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8765/mobile-original.html');
 await page.evaluate(x=>localStorage.setItem('vexo-data-v2',JSON.stringify(x)),fixture());await page.reload();
 await page.locator('summary').filter({hasText:'Parâmetros de teste e armazenamento'}).click();
 const dl=page.waitForEvent('download');await page.locator('#backup-export').click();const file=await dl;const text=fs.readFileSync(await file.path(),'utf8');
 const b=JSON.parse(text);assert.equal(b.format,'VEXO-backup');assert.equal(b.data.rides.length,10);
 await page.locator('#backup-file').setInputFiles({name:'backup.json',mimeType:'application/json',buffer:Buffer.from(text)});
 await page.locator('#backup-summary').getByText('10 corridas',{exact:false}).waitFor();assert.ok(await page.locator('#backup-restore').isDisabled());
 const fresh=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const dest=await fresh.newPage();dest.on('pageerror',e=>errors.push(e.message));
 await dest.goto('http://127.0.0.1:8765/mobile-original.html');await dest.locator('summary').filter({hasText:'Parâmetros de teste e armazenamento'}).click();
 await dest.locator('#backup-file').setInputFiles({name:'backup.json',mimeType:'application/json',buffer:Buffer.from(text)});
 await dest.locator('#backup-summary').getByText('Pronto para restaurar',{exact:false}).waitFor();assert.ok(await dest.locator('#backup-restore').isEnabled());dest.once('dialog',d=>d.accept());await dest.locator('#backup-restore').click();
 await dest.locator('#backup-result').getByText('Backup restaurado.',{exact:false}).waitFor();
 const copied=await dest.evaluate(()=>Vexo.invoke('financeDados'));assert.deepEqual(copied.rides,b.data.rides);assert.deepEqual(copied.fills,b.data.fills);assert.deepEqual(copied.expenses,b.data.expenses);
 await dest.reload();assert.equal(await dest.evaluate(async()=> (await Vexo.invoke('financeDados')).rides.length),10);
 assert.deepEqual(errors,[]);console.log('Backup navegador: exportacao, arquivo selecionado, bloqueio, restauracao e persistencia aprovados.');
}finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});