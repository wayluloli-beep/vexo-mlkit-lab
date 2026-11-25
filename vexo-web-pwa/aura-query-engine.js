/* Architecture experiment: typed read-only plans, no language heuristics in execution. */
const AuraQueryEngine=(()=>{
const check=(x,m='Plano inválido')=>{if(!x)throw Error(m);return x},obj=x=>x&&typeof x==='object'&&!Array.isArray(x);
const keys=(x,ks)=>check(obj(x)&&Object.keys(x).every(k=>ks.includes(k)),'Campo não autorizado');
const one=(x,ks)=>{check(ks.includes(x),'Opção inválida: '+x);return x};
const num=(x,min,max)=>{check(typeof x==='number'&&Number.isFinite(x)&&x>=min&&x<=max,'Número inválido');return x};
const int=(x,min,max)=>{num(x,min,max);check(Number.isInteger(x));return x};
const day=x=>{check(typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x),'Data inválida');const d=new Date(x+'T00:00:00Z');check(Number.isFinite(+d)&&d.toISOString().slice(0,10)===x,'Data inválida');return x};
const round=x=>Math.round((x+Number.EPSILON)*100)/100;
const metrics=['valor','km','duracao','embarque_km','passageiro_km','combustivel','reserva','fixo','resultado','nota','valor_km','valor_hora'];
const fields=['dia','inicio','fim','plataforma','situacao','origem','destino',...metrics];
const periods=['hoje','ontem','semana','quinze','mes','trinta','total'];
const concepts={faturamento:'Faturamento é receita bruta antes dos custos.',lucro:'Resultado operacional desconta combustível consumido e despesas operacionais; depende da cobertura dos registros.',caixa:'Caixa é dinheiro que entrou menos pagamentos; não é lucro.',jornada:'Tempo em corridas não equivale à jornada online.'};
function validateStep(s,core,now){
 keys(s,['tool','args']);const a=s.args;
 switch(s.tool){
 case 'offer':keys(a,['gross','km','minutes']);return {tool:s.tool,args:{gross:num(a.gross,0,100000),km:num(a.km,.01,3000),minutes:num(a.minutes,.01,2880)}};
 case 'explain':keys(a,['concepts']);check(Array.isArray(a.concepts)&&a.concepts.length>0&&a.concepts.length<=4);return {tool:s.tool,args:{concepts:a.concepts.map(x=>one(x,Object.keys(concepts)))}};
 case 'clarify':keys(a,['missing']);return {tool:s.tool,args:{missing:one(a.missing,['period','metric','offer','scope','unsupported'])}};
 case 'fuel_spent':keys(a,['ranges','platform']);check(a.platform==='all','Gastos de combustível não possuem rateio por plataforma');check(Array.isArray(a.ranges)&&a.ranges.length>0&&a.ranges.length<=4,'Períodos inválidos');return {tool:s.tool,args:{platform:'all',ranges:a.ranges.map(r=>{keys(r,['from','to']);const from=day(r.from),to=day(r.to);check(from<=to,'Intervalo invertido');return {from,to};})}};
 case 'metric':{keys(a,['period','platform','metric']);keys(a.period,['from','to']);const from=day(a.period.from),to=day(a.period.to);check(from<=to,'Intervalo invertido');return {tool:s.tool,args:{period:{from,to},platform:one(a.platform,['all','Uber','99']),metric:one(a.metric,['ganhos','lucro','despesas','corridas','ganho_km','ganho_hora','consumo_kml','meta'])}};}
 case 'finance':keys(a,['period','metric']);return {tool:s.tool,args:{period:one(a.period,periods),metric:one(a.metric,['saldo','lucro','despesas','combustivel_gasto','litros','abastecimentos','preco_litro','meta','consumo_kml','custo_km','cancelamentos','espera'])}};
 case 'rides':{
 keys(a,['period','platform','source','status','operation','metric','filters','clock','fields','direction','recordId']);
 let from,to;if(typeof a.period==='string'){one(a.period,periods);[from,to]=core.range(a.period,now);}else{keys(a.period,['from','to']);from=day(a.period.from);to=day(a.period.to);check(from<=to,'Intervalo invertido');}
 const o={period:{from,to},platform:one(a.platform,['all','Uber','99','unknown']),source:one(a.source,['all','real','simulated']),status:one(a.status,['finished','unfinished','cancel trip','all']),operation:one(a.operation,['count','sum','average','ratio','list','extreme'])};
 if(['sum','average','extreme'].includes(o.operation))o.metric=one(a.metric,metrics);
 if(o.operation==='sum')check(!['nota','valor_km','valor_hora'].includes(o.metric),'Métrica não somável');
 if(o.operation==='ratio')o.metric=one(a.metric,['valor_km','valor_hora']);
 if(a.clock!=null){keys(a.clock,['start','end']);o.clock={start:int(a.clock.start,0,1439),end:int(a.clock.end,0,1439)};}
 check(a.filters==null||Array.isArray(a.filters)&&a.filters.length<=4);
 o.filters=(a.filters||[]).map(f=>{keys(f,['field','op','value']);return {field:one(f.field,metrics),op:one(f.op,['gt','gte','lt','lte','eq']),value:num(f.value,-1e9,1e9)}});
 if(['list','extreme'].includes(o.operation)){check(Array.isArray(a.fields)&&a.fields.length>0&&a.fields.length<=8);o.fields=a.fields.map(k=>one(k,fields));o.direction=one(a.direction??'asc',['asc','desc']);}
 if(a.recordId!=null){check(typeof a.recordId==='string'&&a.recordId.length>0&&a.recordId.length<=200);o.recordId=a.recordId;}
 return {tool:s.tool,args:o};
 }
 default:throw Error('Ferramenta não autorizada');
 }}
function compile(command,session,core,now){
 let p;if(command.mode==='new'){keys(command,['mode','plan']);p=command.plan;}
 else if(command.mode==='revise'){keys(command,['mode','baseTurn','step','changes']);check(session?.plan&&command.baseTurn===session.turn,'Contexto desatualizado');const i=int(command.step,0,session.plan.steps.length-1);check(obj(command.changes)&&Object.keys(command.changes).length);p={version:1,steps:session.plan.steps.map((s,j)=>j===i?{tool:s.tool,args:{...s.args,...command.changes}}:s)};}
 else throw Error('Modo inválido');
 keys(p,['version','steps']);check(p.version===1&&Array.isArray(p.steps)&&p.steps.length>0&&p.steps.length<=4);
 return {version:1,steps:p.steps.map(s=>validateStep(s,core,now))};
}
function project(bundle,core,now){
 const s=core.snapshot(bundle.finance,bundle.rates,'total',now),raw=bundle.finance.rides.filter(r=>r[0]!=null&&r[0]!==''&&r[2].slice(0,10)>=s.from&&r[2].slice(0,10)<=s.to).sort((a,b)=>a[2].localeCompare(b[2]));
 check(raw.length===s.records.length,'Projeção inconsistente');
 return s.records.map((r,i)=>{check(r.inicio===raw[i][2]&&r.situacao===raw[i][1],'Identidade inconsistente');return {...r,id:raw[i][0]}});
}
function execute(s,b,rows,core,now){
 const a=s.args;
 if(s.tool==='explain')return {kind:'concepts',items:a.concepts.map(k=>({key:k,text:concepts[k]}))};
 if(s.tool==='clarify')return {kind:'clarification',missing:a.missing};
 if(s.tool==='fuel_spent'){const v=core.fuelSpentForRanges(b.finance,a.ranges);return {kind:'fuel_spent',value:v.value,count:v.count,evidence:{ranges:a.ranges,platform:'all',basis:'paid_fuel'}};}
 if(s.tool==='metric'){
 const platform=a.platform==='all'?null:a.platform;
 if(platform&&!['ganhos','corridas','ganho_km','ganho_hora'].includes(a.metric))return {kind:'unavailable',reason:'Não existe rateio confiável desse indicador por plataforma.'};
 if(a.metric==='consumo_kml'){const x=core.snapshot(b.finance,b.rates,'hoje',now);if(a.period.from!==x.from||a.period.to!==x.to||!Number.isFinite(x.consumption))return {kind:'unavailable',reason:'Consumo histórico indisponível. A taxa atual não representa o período solicitado.'};return {kind:'metric',text:core.answer(a.metric,x),period:a.period};}
 if(a.metric==='meta'){const today=core.range('hoje',now)[0];if(a.period.from!==today||a.period.to!==today)return {kind:'unavailable',reason:'A meta configurada é mensal e atual.'};const x=core.snapshot(b.finance,b.rates,'mes',now);if(!(x.goal>0))return {kind:'unavailable',reason:'Nenhuma meta mensal configurada.'};return {kind:'metric',text:core.answer(a.metric,x),period:{from:x.from,to:x.to}};}
 const x=core.snapshot(b.finance,b.rates,a.period,now);
 if(a.metric==='lucro'&&x.result==null)return {kind:'unavailable',reason:'Resultado operacional integral indisponível: cobertura de combustível '+x.coverage+'/'+x.count+' corridas.'};
 const text=core.answer(a.metric,x,{platform});return text?{kind:'metric',text,period:a.period}:{kind:'unavailable',reason:'Indicador indisponível.'};
 }
 if(s.tool==='finance'){const x=core.snapshot(b.finance,b.rates,a.period,now);return {kind:'finance',text:core.answer(a.metric,x),period:{from:x.from,to:x.to}};}
 if(s.tool==='offer'){const r=b.rates;if(!r||![r.fuel,r.reserve,r.fixed].every(x=>Number.isFinite(x)&&x>=0))return {kind:'unavailable',reason:'Parâmetros de custos ausentes'};
 const fuel=round(a.km*r.fuel),reserve=round(a.km*r.reserve),fixed=round(a.minutes/60*r.fixed),margin=round(a.gross-fuel-reserve-fixed);return {kind:'offer',inputs:a,fuel,reserve,fixed,margin,marginPerHour:round(margin*60/a.minutes),estimated:true};}
 const rs=rows.filter(r=>{if(r.dia<a.period.from||r.dia>a.period.to||a.recordId!=null&&r.id!==a.recordId||a.platform!=='all'&&(a.platform==='unknown'?r.plataforma!=='Não identificada':r.plataforma!==a.platform)||a.source!=='all'&&(a.source==='real'?r.simulated:!r.simulated)||a.status!=='all'&&r.situacao!==a.status)return false;
 if(a.clock){const n=Number(r.inicio.slice(11,13))*60+Number(r.inicio.slice(14,16)),{start,end}=a.clock;if(!(start<=end?n>=start&&n<=end:n>=start||n<=end))return false;}
 return a.filters.every(f=>Number.isFinite(r[f.field])&&({gt:r[f.field]>f.value,gte:r[f.field]>=f.value,lt:r[f.field]<f.value,lte:r[f.field]<=f.value,eq:r[f.field]===f.value})[f.op]);});
 const e={period:a.period,platform:a.platform,source:a.source,status:a.status,filters:a.filters,clock:a.clock||null,matched:rs.length,simulated:rs.filter(r=>r.simulated).length};
 if(a.operation==='count')return {kind:'number',metric:'count',value:rs.length,evidence:e};
 if(['sum','average'].includes(a.operation)){const vs=rs.map(r=>r[a.metric]).filter(Number.isFinite),sum=vs.reduce((n,v)=>n+v,0);return {kind:'number',metric:a.metric,value:vs.length?round(a.operation==='average'?sum/vs.length:sum):rs.length||a.operation==='average'?null:0,evidence:{...e,available:vs.length,missing:rs.length-vs.length}};}
 if(a.operation==='ratio'){const k=a.metric==='valor_km'?'km':'duracao',valid=rs.filter(r=>Number.isFinite(r.valor)&&Number.isFinite(r[k])&&r[k]>0),d=valid.reduce((n,r)=>n+r[k],0);return {kind:'number',metric:a.metric,value:d?round(valid.reduce((n,r)=>n+r.valor,0)/d*(k==='duracao'?3600:1)):null,evidence:{...e,available:valid.length,missing:rs.length-valid.length}};}
 const sorted=a.operation==='extreme'?rs.filter(r=>Number.isFinite(r[a.metric])).sort((x,y)=>(a.direction==='desc'?y[a.metric]-x[a.metric]:x[a.metric]-y[a.metric])||String(x.id).localeCompare(String(y.id))):a.direction==='desc'?[...rs].reverse():rs;
 return {kind:'records',rows:sorted.slice(0,a.operation==='extreme'?1:20).map(r=>({id:r.id,simulated:r.simulated,values:Object.fromEntries(a.fields.map(k=>[k,r[k]??null]))})),evidence:e,more:a.operation==='list'&&sorted.length>20};
}
async function run(command,session,{readData,core,now=new Date()}){
 const plan=compile(command,session,core,now),needs=plan.steps.some(s=>!['explain','clarify'].includes(s.tool)),bundle=needs?await readData():null,rows=plan.steps.some(s=>s.tool==='rides')?project(bundle,core,now):[];
 const results=plan.steps.map(s=>execute(s,bundle,rows,core,now));
 return {results,session:needs?{turn:(session?.turn||0)+1,plan,recordIds:results.map(r=>r.kind==='records'?r.rows.map(x=>x.id):[])}:session};
}
return {compile,run};
})();
if(typeof module!=='undefined')module.exports=AuraQueryEngine;