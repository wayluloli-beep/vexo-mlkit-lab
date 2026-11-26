const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const mem=new Map(),window={addEventListener(){},dispatchEvent(){}},ctx=vm.createContext({window,localStorage:{getItem:k=>mem.get(k)??null,setItem:(k,v)=>mem.set(k,v)},navigator:{},console,Event:class{},crypto:require('node:crypto').webcrypto});
vm.runInContext(fs.readFileSync('vexo-web-pwa/data.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('vexo-web-pwa/aura-core.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('vexo-web-pwa/aura-dashboard-context.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('vexo-web-pwa/aura-dash-tools.js','utf8'),ctx);
(async()=>{const d=await window.Vexo.invoke('auraDados'),r=d.finance;assert(r.rides.length>=420);assert(r.fills.length>=10);assert(r.expenses.length>=50);assert(r.rides.every(x=>x[0].startsWith('LAB-')));await window.Vexo.invoke('backupExport');ctx.bundle=d;
const p=vm.runInContext('AuraDashboardContext.project(bundle,AuraCore)',ctx);assert.equal(p.drive.corridas_finalizadas,12);assert(p.drive.faturamento_bruto_brl>0);assert(p.finance.meta_mensal_brl>0);
const query=vm.runInContext('AuraDashboardContext.localWire("Quantas corridas eu fiz?",AuraCore)',ctx);assert.equal(query.data_queries[0].metric,'RIDE_COUNT');
const before=mem.get('vexo-data-v2');await window.Vexo.invoke('auraDados');assert.equal(mem.get('vexo-data-v2'),before);
const questions=[
['Quantas corridas fiz hoje?',/12/],['Quanto faturei hoje?',/340,98/],
['Qual meu ticket médio hoje?',/28,42/],['Qual o melhor horário nesta semana?',/corridas/],
['Mapa de calor de corridas nesta semana',/corridas/],['Quais os melhores dias este mês?',/corridas/],
['Quantos dias abasteci neste mês?',/dias com abastecimento/],['Qual o posto mais barato neste mês?',/Posto fictício/],
['Quantos litros abasteci hoje?',/22,37/],['Quanto gastei com combustível hoje?',/144,06/],
['Qual meu consumo medido hoje?',/km\/L/],['Qual o custo por km de combustível hoje?',/Custo\/km/],
['Quais os ciclos completos este mês?',/ciclos fechados/],['Quantos abastecimentos por semana?',/compras\/semana/],
['Mapa de calor de abastecimentos este mês',/Horário da compra/],['Quais despesas por categoria hoje?',/Manutenção/],
['Qual a cobertura de combustível hoje?',/Cobertura/],['Qual a meta de saldo?',/3.500,00/],
['Qual a reserva por km?',/0,15/],['Coloca 300',/ganho de corridas, combustível/],
['Combustível',/Nenhuma alteração/],['Registra 300 de combustível',/Nenhum dado foi alterado/]];
ctx.readData=()=>window.Vexo.invoke('auraDados');
let passed=0;for(const [q,re] of questions){ctx.question=q;const got=await vm.runInContext('AuraDashTools.handle(question,{readData})',ctx);if(!got||!re.test(got.text)){console.error('FAIL',q,got?.text);continue;}passed++;console.log('DASH_PASS '+q+' | '+got.text.slice(0,120));}
console.log('DASH_RESULT '+passed+'/'+questions.length);assert.equal(passed,questions.length);assert.equal(mem.get('vexo-data-v2'),before);

ctx.testNow=new Date(2026,10,26,12);
const expectedOctober=r.rides.filter(x=>x[1]==='finished'&&x[2].startsWith('2026-10')).reduce((a,x)=>a+x[7],0);
const expectedOctoberText=expectedOctober.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
ctx.question='Eu fiz 16 mil reais?';
let actual=await vm.runInContext('AuraDashTools.handle(question,{readData,now:testNow})',ctx);
assert(actual.text.includes('histórico completo')&&actual.text.includes('Neste mês'),actual.text);
console.log('HISTORY_PASS '+actual.text);
ctx.question='E no mês anterior?';
actual=await vm.runInContext('AuraDashTools.handle(question,{readData,now:testNow})',ctx);
assert(actual.text.includes('01/10/2026 a 31/10/2026')&&actual.text.includes(expectedOctoberText),actual.text+' vs '+expectedOctoberText);
console.log('HISTORY_PASS '+actual.text);
ctx.question='Quanto gastei com combustível em outubro de 2026?';
actual=await vm.runInContext('AuraDashTools.handle(question,{readData,now:testNow})',ctx);
const expectedFuel=r.fills.filter(x=>x[1].startsWith('2026-10')).reduce((a,x)=>a+Math.round((x[3]*x[4]+Number.EPSILON)*100)/100,0);
assert(actual.text.includes(expectedFuel.toLocaleString('pt-BR',{style:'currency',currency:'BRL'})),actual.text);
console.log('HISTORY_PASS '+actual.text);
ctx.question='E neste mês?';actual=await vm.runInContext('AuraDashTools.handle(question,{readData,now:testNow})',ctx);
assert(actual.text.includes('01/11/2026 a 26/11/2026')&&actual.text.includes('abastecimentos'),actual.text);
console.log('HISTORY_PASS '+actual.text);
ctx.question='Quantas corridas fiz em outubro de 2026?';actual=await vm.runInContext('AuraDashTools.handle(question,{readData,now:testNow})',ctx);
assert(actual.text.includes(String(r.rides.filter(x=>x[1]==='finished'&&x[2].startsWith('2026-10')).length)),actual.text);
console.log('HISTORY_PASS '+actual.text);
ctx.question='E no mês anterior?';ctx.history=[{role:'user',text:'Eu fiz 16 mil reais?'}];
// Emulate a fresh module (as on reload); last user question restores the metric.
const fresh=vm.createContext({window,console,readData:ctx.readData,testNow:ctx.testNow,question:ctx.question,history:ctx.history});
for(const file of ['aura-core.js','aura-dashboard-context.js','aura-dash-tools.js'])vm.runInContext(fs.readFileSync('vexo-web-pwa/'+file,'utf8'),fresh);
actual=await vm.runInContext('AuraDashTools.handle(question,{readData,now:testNow,history})',fresh);
assert(actual.text.includes(expectedOctoberText),actual.text);
console.log('HISTORY_PASS reload '+actual.text);
console.log('HISTORY_RESULT 6/6');assert.equal(mem.get('vexo-data-v2'),before);

console.log('LAB_SEED_CHECK '+JSON.stringify({rides:r.rides.length,finished:r.rides.filter(x=>x[1]==='finished').length,fills:r.fills.length,expenses:r.expenses.length,today:p,retained:true}));})().catch(e=>{console.error(e);process.exitCode=1;});