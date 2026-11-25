/* A mesma função financeira do painel Finance, extraída sem modificar suas regras. */
const Core=(()=>{
const categories=['Pedágio','Manutenção','Fixo','Operacional','Pessoal'];
const sum=(a,f)=>a.reduce((s,x)=>s+f(x),0), cents=x=>Math.round((x+Number.EPSILON)*100)/100;
const time=s=>{if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(s))throw Error('Data e hora inválida: '+s);const n=Date.parse(s+'Z');if(!Number.isFinite(n)||new Date(n).toISOString().slice(0,19)!==s)throw Error('Data inválida: '+s);return n;};
const day=s=>s.slice(0,10), date=(n)=>new Date(n).toISOString().slice(0,10), dtime=s=>time(s+'T00:00:00');
const number=(v)=>{if(v===''||v===null||v===undefined||typeof v==='boolean'||!Number.isFinite(Number(v))||Number(v)<0)throw Error('Número inválido: '+v);return Number(v);};
const unique=(a)=>{if(new Set(a.map(x=>x.id)).size!==a.length)throw Error('IDs duplicados na origem.');return a;};
function normalize(raw){
 const rides=unique(raw.rides.filter(r=>r[0]!==''&&r[0]!=null).map(r=>{let a=time(r[2]),b=r[3]?time(r[3]):null; if(!['finished','unfinished','cancel trip'].includes(r[1]))throw Error('Situação inválida: '+r[0]); if(r[1]==='finished'&&(b===null||b<a))throw Error('Finalização inválida: '+r[0]);return {id:String(r[0]),status:r[1],date:r[2],a,b,seconds:number(r[4]),km:number(r[5]),revenue:number(r[7])};})).sort((a,b)=>a.a-b.a);
 const fills=unique(raw.fills.filter(r=>r[0]!==''&&r[0]!=null).map(r=>{const l=number(r[3]),p=number(r[4]);if(!l||!p||typeof r[6]!=='boolean')throw Error('Abastecimento inválido: '+r[0]);return {id:String(r[0]),date:r[1],t:time(r[1]),odo:number(r[2]),liters:l,price:p,cost:cents(l*p),fuel:r[5],full:r[6]};})).sort((a,b)=>a.t-b.t);
 const expenses=unique(raw.expenses.filter(r=>r[0]!==''&&r[0]!=null).map(r=>{const paid=number(r[4]),refund=number(r[5]??0);if(!categories.includes(r[2])||!paid||refund>paid||!r[3])throw Error('Despesa inválida: '+r[0]);dtime(r[1]);return {id:String(r[0]),date:r[1],category:r[2],description:String(r[3]),paid,refund,net:cents(paid-refund),ride:String(r[6]??'')};})).sort((a,b)=>a.date.localeCompare(b.date));
 const goals={revenue:number(raw.goals.revenue),cash:number(raw.goals.cash),reserve:number(raw.goals.reserve)};
 const cycles=[];let anchor=null,liters=0,cost=0,invalid=0;for(let i=0;i<fills.length;i++){const f=fills[i];if(i&&(f.t<=fills[i-1].t||f.odo<fills[i-1].odo))throw Error('Ordem ou odômetro inválido: '+f.id);if(anchor){liters+=f.liters;cost+=f.cost;}if(f.full){if(anchor&&f.odo===anchor.odo){invalid++;continue;}if(anchor){const km=f.odo-anchor.odo;if(km>0&&liters>0)cycles.push({a:anchor.t,b:f.t,km,liters,cost:cents(cost),rate:cost/km,eff:km/liters,id:f.id});else invalid++;}anchor=f;liters=cost=0;}}
 // Rateio por sobreposição temporal; km uniformes dentro de uma corrida que cruza um ciclo.
 const finished=rides.filter(r=>r.status==='finished').map(r=>{let coveredKm=0,cost=0,coveredTime=0;for(const c of cycles){if(r.b===r.a){if(r.a>=c.a&&r.a<c.b){coveredKm=r.km;cost=r.km*c.rate;coveredTime=1;break;}continue;}const dt=Math.max(0,Math.min(r.b,c.b)-Math.max(r.a,c.a));if(!dt)continue;const k=r.km*dt/(r.b-r.a);coveredKm+=k;coveredTime+=dt;cost+=k*c.rate;}const covered=r.b===r.a?coveredTime===1:coveredTime>=r.b-r.a-1;return {...r,covered,coveredKm,cost:covered?cost:null};});
 return {rides,finished,fills,expenses,goals,cycles,invalid};
}
function stats(data,start='',end=''){const inside=s=>(!start||day(s)>=start)&&(!end||day(s)<=end),r=data.finished.filter(x=>inside(x.date)),f=data.fills.filter(x=>inside(x.date)),e=data.expenses.filter(x=>inside(x.date)),op=e.filter(x=>x.category!=='Pessoal'),personal=e.filter(x=>x.category==='Pessoal'),covered=r.filter(x=>x.covered),revenue=sum(r,x=>x.revenue),km=sum(r,x=>x.km),hours=sum(r,x=>x.seconds)/3600,paidFuel=sum(f,x=>x.cost),opCost=sum(op,x=>x.net),personalCost=sum(personal,x=>x.net),fuelEst=sum(covered,x=>x.cost),coveredRevenue=sum(covered,x=>x.revenue),coveredKm=sum(covered,x=>x.km),complete=r.length>0&&covered.length===r.length,active=new Set(r.map(x=>day(x.date))).size;
 const scope=data.cycles.filter(c=>(!start||c.b>=dtime(start))&&(!end||c.a<dtime(end)+86400000));
 const warnings=scope.filter(c=>c.eff>20||c.eff<4); // limiar de inspeção ilustrativo, não especificação veicular
 const inconsistent=scope.filter(c=>sum(data.finished,x=>{if(x.b===x.a)return x.a>=c.a&&x.a<c.b?x.km:0;return x.km*Math.max(0,Math.min(x.b,c.b)-Math.max(x.a,c.a))/(x.b-x.a);})>c.km+0.01);
 return {r,f,e,op,personal,covered,revenue,km,hours,paidFuel,opCost,personalCost,fuelEst,coveredRevenue,coveredKm,complete,active,scope,warnings,inconsistent,cash:revenue-paidFuel-opCost,afterPersonal:revenue-paidFuel-opCost-personalCost,result:complete&&!inconsistent.length?revenue-fuelEst-opCost:null,reserve:km*data.goals.reserve};}
function range(data){const a=[...data.rides.map(r=>day(r.date)),...data.fills.map(r=>day(r.date)),...data.expenses.map(r=>r.date)].sort();return [a[0]||'',a.at(-1)||''];}
function common(data){if(!data.cycles.length||!data.finished.length)return range(data);const a=Math.max(data.cycles[0].a,data.finished[0].a),b=Math.min(data.cycles.at(-1).b,Math.max(...data.finished.map(r=>r.b)));if(a>b)return range(data);const s=date(a),e=date(b);const innerStart=date(Math.ceil(a/86400000)*86400000),innerEnd=date(Math.floor(b/86400000)*86400000-86400000);return innerStart<=innerEnd?[innerStart,innerEnd]:s<=e?[s,e]:range(data);}
function groups(rows,key){const m=new Map();for(const r of rows){const k=key(r);if(!m.has(k))m.set(k,[]);m.get(k).push(r);}return m;}
return {categories,normalize,stats,range,common,groups,sum,day,time,date,dtime,cents};})();

