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
'use strict';
const periods=['hoje','ontem','semana','quinze','mes','trinta','total'];
const catalog=[
 ['ganhos',/\b(ganh\w*|fatur\w*|receita|dinheiro|rendeu|rendimento)\b|quanto fiz/],
 ['despesas',/\b(gastei|gastos?|despesas?|paguei|desembolsei|custos?)\b/],
 ['saldo',/\b(saldo|caixa|sobrou|sobrando)\b/],
 ['lucro',/\blucro\b|resultado operacional/],
 ['meta',/\bmetas?\b|quanto falta/],
 ['ganho_hora',/por hora|r\$\s*\/\s*h|ganho.*hora/],
 ['ganho_km',/por km|por quilometro|r\$\s*\/\s*km/],
 ['consumo_kml',/\bconsumo\b|km\s*\/\s*l|quilometros por litro/],
 ['custo_km',/custo.*(km|quilometro)|combustivel.*(km|quilometro)|quanto custa.*km/],
 ['combustivel_gasto',/quanto (?:de )?(?:combustivel|gasolina|etanol).*gast|gastei.*(?:combustivel|gasolina|etanol)|gasto.*(?:combustivel|gasolina|etanol)|(?:combustivel|gasolina|etanol).*(?:paguei|gastei)/],
 ['litros',/\blitros?\b/],
 ['abastecimentos',/quant[oa]s?\s+(?:vezes )?abastec|abastecimentos?|quantas vezes.*posto/],
 ['preco_litro',/(?:preco|valor|custo).*(?:litro|gasolina|etanol)|quanto.*(?:cada|o) litro/],
 ['cancelamentos',/\bcancel\w*/],
 ['espera',/\bespera\b|ocioso|ociosidade|\bparad[oa]\b|intervalo entre/],
 ['distancia',/\bkm\b|quilometr\w*|distancia|quanto rodei|quanto percorri/],
 ['duracao',/\btempo\b|duracao|demor\w*|\bhoras?\b|\bminutos?\b/],
 ['corridas',/quantas corridas|numero de corridas|total de corridas|quantidade de corridas/],
 ['ticket',/ticket|valor medio|media por corrida|media de valor/],
 ['plataformas',/\buber\b|\b99\b|noventa e nove|plataformas?|qual aplicativo|qual app/],
 ['detalhes',/^(?:e\s+)?(?:detalh\w*|explic\w*|resum\w*|me mostr\w*|mais detalhes)|^(?:como assim|por que|porque)\??$/],
 ['plano',/plano|sugest\w*|estrateg\w*|melhorar|produtiv\w*|compensa|vale a pena|o que (?:fazer|faco)|como ganhar|como aumentar|como reduzir/]
];
const keys=catalog.map(x=>x[0]),partitioned=['ganhos','distancia','duracao','corridas','ganho_hora','ganho_km','ticket'];
const intents=[...keys,'comparacao','multi','saudacao','conversa','esclarecer'];
const normalize=q=>String(q||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim();
const round=x=>Number.isFinite(x)?Math.round((x+Number.EPSILON)*100)/100:null;
const money=x=>Number.isFinite(x)?x.toLocaleString('pt-BR',{style:'currency',currency:'BRL'}):'indisponível';
const fmt=(x,d=1)=>Number.isFinite(x)?x.toLocaleString('pt-BR',{maximumFractionDigits:d,minimumFractionDigits:d}):'indisponível';
const duration=seconds=>{if(!Number.isFinite(seconds))return 'indisponível';const m=Math.round(seconds/60);return Math.floor(m/60)+'h '+String(m%60).padStart(2,'0')+'min';};
const date=d=>new Date(d-d.getTimezoneOffset()*60000).toISOString().slice(0,10);
const add=(d,n)=>{const x=new Date(d);x.setDate(x.getDate()+n);return x;};
function range(period,now=new Date()){
 if(period==='total')return ['0001-01-01',date(now)];
 if(period==='ontem')return [date(add(now,-1)),date(add(now,-1))];
 if(period==='mes'){const start=new Date(now);start.setDate(1);return [date(start),date(now)];}
 const n={hoje:0,semana:6,quinze:14,trinta:29}[period]??0;return [date(add(now,-n)),date(now)];
}
function snapshot(raw,rate,period='hoje',now=new Date()){
 const data=Core.normalize(raw);let [from,to]=range(period,now);
 if(period==='total'){const dates=[...data.rides.map(x=>x.date),...data.fills.map(x=>x.date),...data.expenses.map(x=>x.date)].map(x=>x.slice(0,10)).filter(x=>x<=to).sort();from=dates[0]||to;}
 const s=Core.stats(data,from,to),inside=x=>x.date.slice(0,10)>=from&&x.date.slice(0,10)<=to;
 const rides=data.rides.filter(inside),real=rides.filter(r=>!r.id.startsWith('MOB-')),simulated=rides.length-real.length;
 const canceled=real.filter(r=>r.status==='cancel trip').length,finished=real.filter(r=>r.status==='finished').sort((a,b)=>a.a-b.a);
 const gaps=[];for(let j=1;j<finished.length;j++){const a=finished[j-1],b=finished[j];if(a.date.slice(0,10)===b.date.slice(0,10)&&a.b!=null&&b.a>=a.b){const gap=(b.a-a.b)/60000;if(gap<=120)gaps.push(gap);}}
 const gap=gaps.length?gaps.reduce((a,b)=>a+b,0)/gaps.length:null;
 const platformStats=Object.fromEntries(['Uber','99','unknown'].map(k=>[k,{count:0,gross:0,km:0,seconds:0,tripKm:0,pickupKm:0,splitCount:0,simulated:0}]));
 const rawById=new Map(raw.rides.map(r=>[String(r[0]),r]));let tripKm=0,pickupKm=0,splitCount=0;
 for(const r of s.r){const row=rawById.get(r.id)||[],app=String(row[8]??'').trim().toLowerCase(),p=platformStats[app==='uber'?'Uber':app==='99'?'99':'unknown'];
 p.count++;p.gross+=r.revenue;p.km+=r.km;p.seconds+=r.seconds;if(r.id.startsWith('MOB-'))p.simulated++;
 if(typeof row[9]==='number'&&typeof row[10]==='number'&&Number.isFinite(row[9])&&Number.isFinite(row[10])&&row[9]>=0&&row[10]>=0&&Math.abs(row[9]+row[10]-r.km)<=.03){p.pickupKm+=row[9];p.tripKm+=row[10];p.splitCount++;pickupKm+=row[9];tripKm+=row[10];splitCount++;}}
 for(const p of Object.values(platformStats)){p.gross=round(p.gross);p.km=round(p.km);p.tripKm=round(p.tripKm);p.pickupKm=round(p.pickupKm);}
 const byPlatform=Object.fromEntries(Object.entries(platformStats).map(([k,p])=>[k,p.count]));
 const liters=s.f.reduce((a,r)=>a+r.liters,0);
 return {period,from,to,byPlatform,platformStats,seconds:s.r.reduce((a,r)=>a+r.seconds,0),tripKm:round(tripKm),pickupKm:round(pickupKm),splitCount,count:s.r.length,realCount:finished.length,simulated,canceled,cancelRate:real.length?canceled/real.length*100:null,gap:round(gap),gapSamples:gaps.length,gross:round(s.revenue),cash:round(s.cash),afterPersonal:round(s.afterPersonal),result:round(s.result),km:round(s.km),hours:round(s.hours),grossHour:s.hours?round(s.revenue/s.hours):null,grossKm:s.km?round(s.revenue/s.km):null,paidFuel:round(s.paidFuel),opCost:round(s.opCost),personalCost:round(s.personalCost),liters:round(liters),fillCount:s.f.length,avgPrice:liters?round(s.paidFuel/liters):null,consumption:Number.isFinite(rate?.eff)?rate.eff:null,fuelKm:Number.isFinite(rate?.fuel)?rate.fuel:null,cycles:rate?.cycles||0,goal:period==='mes'?data.goals.revenue:null,reserve:round(s.reserve),coverage:s.covered.length,invalid:s.inconsistent.length};
}
function cleanQuery(q,previous=null){
 if(!q||!intents.includes(q.intent))return null;
 const period=periods.includes(q.period)?q.period:periods.includes(previous?.period)?previous.period:'hoje';
 const platform=['Uber','99'].includes(q.platform)?q.platform:null;
 const compareMetric=partitioned.includes(q.compareMetric)?q.compareMetric:'corridas';
 const metrics=Array.isArray(q.metrics)?[...new Set(q.metrics.filter(k=>keys.includes(k)&&!['plataformas','detalhes','plano'].includes(k)))].slice(0,4):[];
 if(q.intent==='multi'&&!metrics.length)return null;
 return {intent:q.intent,period,platform,compareMetric,metrics,reply:typeof q.reply==='string'?q.reply.trim().slice(0,350):''};
}
function parse(question,previous=null){
 const t=normalize(question);const prior=cleanQuery(previous);
 const explicit=/\bontem\b/.test(t)?'ontem':/\b(?:15|quinze)\s*(?:dias)?\b/.test(t)&&!/\b(?:r\$|reais)\b/.test(t)?'quinze':/\b(?:30|trinta)\s*(?:dias)\b/.test(t)?'trinta':/\bsemana\b|\b7 dias\b/.test(t)?'semana':/\bmes\b|mensal/.test(t)?'mes':/\bhoje\b/.test(t)?'hoje':/historico (?:todo|completo)|todo (?:o )?periodo|desde (?:o )?comeco|desde sempre/.test(t)?'total':null;
 const u=/\buber\b/.test(t),n=/\b99\b|noventa e nove/.test(t),both=u&&n,hasPlatform=u||n;
 let platform=u&&!n?'Uber':n&&!u?'99':null;
 const follow=/^(?:e\s+)?(?:na|no|pela|pelo|da|do|so|apenas)\s+(?:uber|99|noventa e nove)(?:\s+(?:hoje|ontem|nessa semana|nesse mes))?\s*\??$/.test(t);
 const other=/^(?:e\s+)?(?:a|o)\s+outr[oa](?:\s+plataforma)?\s*\??$/.test(t);
 const periodOnly=explicit&&/^(?:e\s+)?(?:nos?\s+|nas?\s+|ness[ae]\s+|nest[ae]\s+|ultim[oa]s?\s+|no\s+|na\s+|de\s+)*(?:hoje|ontem|semana|mes|15|quinze|30|trinta|7 dias|historico todo|desde sempre)(?:\s+dias)?\s*[?.!]*$/.test(t);
 if(other&&prior?.platform){return {...prior,platform:prior.platform==='Uber'?'99':'Uber',reply:''};}
 if((follow||periodOnly)&&prior&&prior.intent!=='saudacao'){return {...prior,period:explicit||prior.period,platform:follow?platform:prior.platform,reply:''};}
 if(/^(oi|ola|opa|e ai|bom dia|boa tarde|boa noite)[!?. ]*$/.test(t))return cleanQuery({intent:'saudacao',period:'hoje'});
 const found=new Set(catalog.filter(([,r])=>r.test(t)).map(([k])=>k));
 // Semantic precedence applies to overlapping units, not entire questions.
 if(found.has('custo_km')){found.delete('ganho_km');found.delete('distancia');found.delete('despesas');}
 if(found.has('consumo_kml')){found.delete('distancia');found.delete('litros');}
 if(found.has('preco_litro')){found.delete('litros');found.delete('despesas');}
 if(found.has('combustivel_gasto'))found.delete('despesas');
 if(found.has('ganho_hora')){found.delete('duracao');if(!/\be\s+(?:quanto|qual|o)?\s*(?:ganhei|faturei|faturamento|ganhos?)\b/.test(t))found.delete('ganhos');}
 if(found.has('ganho_km')){found.delete('distancia');if(!/\be\s+(?:quanto|qual|o)?\s*(?:ganhei|faturei|faturamento|ganhos?)\b/.test(t))found.delete('ganhos');}
 if(found.has('espera'))found.delete('duracao');
 if(found.has('ticket')){found.delete('ganhos');found.delete('corridas');}
 if(found.has('plano'))return cleanQuery({intent:'plano',period:explicit||prior?.period||'hoje',platform});
 if(found.has('detalhes')&&found.size===1)return cleanQuery({intent:'detalhes',period:explicit||prior?.period||'hoje',platform:platform||prior?.platform});
 found.delete('detalhes');found.delete('plataformas');
 // Explicit comparison preserves its metric; bare "99 ou Uber" shows the full platform breakdown.
 const comparing=both||/qual (?:aplicativo|app|plataforma)|compar\w*|em qual|mais corridas?/.test(t)&&hasPlatform;
 const selected=[...found];
 let intent=null,compareMetric='corridas',metrics=[];
 if(comparing){const m=selected.find(k=>partitioned.includes(k)&&k!=='corridas');intent=m?'comparacao':'plataformas';compareMetric=m||'corridas';platform=null;}
 else if(selected.length>1&&/\be\b|[,;]/.test(t)){intent='multi';metrics=selected.slice(0,4);}
 else if(selected.length){const priority=['meta','lucro','saldo','ganho_hora','ganho_km','custo_km','consumo_kml','preco_litro','combustivel_gasto','cancelamentos','espera','ticket','litros','abastecimentos','despesas','distancia','duracao','corridas','ganhos'];intent=priority.find(k=>found.has(k))||selected[0];}
 else if(hasPlatform||/plataforma|qual aplicativo|qual app/.test(t))intent='plataformas';
 else if(periodOnly&&prior)return {...prior,period:explicit,reply:''};
 else if(/^(?:e\s+)?(?:o\s+)?total\s*[?.!]*$/.test(t)&&prior)return {...prior,reply:''};
 if(!intent)return {intent:null,period:explicit||prior?.period||'hoje',platform,compareMetric,metrics:[]};
 // Fuel spending is a precise submetric but retains the old expenses label for compatibility.
 if(intent==='meta'&&!explicit) return cleanQuery({intent,period:'mes',platform,compareMetric,metrics});
 return cleanQuery({intent,period:explicit||prior?.period||'hoje',platform,compareMetric,metrics});
}
const note=s=>s.simulated?' '+s.simulated+' registro(s) simulados no período.':'';
function platformValue(p,k){switch(k){case 'ganhos':return p.gross;case 'distancia':return p.km;case 'duracao':return p.seconds;case 'ganho_hora':return p.seconds?p.gross*3600/p.seconds:null;case 'ganho_km':return p.km?p.gross/p.km:null;case 'ticket':return p.count?p.gross/p.count:null;default:return p.count;}}
function valueFormat(v,k){return v==null?'indisponível':k==='duracao'?duration(v):k==='distancia'?fmt(v,2)+' km':k==='corridas'?String(v):money(v);}
function plan(s){
 const a=[];
 if(!s.realCount)a.push('Os registros de trabalho real ainda são insuficientes. Separe simulações do trabalho real antes de mudar sua estratégia.');
 if(s.canceled>=10||s.cancelRate!=null&&s.cancelRate>10)a.push('Revise os '+s.canceled+' cancelamentos registrados. Avalie embarque, destino e margem antes de aceitar.');
 if(s.gap!=null&&s.gap>8)a.push('O intervalo médio observado foi '+fmt(s.gap)+' min. Se estiver online sem ofertas por mais de 8 min, avalie demanda e região quando estiver estacionado.');
 else if(s.gap===null)a.push('Não há intervalos suficientes para medir espera online. Registre início e fim da jornada para distinguir pausas de espera.');
 if(s.result===null)a.push('Complete ciclos de tanque cheio e registre despesas para calcular o resultado operacional integral.');
 else if(s.result<0)a.push('O resultado operacional registrado é negativo. Revise combustível e despesas antes de ampliar a jornada.');
 if(s.fuelKm!=null)a.push('Use '+money(s.fuelKm)+'/km de combustível '+(s.cycles?'estimado por ciclos':'estimado pelos parâmetros')+' ao avaliar ofertas e embarques.');
 if(s.grossHour!=null)a.push('Faturamento por hora em corrida: '+money(s.grossHour)+'. Compare com a meta e o tempo online real.');
 return a.slice(0,5);
}
function answer(intent,s,options={}){
 const p=options.platform,metric=options.compareMetric||'corridas';
 if(intent==='saudacao')return 'Olá! Sou a Aura. Posso consultar suas corridas, ganhos, combustível, despesas e montar um plano de ação.';
 if(intent==='multi')return (options.metrics||[]).map(k=>answer(k,s,{platform:p,omitNote:true})).filter(Boolean).join('\n\n')+note(s);
 let out;
 if(p&&partitioned.includes(intent)){
 const a=s.platformStats[p];out=p+': '+valueFormat(platformValue(a,intent),intent)+' em '+a.count+' corridas finalizadas.';
 if(intent==='distancia'&&a.count&&a.splitCount===a.count)out+=' Passageiro: '+fmt(a.tripKm,2)+' km; embarque: '+fmt(a.pickupKm,2)+' km.';
 if(s.byPlatform.unknown)out+=' '+s.byPlatform.unknown+' sem plataforma não entram nesse subtotal.';
 }else if(p&&!['plataformas','detalhes','plano','comparacao'].includes(intent)){
 out='Não há rateio confiável de '+intent.replace(/_/g,' ')+' por plataforma. Para não misturar os dados, consulte o total do VEXO ou o faturamento de '+p+'.';
 }else switch(intent){
 case 'comparacao':{const a=s.platformStats.Uber,b=s.platformStats['99'],x=platformValue(a,metric),y=platformValue(b,metric);out='Uber: '+valueFormat(x,metric)+' | 99: '+valueFormat(y,metric)+'.';if(x!=null&&y!=null&&x!==y)out+=' '+(x>y?'Uber':'99')+' teve o maior valor nesse indicador.';if(s.byPlatform.unknown)out+=' '+s.byPlatform.unknown+' corridas sem plataforma não entram na comparação.';break;}
 case 'plataformas':{const a=s.platformStats;if(p){out=p+': '+a[p].count+' corridas finalizadas; '+money(a[p].gross)+' de faturamento.';}else{out='Corridas finalizadas: Uber '+a.Uber.count+' | 99 '+a['99'].count+'. Faturamento: Uber '+money(a.Uber.gross)+' | 99 '+money(a['99'].gross)+'.';if(a.Uber.count+a['99'].count===0)out+=' Não há plataforma identificada.';else if(a.Uber.count===a['99'].count)out+=' Empate na quantidade.';else out+=' '+(a.Uber.count>a['99'].count?'Uber':'99')+' teve '+Math.abs(a.Uber.count-a['99'].count)+' corrida(s) a mais.';}if(a.unknown.count)out+=' '+a.unknown.count+' sem plataforma identificada.';break;}
 case 'detalhes':if(p){const a=s.platformStats[p];out=p+': '+a.count+' corridas; '+money(a.gross)+'; '+fmt(a.km,2)+' km; '+duration(a.seconds)+' em corridas.';}else out='Resumo: '+s.count+' corridas finalizadas; faturamento '+money(s.gross)+'; '+fmt(s.km,2)+' km; '+duration(s.seconds)+' em corridas.\nUber: '+s.byPlatform.Uber+'; 99: '+s.byPlatform['99']+'; sem plataforma: '+s.byPlatform.unknown+'.\nCaixa operacional: '+money(s.cash)+'; combustível pago: '+money(s.paidFuel)+'.';break;
 case 'duracao':out='Tempo total registrado em corridas: '+duration(s.seconds)+'.'+(s.count?' Média: '+duration(s.seconds/s.count)+' por corrida.':'')+' Não equivale ao tempo online.';break;
 case 'distancia':out='Distância registrada nas corridas finalizadas: '+fmt(s.km,2)+' km.';if(s.count&&s.splitCount===s.count)out+=' Com passageiro: '+fmt(s.tripKm,2)+' km; até o embarque: '+fmt(s.pickupKm,2)+' km.';else if(s.count)out+=' Separação de embarque e trajeto disponível em '+s.splitCount+' de '+s.count+' corridas.';out+=' Não inclui deslocamentos fora dos registros.';break;
 case 'corridas':out='Total de corridas finalizadas: '+s.count+'.';break;
 case 'ticket':out='Valor médio por corrida finalizada: '+money(s.count?s.gross/s.count:null)+'.';break;
 case 'ganhos':out='Faturamento registrado: '+money(s.gross)+' em '+s.count+' corridas finalizadas.';break;
 case 'saldo':out='Caixa operacional: '+money(s.cash)+'. Após despesas pessoais: '+money(s.afterPersonal)+'. Caixa não é lucro.';break;
 case 'lucro':out=s.result==null?'Resultado operacional integral indisponível: cobertura de combustível '+s.coverage+'/'+s.count+' corridas'+(s.invalid?', com ciclos inconsistentes':'')+'. Caixa operacional: '+money(s.cash)+'.':'Resultado operacional estimado: '+money(s.result)+'. Considera combustível rateado e despesas operacionais registradas.';break;
 case 'despesas':out='Abastecimentos pagos: '+money(s.paidFuel)+'. Despesas operacionais líquidas: '+money(s.opCost)+'. Pessoais: '+money(s.personalCost)+'.';break;
 case 'combustivel_gasto':out='Total pago em abastecimentos: '+money(s.paidFuel)+' em '+s.fillCount+' registro(s). Não equivale necessariamente ao combustível consumido nas corridas.';break;
 case 'litros':out='Volume abastecido: '+fmt(s.liters,2)+' L em '+s.fillCount+' registro(s).';break;
 case 'abastecimentos':out=s.fillCount+' abastecimento(s) registrado(s), '+fmt(s.liters,2)+' L e '+money(s.paidFuel)+' pagos.';break;
 case 'preco_litro':out='Preço médio ponderado dos abastecimentos: '+money(s.avgPrice)+'/L.';break;
 case 'ganho_hora':out='Faturamento por hora em corrida: '+money(s.grossHour)+'. Não inclui espera online.';break;
 case 'ganho_km':out='Faturamento por km registrado: '+money(s.grossKm)+'. Não é lucro por km.';break;
 case 'consumo_kml':out='Consumo '+(s.cycles?'estimado por ciclos completos':'configurado, sem ciclo completo')+': '+fmt(s.consumption)+' km/L. Reflete a taxa atual do motor local.';break;
 case 'custo_km':out='Combustível por km: '+money(s.fuelKm)+' ('+(s.cycles?'ciclos completos':'estimativa configurada')+'). Não inclui todos os custos.';break;
 case 'meta':out=s.goal==null?'A meta de receita é mensal. Consulte a meta deste mês.':s.goal<=0?'Nenhuma meta mensal de receita configurada.':'Meta mensal: '+money(s.goal)+'. Faturamento: '+money(s.gross)+'. Progresso: '+fmt(s.gross/s.goal*100)+'%. Falta: '+money(Math.max(0,s.goal-s.gross))+'.';break;
 case 'cancelamentos':out='Cancelamentos reais registrados: '+s.canceled+(s.cancelRate==null?'. Sem base suficiente para uma taxa.':' ('+fmt(s.cancelRate)+'% dos registros reais).')+' Recusar uma oferta não é cancelar corrida aceita.';break;
 case 'espera':out=s.gap==null?'Não há intervalos suficientes entre corridas reais.':'Intervalo médio entre corridas reais: '+fmt(s.gap)+' min, em '+s.gapSamples+' intervalos. Pode incluir pausas; não mede necessariamente espera online.';break;
 case 'plano':out='Plano de ação:\n'+plan(s).map((x,i)=>(i+1)+'. '+x).join('\n');break;
 default:return null;
 }
 return out+(options.omitNote?'':note(s));
}
function looksLikeData(q){return /corrid|uber|\b99\b|combust|abastec|ganh|fatur|despes|gasto|saldo|meta|lucro|\bkm\b|quilometr|rod|motorista|trabalh|cancel|tempo|hora|litro|quanto fiz|rendeu/.test(normalize(q));}
function errorLabel(e){return e?.httpStatus?'HTTP '+e.httpStatus+(e.reason?' · '+String(e.reason).slice(0,60):''):e?.name==='AbortError'?'Tempo limite':'Rede ou resposta inválida';}
async function resolve(question,previous,{readData,interpret,now=new Date(),onPhase=()=>{}}){
 const q=String(question||'').trim().slice(0,600),prior=cleanQuery(previous);
 let query=parse(q,prior),source='Dados locais · sem consumo de API';
 if(!query.intent){
   onPhase('Consultando Gemini…');
   try{
     const raw=await interpret(q,prior),remote=cleanQuery(raw,prior);
     if(!remote)throw Error('Contrato inválido');
     query=remote;source='Gemini · interpretação + dados locais';
     if(['conversa','esclarecer','saudacao'].includes(query.intent)){
       if(query.intent==='saudacao')return {text:answer('saudacao'),source:'Gemini · conversa geral',context:prior};
       const generic='Posso consultar corridas, Uber/99, km, duração, ganhos, despesas, combustível e metas. Qual indicador você quer analisar?';
       return {text:looksLikeData(q)?generic:query.reply||generic,source:'Gemini · conversa geral',context:prior};
     }
   }catch(e){
     const detail=errorLabel(e);
     return {text:'Não consegui interpretar essa pergunta agora ('+detail+'). Posso consultar os dados locais, inclusive corridas, plataformas, duração, distância, ganhos, combustível e despesas. Qual indicador você quer?',source:'Modo local · '+detail,context:prior};
   }
 }
 if(query.intent==='saudacao')return {text:answer('saudacao'),source:'Dados locais · sem consumo de API',context:prior};
 const bundle=await readData(),s=snapshot(bundle.finance,bundle.rates,query.period,now),reply=answer(query.intent,s,query);
 if(!reply)throw Error('Consulta não implementada');
 return {text:reply,source:source+' · '+s.from.split('-').reverse().join('/')+' a '+s.to.split('-').reverse().join('/'),context:{...query,reply:''},snapshot:s};
}
return {snapshot,parse,answer,plan,range,cleanQuery,resolve,catalog:keys};
})();
if(typeof module!=='undefined')module.exports=AuraCore;
