/* Local application data. No Google service is used. */
(() => {
 const KEY='vexo-data-v2', BACKUP=KEY+'-backup', QUARANTINE=KEY+'-quarantine', clone=x=>JSON.parse(JSON.stringify(x));
 const date=(d=new Date())=>new Date(d-d.getTimezoneOffset()*60000).toISOString().slice(0,19);
 const uid=p=>p+crypto.randomUUID(), cents=x=>Math.round((x+Number.EPSILON)*100)/100;
 const empty=()=>({rides:[],fills:[],expenses:[],goals:{revenue:0,cash:0,reserve:0.15},settings:{fuel:6.2,consumption:10,fixed:0},offer:null,seen:[]});

 // Isolated lab origin: deterministic fictional records. Never replace existing data.
 function labSeed(){
   const d=empty();let seed=20261126;
   const rnd=()=>{seed=(Math.imul(1664525,seed)+1013904223)>>>0;return seed/4294967296;};
   const pick=a=>a[Math.floor(rnd()*a.length)],int=(a,b)=>a+Math.floor(rnd()*(b-a+1));
   const today=new Date();today.setHours(0,0,0,0);
   const dayAt=(offset,h=0,m=0)=>{const x=new Date(today);x.setDate(x.getDate()+offset);x.setHours(h,m,0,0);return x;};
   const days=60,eff=11.5,price=6.19;let odo=84500,kmCycle=0,fillCount=0,rideCount=0,expenseCount=0;
   d.settings={fuel:price,consumption:eff,fixed:4.5};d.goals={revenue:5500,cash:3500,reserve:.15};
   const addFill=(at,liters,unit)=>d.fills.push(['LAB-F-'+(++fillCount),date(at),Math.round(odo),cents(liters),unit,'Gasolina',true,'Posto fictício '+(fillCount%4+1)]);
   addFill(dayAt(-(days-1),5),32,price);
   for(let day=-(days-1);day<=0;day++){
     let at=dayAt(day,6,int(0,20));
     const n=day===0?12:int(7,13);
     for(let i=0;i<n;i++){
       const pickupKm=cents(.5+rnd()*3),tripKm=cents(2+rnd()*15),km=cents(pickupKm+tripKm),mins=int(3,9)+Math.ceil(tripKm*2.8)+int(0,4),gross=cents(Math.max(9,km*(1.45+rnd()*1.15)+rnd()*6)),fuel=cents(km*price/eff),reserve=cents(km*.15),fixed=cents(mins*4.5/60);
       const end=new Date(at.getTime()+mins*60000);
       d.rides.push(['LAB-R-'+(++rideCount),'finished',date(at),date(end),mins*60,km,pick(['Paid by Company','Cash']),gross,pick(['99','99','Uber']),pickupKm,tripKm,fuel,reserve,fixed,cents(gross-fuel-reserve-fixed),'Embarque fictício '+int(1,20),'Destino fictício '+int(1,20),cents(4.4+rnd()*.6)]);
       kmCycle+=km;odo+=km;at=new Date(end.getTime()+int(3,15)*60000);
     }
     if(day%4===0){const a=new Date(at.getTime()+60000);d.rides.push(['LAB-R-'+(++rideCount),'cancel trip',date(a),date(new Date(a.getTime()+180000)),180,0,'Paid by Company',0,'99',0,0,0,0,0,0,'Embarque fictício','Cancelada fictícia',4.8]);}
     const addExpense=(cat,desc,val)=>d.expenses.push(['LAB-E-'+(++expenseCount),date(dayAt(day)).slice(0,10),cat,desc,cents(val),0,'']);
     if(day%3===0)addExpense('Operacional','Lavagem e estacionamento fictícios',int(8,28));
     if(day%7===0)addExpense('Manutenção','Manutenção fictícia',int(35,130));
     if(day%2===0)addExpense('Pessoal','Alimentação fictícia',int(14,38));
     if(day%5===0)addExpense('Pedágio','Pedágio fictício',int(4,18));
     if(kmCycle>=270||day===0){addFill(new Date(at.getTime()+60000),Math.max(.01,kmCycle/eff),cents(price+(rnd()-.5)*.5));kmCycle=0;}
   }
   return d;
 }

 let storageNotice='';
 function parseState(raw){const d=JSON.parse(raw);if(!d||!['rides','fills','expenses','seen'].every(k=>Array.isArray(d[k]))||!d.goals||!d.settings||!('offer' in d)||!['rides','fills','expenses'].every(k=>d[k].every(r=>Array.isArray(r)&&typeof r[0]==='string'&&r[0])))throw Error('Estrutura inválida.');return d;}
 function read(){const raw=localStorage.getItem(KEY);if(raw!==null){try{return parseState(raw);}catch{const backup=localStorage.getItem(BACKUP);try{const d=parseState(backup);localStorage.setItem(QUARANTINE,raw);localStorage.setItem(KEY,backup);storageNotice='Dados recuperados de uma cópia local; confira os últimos registros.';return d;}catch{throw Error('Dados locais danificados. Original preservado; recuperação segura indisponível.');}}}const backup=localStorage.getItem(BACKUP);if(backup!==null){try{const d=parseState(backup);localStorage.setItem(KEY,backup);storageNotice='Cópia local restaurada; confira os últimos registros.';return d;}catch{throw Error('Cópia local inválida. Dados preservados.');}}const d=labSeed();localStorage.setItem(KEY,JSON.stringify(d));localStorage.setItem(BACKUP,JSON.stringify(d));return d;/* legacy migration disabled in isolated lab */ let old;try{old=JSON.parse(localStorage.getItem('vexo-pwa-state')||'null');}catch{throw Error('Histórico anterior inválido. Dados preservados.');}if(old){Object.assign(d.settings,old.settings);for(const r of old.runs||[])if(!d.rides.some(x=>x[0]===r.id)){const end=new Date();d.rides.push([r.id,'finished',date(new Date(end-r.min*60000)),date(end),r.min*60,r.km,'Paid by Company',r.gross]);}}return d;}
 const num=(n,min=0,max=1e9)=>{if(typeof n!=='number'||!Number.isFinite(n)||n<min||n>max)throw Error('Confira os valores numéricos.');return n;};
 const validDate=(s,kind)=>{if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$/.test(s))throw Error('Data inválida.');const full=s.length===10?s+'T00:00:00':s.length===16?s+':00':s;const n=Date.parse(full+'Z');if(!Number.isFinite(n)||new Date(n).toISOString().slice(0,19)!==full||(kind==='day'&&s.length!==10)||(kind==='time'&&s.length===10))throw Error('Data inválida.');return s.length===10?s:full;};
 function rates(d){let anchor=null,liters=0,cost=0,km=0,total=0,totalL=0,cycles=0;for(const r of [...d.fills].sort((a,b)=>a[1].localeCompare(b[1]))){if(anchor){liters+=r[3];cost+=cents(r[3]*r[4]);}if(r[6]){if(anchor&&r[2]===anchor[2])continue;if(anchor&&r[2]>anchor[2]){km+=r[2]-anchor[2];total+=cost;totalL+=liters;cycles++;}anchor=r;liters=cost=0;}}return {fuel:km?total/km:d.settings.fuel/d.settings.consumption,eff:km?km/totalL:d.settings.consumption,reserve:d.goals.reserve,fixed:d.settings.fixed,cycles};}
 function repeatedFull(rows){let last=null,count=0;for(const x of rows){if(x[6]){if(x[2]===last)count++;last=x[2];}}return count;}
 function quote(r,d){const q=rates(d),km=r.pickupKm+r.tripKm,min=r.pickupMin+r.tripMin,fuel=cents(km*q.fuel),reserve=cents(km*q.reserve),fixed=cents(min/60*q.fixed);return {...r,km:cents(km),min,fuel,reserve,fixed,profit:cents(r.gross-fuel-reserve-fixed),rates:q};}
 const finance=d=>({rides:d.rides,fills:d.fills,expenses:d.expenses,goals:d.goals});
 function state(d){const rows=d.rides.filter(r=>r[1]==='finished'&&r[3].slice(0,10)===date().slice(0,10));const sum=i=>cents(rows.reduce((a,r)=>a+(Number(r[i])||0),0));const unknown=rows.filter(r=>![11,12,13,14].every(i=>typeof r[i]==='number'&&Number.isFinite(r[i]))).length;return {storageNotice:storageNotice||(localStorage.getItem(QUARANTINE)!==null?'Houve recuperação local; confira os últimos registros.':''),ride:d.offer?.status==='offer'?quote(d.offer,d):d.offer,rates:rates(d),summary:{today:date().slice(0,10),count:rows.length,gross:sum(7),km:sum(5),minutes:sum(4)/60,fuel:unknown?null:sum(11),reserve:unknown?null:sum(12),fixed:unknown?null:sum(13),profit:unknown?null:sum(14),unknownCosts:unknown,recent:rows.slice(-10).reverse().map(r=>({id:r[0],app:r[8],gross:r[7],km:r[5],profit:r[14],time:r[3]}))}};}
 function upsert(list,before,after,prefix){const r=clone(after);if(before){const i=list.findIndex(x=>x[0]===before[0]);if(i<0||JSON.stringify(list[i])!==JSON.stringify(before))throw Error('Registro atualizado em outra tela. Atualize e tente novamente.');r[0]=before[0];list[i]=r;}else{r[0]=uid(prefix);list.push(r);}return r;}

 const BACKUP_LIMIT=1500000;
 function backupPayload(d){return {format:'VEXO-backup',version:1,createdAt:new Date().toISOString(),data:{rides:d.rides,fills:d.fills,expenses:d.expenses,goals:d.goals,settings:d.settings,seen:d.seen}};}
 function validateBackup(text){
  if(typeof text!=='string'||!text.length||text.length>BACKUP_LIMIT)throw Error('Arquivo vazio ou acima de 1,5 MB.');
  let b;try{b=JSON.parse(text);}catch{throw Error('Arquivo JSON inválido.');}
  if(b?.format!=='VEXO-backup'||b.version!==1||!b.data)throw Error('Formato de backup não reconhecido.');
  const x=b.data,checkId=id=>{if(typeof id!=='string'||!id.trim()||id.length>200)throw Error('Identificador inválido.');};
  for(const k of ['rides','fills','expenses','seen'])if(!Array.isArray(x[k])||x[k].length>20000)throw Error('Lista inválida no backup.');
  for(const k of ['rides','fills','expenses']){const ids=new Set();for(const r of x[k]){if(!Array.isArray(r))throw Error('Registro inválido.');checkId(r[0]);if(ids.has(r[0]))throw Error('Registros duplicados no backup.');ids.add(r[0]);}}
  for(const r of x.rides){if(r.length<8||r.length>18||!['finished','unfinished','cancel trip'].includes(r[1]))throw Error('Corrida inválida.');
   r[2]=validDate(r[2],'time');if(r[3]!=null&&r[3]!==''){r[3]=validDate(r[3],'time');if(r[3]<r[2])throw Error('Horário inválido.');}else if(r[1]==='finished')throw Error('Finalização ausente.');
   [4,5,7].forEach(i=>num(r[i]));if(typeof r[6]!=='string'||r[6].length>200)throw Error('Forma de pagamento inválida.');
   if(r[8]!=null&&(typeof r[8]!=='string'||r[8].length>100))throw Error('Plataforma inválida.');
   for(const i of [9,10,11,12,13])if(r[i]!=null)num(r[i]);if(r[14]!=null)num(r[14],-1e9,1e9);
   for(const i of [15,16])if(r[i]!=null&&(typeof r[i]!=='string'||r[i].length>1000))throw Error('Endereço inválido.');
   if(r[17]!=null)num(r[17],0,5);
  }
  for(const r of x.fills){if(r.length!==8)throw Error('Abastecimento incompleto.');r[1]=validDate(r[1],'time');num(r[2],0,1e8);num(r[3],.01,1e5);num(r[4],.01,1000);if(typeof r[6]!=='boolean'||!['Gasolina','Etanol','Diesel'].includes(r[5])||typeof r[7]!=='string'||r[7].length>1000)throw Error('Abastecimento inválido.');}
  x.fills.sort((a,b)=>a[1].localeCompare(b[1]));for(let i=1;i<x.fills.length;i++)if(x.fills[i][1]===x.fills[i-1][1]||x.fills[i][2]<x.fills[i-1][2])throw Error('Ordem de abastecimentos inválida.');
  const rideIds=new Set(x.rides.map(r=>r[0]));for(const r of x.expenses){if(r.length!==7)throw Error('Despesa incompleta.');r[1]=validDate(r[1],'day');num(r[4],.01);num(r[5]);if(r[5]>r[4]||!['Pedágio','Manutenção','Fixo','Operacional','Pessoal'].includes(r[2])||typeof r[3]!=='string'||!r[3].trim()||r[3].length>120||typeof r[6]!=='string'||r[6]&&!rideIds.has(r[6]))throw Error('Despesa inválida.');}
  if(!x.goals||!x.settings)throw Error('Parâmetros ausentes.');for(const k of ['revenue','cash','reserve'])num(x.goals[k]);num(x.settings.fuel,.01,1000);num(x.settings.consumption,.01,1000);num(x.settings.fixed,0,1e6);x.seen.forEach(checkId);
  const {revenue,cash,reserve}=x.goals,{fuel,consumption,fixed}=x.settings;
  return {rides:x.rides,fills:x.fills,expenses:x.expenses,goals:{revenue,cash,reserve},settings:{fuel,consumption,fixed},offer:null,seen:[...new Set(x.seen)]};
 }
 function backupCounts(d){return {rides:d.rides.length,fills:d.fills.length,expenses:d.expenses.length};}

 function call(name,args,d){switch(name){
 case 'backupExport':{const text=JSON.stringify(backupPayload(d));validateBackup(text);return text;}
 case 'backupInspect':{const b=validateBackup(args[0]);return {...backupCounts(b),canRestore:!d.rides.length&&!d.fills.length&&!d.expenses.length&&!['offer','accepted'].includes(d.offer?.status)};}
 case 'backupRestore':{if(args[1]!=='RESTORE_EMPTY')throw Error('Confirmação de restauração ausente.');if(d.rides.length||d.fills.length||d.expenses.length||['offer','accepted'].includes(d.offer?.status))throw Error('Esta instalação já contém registros ou corrida ativa. Nenhum dado foi alterado.');const b=validateBackup(args[0]);Object.assign(d,b);return backupCounts(d);}
 case 'dadosDashboard99':return d.rides.map(r=>r.slice(0,8));
 case 'dadosDashboardFuel':return d.fills;
 case 'financeDados':return finance(d);
 case 'auraDados':return {finance:finance(d),rates:rates(d)};
 case 'webState':return state(d);
 case 'settings':return d.settings;
 case 'saveSettings': {const s=args[0];num(s.fuel,.01,1000);num(s.consumption,.01,1000);num(s.fixed,0,1e6);d.settings={fuel:s.fuel,consumption:s.consumption,fixed:s.fixed};return d.settings;}
 case 'salvarDashboardFuel':{const [before,input]=args,r=clone(input);if(r.length!==8)throw Error('Abastecimento incompleto.');r[1]=validDate(r[1],'time');num(r[2],0,1e8);num(r[3],.01,1e5);num(r[4],.01,1000);if(typeof r[6]!=='boolean'||!['Gasolina','Etanol','Diesel'].includes(r[5]))throw Error('Combustível inválido.');const priorRepeated=repeatedFull(d.fills);upsert(d.fills,before,r,'FUEL-');d.fills.sort((a,b)=>a[1].localeCompare(b[1]));for(let i=1;i<d.fills.length;i++)if(d.fills[i][1]===d.fills[i-1][1]||d.fills[i][2]<d.fills[i-1][2])throw Error('Confira a ordem das datas e dos odômetros.');if(repeatedFull(d.fills)>priorRepeated)throw Error('Dois tanques cheios com o mesmo odômetro. Edite o registro anterior.');return d.fills;}
 case 'financeSalvarDespesa':{const [before,input]=args,r=clone(input);if(!Array.isArray(r)||r.length!==7)throw Error('Despesa incompleta.');r[1]=validDate(r[1],'day');num(r[4],.01);num(r[5]);if(r[5]>r[4]||!['Pedágio','Manutenção','Fixo','Operacional','Pessoal'].includes(r[2])||typeof r[3]!=='string'||!r[3].trim()||r[3].length>120)throw Error('Confira categoria, descrição e reembolso.');r[3]=r[3].trim();if(typeof r[6]!=='string'||(r[6]&&!d.rides.some(x=>x[0]===r[6])))throw Error('Corrida não encontrada.');if(!before){const id=r[0];if(id){if(typeof id!=='string'||!/^DS-REQ-[a-zA-Z0-9-]{1,80}$/.test(id))throw Error('Identificador de despesa inválido.');const found=d.expenses.find(x=>x[0]===id);if(found){if(JSON.stringify(found)!==JSON.stringify(r))throw Error('Envio já utilizado com outros dados. Abra um novo registro.');return finance(d);}d.expenses.push(r);}else{if(d.expenses.some(x=>JSON.stringify(x.slice(1))===JSON.stringify(r.slice(1))))return finance(d);upsert(d.expenses,null,r,'DS-');}}else upsert(d.expenses,before,r,'DS-');return finance(d);}
 case 'financeSalvarMetas':{const [before,g]=args;if(JSON.stringify(before)!==JSON.stringify(d.goals))throw Error('Atualize as metas antes de salvar.');['revenue','cash','reserve'].forEach(k=>num(g[k]));d.goals={revenue:g.revenue,cash:g.cash,reserve:g.reserve};return finance(d);}
 case 'editarLinhaDashboard99':{const [i,before,after]=args;if(String(before[0]).startsWith('MOB-'))throw Error('Corrida simulada finalizada é preservada no histórico.');[4,5,7].forEach(k=>num(after[k]));if(!['finished','unfinished','cancel trip'].includes(after[1]))throw Error('Situação inválida.');if(after[1]==='finished'&&!after[3])throw Error('Data de finalização ausente.');after[2]=validDate(after[2],'time');if(after[3]){after[3]=validDate(after[3],'time');if(after[3]<after[2])throw Error('Finalização anterior ao início.');}const existing=d.rides.find(x=>x[0]===before[0]);if(!existing||JSON.stringify(existing.slice(0,8))!==JSON.stringify(before.slice(0,8)))throw Error('Registro atualizado em outra tela. Atualize e tente novamente.');const next=existing.slice();for(let k=1;k<8;k++)next[k]=after[k];if([4,5,7].some(k=>next[k]!==existing[k])){for(const k of [11,12,13,14])if(k<next.length)next[k]=null;}upsert(d.rides,existing,next,'R-');return d.rides.map(r=>r.slice(0,8));}
 case 'webAction':{const [action,id]=args;let r=d.offer;if(action==='new'){if(r&&['offer','accepted'].includes(r.status))return state(d);r={id:uid('MOB-'),status:'offer',app:Math.random()<.5?'99':'Uber',gross:cents(12+Math.random()*48),pickupKm:1,tripKm:cents(3+Math.random()*15),pickupMin:4,tripMin:Math.round(8+Math.random()*30),rating:cents(4.5+Math.random()*.5),origin:'Embarque simulado',destination:'Destino simulado'};d.seen.push(r.id);d.offer=r;return state(d);}if(!r||r.id!==id)throw Error('A oferta mudou. Atualize.');if(action==='accept'){if(r.status==='accepted')return state(d);if(r.status!=='offer')throw Error('A corrida não está disponível para aceitar.');d.offer={...quote(r,d),status:'accepted'};}else if(action==='finish'){if(r.status==='finished')return state(d);if(r.status!=='accepted')throw Error('Aceite antes de finalizar.');if(!d.rides.some(x=>x[0]===r.id)){const end=new Date();d.rides.push([r.id,'finished',date(new Date(end-r.min*60000)),date(end),r.min*60,r.km,'Paid by Company',r.gross,r.app,r.pickupKm,r.tripKm,r.fuel,r.reserve,r.fixed,r.profit,r.origin,r.destination,r.rating]);}r.status='finished';}else if(action==='reject'){if(r.status==='rejected')return state(d);if(r.status!=='offer')throw Error('Ação inválida para esta corrida.');r.status='rejected';}else throw Error('Ação inválida para esta corrida.');return state(d);}
 default:throw Error('Função não disponível: '+name);
 }}
 const reads=new Set(['dadosDashboard99','dadosDashboardFuel','financeDados','auraDados','webState','settings','backupExport','backupInspect']);
 async function invoke(name,...args){const execute=()=>{const d=read(),result=call(name,args,d);if(!reads.has(name)){const next=JSON.stringify(d);if(next!==localStorage.getItem(KEY)){localStorage.setItem(KEY,next);try{localStorage.setItem(BACKUP,next);}catch{storageNotice='Dados salvos, mas a cópia de segurança local não pôde ser atualizada.';console.warn(storageNotice);}window.dispatchEvent(new Event('vexo-update'));}}return clone(result);};return navigator.locks?navigator.locks.request(KEY,execute):execute();}
 function runner(ok=()=>{},fail=console.error){return new Proxy({}, {get(_,key){if(key==='withSuccessHandler')return f=>runner(f,fail);if(key==='withFailureHandler')return f=>runner(ok,f);return (...args)=>invoke(key,...args).then(ok).catch(fail);}});}
 window.Vexo={invoke,get run(){return runner();}};
 window.addEventListener('storage',e=>{if(e.key===KEY)refresh();});window.addEventListener('focus',refresh);window.addEventListener('vexo-update',refresh);
 function refresh(){if(typeof window.pull99==='function')window.pull99();else if(typeof window.pull==='function')window.pull();else if(typeof window.rpc==='function')window.rpc();}
})();