const AuraCore=(()=>{
const n=(x)=>Number.isFinite(x)?x:null,round=x=>Number.isFinite(x)?Math.round(x*100)/100:null;
const money=x=>x==null?'indisponível':x.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const fmt=(x,d=1)=>x==null?'indisponível':x.toLocaleString('pt-BR',{maximumFractionDigits:d,minimumFractionDigits:d});
const date=(d)=>new Date(d-d.getTimezoneOffset()*60000).toISOString().slice(0,10);
const periods={hoje:1,ontem:1,semana:7,quinze:15,mes:30};
function range(period,now=new Date()){const end=new Date(now),start=new Date(now);if(period==='ontem'){end.setDate(end.getDate()-1);start.setDate(start.getDate()-1)}else if(period==='mes'){start.setDate(1)}else start.setDate(start.getDate()-((periods[period]||1)-1));return [date(start),date(end)]}
function snapshot(raw,rate,period='hoje',now=new Date()){
 const [from,to]=range(period,now),data=Core.normalize(raw),s=Core.stats(data,from,to),inside=x=>x.date.slice(0,10)>=from&&x.date.slice(0,10)<=to;
 const rides=data.rides.filter(inside),real=rides.filter(r=>!r.id.startsWith('MOB-')),sim=rides.length-real.length;
 const canceled=real.filter(r=>r.status==='cancel trip').length,finished=real.filter(r=>r.status==='finished').sort((a,b)=>a.a-b.a);
 const gaps=[];for(let j=1;j<finished.length;j++){const a=finished[j-1],b=finished[j];if(a.date.slice(0,10)===b.date.slice(0,10)&&a.b!=null&&b.a>=a.b){const gap=(b.a-a.b)/60000;if(gap<=120)gaps.push(gap)}}
 const avg=gaps.length?gaps.reduce((a,b)=>a+b,0)/gaps.length:null;
 const byPlatform={Uber:0,'99':0,unknown:0},platformStats=Object.fromEntries(['Uber','99','unknown'].map(k=>[k,{count:0,gross:0,km:0,seconds:0}]));let tripKm=0,pickupKm=0,splitCount=0;
 const rawById=new Map(raw.rides.map(r=>[String(r[0]),r]));
 for(const r of s.r){const row=rawById.get(r.id)||[],app=String(row[8]??'').trim().toLowerCase();const key=app==='uber'?'Uber':app==='99'?'99':'unknown';byPlatform[key]++;const p=platformStats[key];p.count++;p.gross+=r.revenue;p.km+=r.km;p.seconds+=r.seconds;
 if(typeof row[9]==='number'&&typeof row[10]==='number'&&Number.isFinite(row[9])&&Number.isFinite(row[10])&&row[9]>=0&&row[10]>=0&&Math.abs(row[9]+row[10]-r.km)<=.03){pickupKm+=row[9];tripKm+=row[10];splitCount++;}}

 return {period,from,to,byPlatform,platformStats,seconds:s.r.reduce((a,r)=>a+r.seconds,0),tripKm:round(tripKm),pickupKm:round(pickupKm),splitCount,count:s.r.length,realCount:finished.length,simulated:sim,canceled,cancelRate:real.length?canceled/real.length*100:null,gap:round(avg),gapSamples:gaps.length,gross:round(s.revenue),cash:round(s.cash),afterPersonal:round(s.afterPersonal),result:round(s.result),km:round(s.km),hours:round(s.hours),grossHour:s.hours?round(s.revenue/s.hours):null,grossKm:s.km?round(s.revenue/s.km):null,paidFuel:round(s.paidFuel),opCost:round(s.opCost),personalCost:round(s.personalCost),consumption:n(rate?.eff),fuelKm:n(rate?.fuel),cycles:rate?.cycles||0,goal:period==='mes'?n(data.goals.revenue):null,reserve:round(s.reserve),coverage:s.covered.length,invalid:s.inconsistent.length};
}
const normalize=q=>q.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
function parse(q,previous){
 const t=normalize(q).trim();const explicit=/\bontem\b/.test(t)?'ontem':/\b(15|quinze)\b/.test(t)?'quinze':/semana|\b7 dias\b/.test(t)?'semana':/\bmes\b|mensal/.test(t)?'mes':/\bhoje\b/.test(t)?'hoje':null;
 const uber=/\buber\b/.test(t),noventa=/\b99\b|noventa e nove/.test(t),hasApp=uber||noventa;
 const detail=/^(e\s+)?(detalh|explic|resume|resum|me mostra|me mostre|mais detalhes)|^(como assim|por que|porque)\??$/.test(t);
 const metrics=[
 ['plano',/plano|sugest|estrateg|melhorar|produtiv|compensa|vale a pena|o que (fazer|faco)|como ganhar|como aumentar|como reduzir/],
 ['cancelamentos',/cancel/],
 ['espera',/espera|ocioso|ociosidade|parado/],
 ['consumo_kml',/consumo|km\s*\/\s*l|quilometros por litro/],
 ['custo_km',/custo.*(km|quilometro)|combustivel.*(km|quilometro)/],
 ['ganho_hora',/por hora|r\$\s*\/\s*h|ganho.*hora/],
 ['ganho_km',/por km|por quilometro|r\$\s*\/\s*km/],
 ['lucro',/lucro|resultado operacional/],
 ['saldo',/saldo|caixa|sobrou|sobrando/],
 ['meta',/meta/],
 ['despesas',/gastei|gasto|despesa|paguei|custos|desembolsei/],
 ['ticket',/ticket|valor medio|media por corrida|media de valor/],
 ['duracao',/tempo|duracao|demor|horas|minutos/],
 ['distancia',/\bkm\b|quilometr|quilometros|distancia|quanto rodei|quanto percorri/],
 ['corridas',/quantas corridas|numero de corridas|total de corridas|quantidade de corridas/],
 ['ganhos',/ganh|fatur|receita|quanto fiz/],
 ['saudacao',/^(oi|ola|bom dia|boa noite|boa tarde)[!?. ]*$/]];
 let intent=metrics.find(([k,re])=>re.test(t))?.[0]||null;
 let platform=uber&&!noventa?'Uber':noventa&&!uber?'99':null;
 if(hasApp||/plataforma|qual aplicativo/.test(t)){
   const compare=uber&&noventa||/qual aplicativo|qual plataforma|compar|em qual|mais corrida/.test(t);
   if(compare){intent=intent&&['ganhos','distancia','duracao','ganho_hora','ganho_km','ticket'].includes(intent)?'comparacao':'plataformas';}
   else if(!intent||intent==='corridas'){intent='plataformas';}
   else if(!['ganhos','distancia','duracao','ganho_hora','ganho_km','ticket'].includes(intent)){platform=null;}
 }
 if(detail&&!hasApp&&!intent)intent='detalhes';
 if(!intent&&explicit&&previous?.intent){intent=previous.intent;platform=previous.platform||null;}
 const compareMetric=intent==='comparacao'?(metrics.find(([k,re])=>['ganhos','distancia','duracao','ganho_hora','ganho_km','ticket'].includes(k)&&re.test(t))?.[0]||'corridas'):null;
 return {intent,period:explicit||previous?.period||'hoje',platform,compareMetric};
}
function duration(seconds){if(!Number.isFinite(seconds))return 'indisponível';const m=Math.round(seconds/60);return Math.floor(m/60)+'h '+String(m%60).padStart(2,'0')+'min';}
function platformValue(p,metric){switch(metric){case 'ganhos':return p.gross;case 'distancia':return p.km;case 'duracao':return p.seconds;case 'ganho_hora':return p.seconds?p.gross*3600/p.seconds:null;case 'ganho_km':return p.km?p.gross/p.km:null;case 'ticket':return p.count?p.gross/p.count:null;default:return p.count;}}
function platformFormat(v,metric){if(v==null)return 'indisponível';return metric==='duracao'?duration(v):metric==='distancia'?fmt(v,2)+' km':metric==='corridas'?String(v):money(v);}

function note(s){return s.simulated?' Há '+s.simulated+' registros simulados no período; valores não representam exclusivamente trabalho real.':''}
function plan(s){const a=[];if(!s.realCount)a.push('Registre corridas reais para identificar seu desempenho; não use simulações como histórico de trabalho.');if(s.canceled>=10||(s.cancelRate!=null&&s.cancelRate>10))a.push('Revise os '+s.canceled+' cancelamentos registrados. Avalie destino, embarque e margem antes de aceitar; não aceite corridas ruins só para reduzir a taxa.');if(s.gap!=null&&s.gap>8)a.push('O intervalo médio observado foi '+fmt(s.gap)+' min. Se estiver online e parado por mais de 8 min, avalie demanda e região com segurança; não confunda pausas com espera.');else if(s.gap===null)a.push('Não há intervalos suficientes para medir espera; anote quando estiver online e aguardando ofertas.');if(s.result===null)a.push('Complete ciclos de tanque cheio e registre despesas para calcular o resultado operacional integral.');else if(s.result<0)a.push('O resultado operacional registrado é negativo. Reveja custo de combustível e despesas antes de ampliar a jornada.');if(s.fuelKm!=null)a.push('Considere '+money(s.fuelKm)+'/km de combustível '+(s.cycles?'estimado por ciclos':'estimado pelos parâmetros')+' e o custo do embarque ao avaliar uma oferta.');if(s.grossHour!=null)a.push('Seu faturamento por hora em corrida é '+money(s.grossHour)+'. Compare com a meta e com o tempo online real, incluindo pausas.');return a.slice(0,5);}
function answer(intent,s,options={}){let out;const platform=options.platform;const metric=options.compareMetric||'corridas';if(platform&&['ganhos','distancia','duracao','ganho_hora','ganho_km','ticket'].includes(intent)){const p=s.platformStats[platform];return platform+': '+platformFormat(platformValue(p,intent),intent)+' em '+p.count+' corridas finalizadas.'+(s.byPlatform.unknown?' '+s.byPlatform.unknown+' corridas sem plataforma não entram nesse subtotal.':'')+note(s);}switch(intent){
case 'saudacao':return 'Olá! Posso analisar suas corridas, ganhos, despesas, combustível e sugerir um plano de ação.';
case 'comparacao':{const p=s.platformStats;out='Uber: '+platformFormat(platformValue(p.Uber,metric),metric)+' | 99: '+platformFormat(platformValue(p['99'],metric),metric)+'.';if(p.unknown.count)out+=' '+p.unknown.count+' corridas sem plataforma não entram na comparação.';break;}
case 'duracao':out='Tempo total registrado em corridas: '+duration(s.seconds)+'.'+(s.count?' Média por corrida: '+duration(s.seconds/s.count)+'.':'')+' Inclui os tempos registrados pelo VEXO; não equivale ao tempo online.';break;
case 'ticket':out='Valor médio por corrida finalizada: '+money(s.count?s.gross/s.count:null)+'.';break;
case 'detalhes':out='Resumo do período: '+s.count+' corridas finalizadas; faturamento '+money(s.gross)+'; '+fmt(s.km,2)+' km; '+duration(s.seconds)+' em corridas. Uber: '+s.byPlatform.Uber+'; 99: '+s.byPlatform['99']+'; sem plataforma: '+s.byPlatform.unknown+'. Caixa operacional: '+money(s.cash)+'.';break;
case 'plataformas':{const p=s.byPlatform;if(platform){out=platform+': '+p[platform]+' corridas finalizadas.'+(p.unknown?' '+p.unknown+' sem plataforma identificada.':'');break;}out='Corridas finalizadas: Uber '+p.Uber+' | 99 '+p['99']+'.';if(p.unknown)out+=' '+p.unknown+' sem plataforma identificada.';if(p.Uber+p['99']===0)out+=' Não há registros identificados para comparar.';else if(p.Uber===p['99'])out+=' Entre as identificadas, houve empate.';else out+=' Entre as identificadas, '+(p.Uber>p['99']?'Uber':'99')+' teve '+Math.abs(p.Uber-p['99'])+' corrida(s) a mais.';break;}
case 'distancia':out='Distância total registrada nas corridas finalizadas: '+fmt(s.km,2)+' km.';if(s.count&&s.splitCount===s.count)out+=' Com passageiro: '+fmt(s.tripKm,2)+' km; até o embarque: '+fmt(s.pickupKm,2)+' km.';else if(s.count)out+=' Separação entre embarque e trajeto disponível em '+s.splitCount+' de '+s.count+' corridas.';out+=' Não inclui deslocamentos fora dos registros.';break;
case 'corridas':out='Total de corridas finalizadas: '+s.count+'.';break;
case 'ganhos':out='Faturamento registrado: '+money(s.gross)+' em '+s.count+' corridas finalizadas.';break;
case 'saldo':out='Caixa operacional: '+money(s.cash)+'. Após despesas pessoais: '+money(s.afterPersonal)+'. Caixa não é lucro.';break;
case 'lucro':out=s.result==null?'Resultado operacional integral indisponível: cobertura de combustível '+s.coverage+'/'+s.count+' corridas'+(s.invalid?', com ciclos inconsistentes':'')+'. O caixa operacional é '+money(s.cash)+', mas não equivale ao lucro.':'Resultado operacional estimado: '+money(s.result)+'. Considera combustível rateado e despesas operacionais registradas; não é lucro contábil completo.';break;
case 'despesas':out='Abastecimentos pagos: '+money(s.paidFuel)+'. Despesas operacionais líquidas: '+money(s.opCost)+'. Pessoais: '+money(s.personalCost)+'.';break;
case 'ganho_hora':out='Faturamento por hora em corrida: '+money(s.grossHour)+'. Não inclui tempo online ocioso.';break;
case 'ganho_km':out='Faturamento por km registrado: '+money(s.grossKm)+'. Não equivale ao lucro por km.';break;
case 'consumo_kml':out='Consumo '+(s.cycles?'estimado por ciclos completos':'configurado, sem ciclo completo')+': '+fmt(s.consumption)+' km/L.';break;
case 'custo_km':out='Combustível por km: '+money(s.fuelKm)+' ('+(s.cycles?'ciclos completos':'estimativa configurada')+'). Não inclui todos os custos do veículo.';break;
case 'meta':out=s.goal==null?'A meta de receita é mensal. Pergunte pela meta deste mês.':s.goal<=0?'Nenhuma meta mensal de receita configurada no Finance.':'Meta mensal de receita: '+money(s.goal)+'. Faturamento do mês: '+money(s.gross)+'. Progresso: '+fmt(s.gross/s.goal*100)+'%.';break;
case 'cancelamentos':out='Cancelamentos reais registrados: '+s.canceled+(s.cancelRate==null?'. Sem base suficiente para uma taxa.':' ('+fmt(s.cancelRate)+'% dos registros reais).')+' Recusar uma oferta não é cancelar uma corrida aceita.';break;
case 'espera':out=s.gap==null?'Não há intervalos suficientes entre corridas reais.':'Intervalo médio entre corridas reais: '+fmt(s.gap)+' min, em '+s.gapSamples+' intervalos. Não mede necessariamente espera online: inclui possíveis pausas.';break;
case 'plano':out='Plano de ação para o período:\n'+plan(s).map((x,i)=>(i+1)+'. '+x).join('\n');break;
default:return null;}
return out+note(s);}
return {snapshot,parse,answer,plan,range};
})();
if(typeof module!=='undefined')module.exports=AuraCore;
