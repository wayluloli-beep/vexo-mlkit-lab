/* Testes de integração dos motores puros; não executa DOM. */
const fs=require('node:fs'),path=require('node:path');
const integration=async function(d,f,g){
const results=[];const test=async(name,fn)=>{try{await fn();results.push({name,pass:true})}catch(e){results.push({name,pass:false,error:e.message})}};
const near=(a,b)=>{if(typeof a!=="number"||!Number.isFinite(a)||Math.abs(a-b)>1e-8)throw Error(a+" != "+b)};
const eq=(a,b)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw Error(JSON.stringify(a)+" != "+JSON.stringify(b))};
const fuelCode=f.slice(f.indexOf("function normalize(rows)"),f.indexOf("function stats(a,c)"));
const fuel=new Function(fuelCode+"\nreturn {normalize,buildCycles};")();
const start=g.indexOf("const Core=(()=>{"),end=g.indexOf("})();",start)+5;
const core=new Function(g.slice(start,end)+"\nreturn Core;")();
const row=(id,day,odo,liters,price,full)=>[id,`2026-01-${day}T10:00:00`,odo,liters,price,"Gasolina",full,"Posto"];
const base=(fills=[],rides=[],expenses=[])=>({rides,fills,expenses,goals:{revenue:0,cash:0,reserve:.15},settings:{fuel:6.2,consumption:10,fixed:0},offer:null,seen:[]});
const env=state=>{const map=new Map([["vexo-data-v2",JSON.stringify(state)]]);const window={addEventListener(){},dispatchEvent(){}};let seq=0;new Function("localStorage","window","navigator","crypto","Event",d)({getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v)},window,{},{randomUUID:()=>`cross-${++seq}`},class{});return window.Vexo.invoke;};
async function cross(fills,expected,liters){const data=base(fills),a=env(data),rates=(await a("webState")).rates,fc=fuel.buildCycles(fuel.normalize(await a("dadosDashboardFuel"))),fin=core.normalize(await a("financeDados")).cycles;eq(fc.length,fin.length);eq(rates.cycles,fin.length);const km=fin.reduce((n,x)=>n+x.km,0);near(fc.reduce((n,x)=>n+x.cost,0)/km,expected);near(fin.reduce((n,x)=>n+x.cost,0)/km,expected);near(rates.fuel,expected);near(rates.eff,km/liters);near(fc.reduce((n,x)=>n+x.liters,0),liters);}
await test("Radar/Fuel/Finance: ciclo normal",()=>cross([row("F1","01",1000,40,6,true),row("F2","02",1400,40,6,true)],.6,40));
await test("Radar/Fuel/Finance: parcial",()=>cross([row("F1","01",1000,40,6,true),row("F2","02",1200,10,6,false),row("F3","03",1400,30,6,true)],.6,40));
await test("Radar/Fuel/Finance: odômetro legado repetido",()=>cross([row("F1","01",1000,40,6,true),row("F2","02",1000,10,6,true),row("F3","03",1400,30,6,true)],.6,40));
await test("Radar/Fuel/Finance: centavos e preço fracionado",()=>cross([row("F1","01",1000,40,6,true),row("F2","02",1200,1.23,5.678,false),row("F3","03",1400,2.34,5.678,true)],(6.98+13.29)/400,3.57));
await test("Radar/Fuel/Finance: dois ciclos ponderados",()=>cross([row("F1","01",1000,40,6,true),row("F2","02",1400,40,6,true),row("F3","03",1600,25,8,true)],440/600,65));
await test("Driver/Finance: receita e distância compartilhadas",async()=>{const a=env(base());let r=(await a("webAction","new")).ride;await a("webAction","accept",r.id);await a("webAction","finish",r.id);let driver=await a("dadosDashboard99"),fin=core.normalize(await a("financeDados")),s=(await a("webState")).summary;eq(driver.length,1);near(driver[0][7],s.gross);near(fin.finished[0].revenue,s.gross);near(fin.finished[0].km,s.km);});
await test("Finance: caixa, despesas e cobertura do combustível",async()=>{const fills=[row("F1","01",1000,40,6,true),row("F2","03",1400,40,6,true)];const rides=[["R1","finished","2026-01-02T10:00:00","2026-01-02T10:30:00",1800,20,"Paid by Company",50]];const expenses=[["D1","2026-01-02","Pedágio","Teste",10,2,"R1"]];const a=env(base(fills,rides,expenses));const s=core.stats(core.normalize(await a("financeDados")));near(s.revenue,50);near(s.fuelEst,12);near(s.opCost,8);near(s.result,30);near(s.cash,50-480-8);});
await test("Finance: sem ciclo não inventa lucro",async()=>{const rides=[["R1","finished","2026-01-02T10:00:00","2026-01-02T10:30:00",1800,20,"Paid by Company",50]];const a=env(base([],rides));eq(core.stats(core.normalize(await a("financeDados"))).result,null);});
return results;
};
const get=p=>fs.readFileSync(path.join(__dirname,p),'utf8');
integration(get('data.js'),get('fuel.html'),get('finance.html')).then(r=>{console.log(JSON.stringify(r,null,2));if(r.some(x=>!x.pass))process.exitCode=1;}).catch(e=>{console.error(e);process.exitCode=1;});
