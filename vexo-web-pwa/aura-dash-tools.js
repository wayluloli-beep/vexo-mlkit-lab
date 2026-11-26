/* LAB: read-only dashboard tools. Uses the existing Finance Core and original Fuel functions. */
const AuraDashTools=(()=>{
'use strict';
const sum=(a,f)=>a.reduce((t,r)=>t+f(r),0),div=(a,b)=>b>0?a/b:null;
function normalize(rows){return rows.map((r,i)=>({r,i})).filter(({r})=>r.some((v,k)=>v!==''&&v!==null&&v!==undefined&&!(k===6&&v===false))).map(({r,i})=>{
 const [id,date,odo,liters,price,fuel,full,station]=r;
 if(!id||!date||!Number.isFinite(Date.parse(date))||[odo,liters,price].some(x=>x===''||!Number.isFinite(Number(x)))||Number(odo)<0||Number(liters)<=0||Number(price)<=0||!['Gasolina','Etanol','Diesel'].includes(fuel)||typeof full!=='boolean')throw Error('Registro inválido na posição '+(i+1));
 return {id:String(id),date:String(date),odo:+odo,liters:+liters,price:+price,fuel,full,station:String(station||'Sem posto'),cost:Math.round((+liters*+price+Number.EPSILON)*100)/100};
 }).sort((a,b)=>a.date.localeCompare(b.date)||a.odo-b.odo);}
function buildCycles(a){
 let anchor=null, litres=0,cost=0,types=new Set(),out=[];
 for(const r of a){
  if(anchor){litres+=r.liters;cost+=r.cost;types.add(r.fuel);}
  if(r.full){
   if(anchor&&r.odo===anchor.odo)continue;
   if(anchor&&r.odo>anchor.odo&&litres>0)out.push({date:r.date,start:anchor.date,km:r.odo-anchor.odo,liters:litres,cost,eff:(r.odo-anchor.odo)/litres,costKm:cost/(r.odo-anchor.odo),fuel:types.size===1?[...types][0]:'Misto'});
   anchor=r;litres=0;cost=0;types=new Set([r.fuel]);
  }
 }
 return out;
}
function stats(a,c){
 let cost=sum(a,r=>r.cost),liters=sum(a,r=>r.liters),km=sum(c,r=>r.km),used=sum(c,r=>r.liters),cycleCost=sum(c,r=>r.cost);
 return {n:a.length,cost,liters,km,used,cycleCost,eff:div(km,used),cKm:div(cycleCost,km),price:div(cost,liters),avg:div(cost,a.length),cycles:c.length};
}

const norm=q=>String(q||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim(),money=n=>Number.isFinite(n)?n.toLocaleString('pt-BR',{style:'currency',currency:'BRL'}):'indisponível',num=(n,d=2)=>Number.isFinite(n)?n.toLocaleString('pt-BR',{maximumFractionDigits:d,minimumFractionDigits:d}):'indisponível',day=x=>x.date.slice(0,10),hour=x=>+x.date.slice(11,13),wd=x=>new Date(day(x)+'T00:00:00Z').getUTCDay(),days=['domingo','segunda','terça','quarta','quinta','sexta','sábado'],group=(a,key)=>{const m=new Map();for(const x of a){const k=key(x);if(!m.has(k))m.set(k,[]);m.get(k).push(x)}return [...m];};
const scope=q=>/\b(?:corrid|ganh|fatur|receit|lucro|caixa|saldo|meta|combustivel|gasolina|etanol|diesel|litro|abastec|posto|consumo|odometro|despes|gasto|pedagio|manutenc|reembolso|ticket|horari|dia|semana|mes|km|uber|99|heatmap|mapa de calor|jornada|cancel|pagamento|rentabil|reserva)\w*\b/.test(q);
const write=q=>/^(?:(?:por favor|aura)[, ]+)?(?:coloc[ae]|poe|bota|adicion[ae]|lan[cç]a|registr[ae]|salv[ae]|alter[ae]|mud[ae]|apag[ae]|exclu[ai]|delet[ae]|cadastr[ae]|atualiz[ae]|ajust[ae]|defin[ae])\b/.test(q);
function period(q,prior,now){const t=norm(q),p=/\b(?:desde sempre|todo o periodo|historico completo|total geral)\b/.test(t)?'total':/\b(?:30|trinta) dias\b/.test(t)?'trinta':/\b(?:15|quinze) dias\b/.test(t)?'quinze':/\b(?:semana|7 dias)\b/.test(t)?'semana':/\b(?:mes|mensal)\b/.test(t)?'mes':/\bontem\b/.test(t)?'ontem':/\b(?:hoje|hj)\b/.test(t)?'hoje':null;return p||prior?.period||'hoje';}
function dateRange(q,p,now){const m=[...q.matchAll(/\b(\d{1,2})\/(\d{1,2})(?:\/(\d{4}))?\b/g)].slice(0,2);if(!m.length)return AuraCore.range(p,now);const ds=m.map(a=>(a[3]||now.getFullYear())+'-'+a[2].padStart(2,'0')+'-'+a[1].padStart(2,'0'));if(ds.some(x=>!Number.isFinite(Date.parse(x+'T00:00:00Z'))||new Date(x+'T00:00:00Z').toISOString().slice(0,10)!==x)||ds.length===2&&ds[0]>ds[1])throw Error('Data inválida');return [ds[0],ds[1]||ds[0]];}
const fuelMetrics=['abastecimentos','dias abastecidos','compras por semana','litros comprados','preço médio ponderado','consumo medido por ciclo','custo/km','distância medida','valor médio por compra','postos e preços','tipos de combustível','ciclos completos','histórico','mapa de calor de compras','evolução mensal','meta ilustrativa de economia'];
function summarize(a){const gross=sum(a,x=>x.revenue),sec=sum(a,x=>x.seconds),active=new Set(a.map(day)).size;return {count:a.length,gross,sec,km:sum(a,x=>x.km),active,eff:div(gross,sec/60),ticket:div(gross,a.length),daily:div(gross,active)};}
const line=(k,a)=>k+': '+a.count+' corridas · '+money(a.gross)+' · '+money(a.eff)+' por min em corrida · ticket '+money(a.ticket);
const fuelLine=(k,x)=>k+': '+x.n+' compras · '+money(x.cost)+' · '+num(x.liters,1)+' L · '+money(x.price)+'/L · '+x.cycles+' ciclos · '+num(x.eff)+' km/L · '+money(x.cKm)+'/km';
function analyze(q,b,prior=null,now=new Date()){
 const t=norm(q),p=period(t,prior,now),[from,to]=dateRange(t,p,now),inside=x=>day(x)>=from&&day(x)<=to,raw=b.finance;
 const F=Core.normalize(raw),s=Core.stats(F,from,to),f=normalize(raw.fills),fc=buildCycles(f),a=f.filter(inside),c=fc.filter(inside);
 const fuelType=/\betanol\b/.test(t)?'Etanol':/\bgasolina\b/.test(t)?'Gasolina':/\bdiesel\b/.test(t)?'Diesel':/\bmisto\b/.test(t)?'Misto':null;
 const af=fuelType?a.filter(x=>x.fuel===fuelType):a,cf=fuelType?c.filter(x=>x.fuel===fuelType):c,ft=stats(af,cf);
 const driver=s.r,ar=s.e;
 const span=Math.round((Date.parse(to)-Date.parse(from))/86400000)+1;
 const dateLabel=from===to?from:from+' a '+to;
 const out=(text,domain)=>({text,source:'VEXO LAB · '+domain+' · '+dateLabel,context:{period:p,domain},kind:'success'});
 if(/(?:quais|que|o que).*(?:dados|funcoes|indicadores|consegue|consultar)/.test(t))return out('Driver: corridas, receita, ticket, distância, duração, pagamentos, horários, dias, mapas de calor, mensal e estratégia.\nFuel: '+fuelMetrics.join(', ')+'.\nFinanceiro: caixa, despesas, reembolsos, margem, resultado, cobertura, metas e reserva. Consultas são somente leitura.','Catálogo');
 if(/(?:posto|abastec|combustivel|gasolina|etanol|diesel|litro|consumo|ciclo|odometro)/.test(t)){
  if(/posto/.test(t)&&/preco|barat|caro|melhor|compar|lista|qual/.test(t)){const z=group(af,x=>x.station+' · '+x.fuel).map(([k,r])=>[k,stats(r,[])]).sort((a,b)=>a[1].price-b[1].price);return out(z.length?z.slice(0,15).map(([k,r])=>k+': '+money(r.price)+'/L · '+r.n+' compras · '+money(r.cost)).join('\n'):'Sem compras no período.','Fuel');}
  if(/mapa de calor|heatmap|pico.*abastec|horario.*abastec/.test(t)){const v=/litro/.test(t)?x=>x.liters:/quantidade|compras/.test(t)?()=>1:x=>x.cost;const z=group(af,x=>days[wd(x)]+' '+hour(x)+'h').map(([k,r])=>({k,v:sum(r,v),n:r.length})).sort((a,b)=>b.v-a.v);return out(z.length?z.slice(0,5).map(x=>x.k+': '+(/litro/.test(t)?num(x.v)+' L':/quantidade|compras/.test(t)?x.v+' compras':money(x.v))+' ('+x.n+' registros)').join('\n')+'\nHorário da compra, não do consumo.':'Sem compras.','Fuel');}
  if(/por mes|mensal|evolucao/.test(t)){const keys=[...new Set(af.map(x=>x.date.slice(0,7)))].sort();return out(keys.map(k=>fuelLine(k,stats(af.filter(x=>x.date.startsWith(k)),cf.filter(x=>x.date.startsWith(k))))).join('\n')||'Sem compras.','Fuel');}
  if(/dias.*abastec|dias.*posto|dias com compra/.test(t))return out(new Set(af.map(day)).size+' dias com abastecimento em '+span+' dias corridos.','Fuel');
  if(/por semana|semanal/.test(t))return out(num(ft.n*7/span)+' compras/semana · '+num(ft.liters*7/span)+' L/semana · '+money(ft.cost*7/span)+'/semana.','Fuel');
  if(/entre.*abastec|intervalo.*compra/.test(t))return out('Intervalo médio entre compras: '+num(af.length>1?(Date.parse(af.at(-1).date)-Date.parse(af[0].date))/86400000/(af.length-1):null)+' dias.','Fuel');
  if(/historico|ultimos? abastec|liste.*abastec/.test(t))return out(af.slice().reverse().slice(0,10).map(x=>day(x)+' · '+x.station+' · '+x.fuel+' · '+num(x.liters)+' L · '+money(x.cost)+' · odômetro '+num(x.odo,0)+' km').join('\n')||'Sem compras.','Fuel');
  if(/ciclos? completos|consumo por ciclo|ciclo.*misto|ciclo.*flex/.test(t)){return out(ft.cycles+' ciclos fechados · '+num(ft.km,0)+' km · '+num(ft.used)+' L repostos · '+num(ft.eff)+' km/L · '+money(ft.cKm)+'/km. Misto significa tipos diferentes registrados entre dois tanques cheios; não mede combustível residual.','Fuel');}
  if(/consumo|km\/l|km por litro/.test(t)&&!/quanto.*gastei|gasto.*consumo/.test(t))return out('Consumo medido no período: '+num(ft.eff)+' km/L em '+ft.cycles+' ciclos completos. '+(ft.cycles?'Fechamentos no recorte.':'Sem ciclos completos no recorte; taxa atual configurada/medida: '+num(b.rates.eff)+' km/L.'),'Fuel');
  if(/custo.*(?:km|quilometro)|combustivel por km/.test(t))return out('Custo/km medido: '+money(ft.cKm)+' em '+ft.cycles+' ciclos fechados; taxa atual do motor '+money(b.rates.fuel)+'/km.','Fuel');
  if(/preco.*litro|valor.*litro|quanto.*litro/.test(t)&&!/quantos litros/.test(t))return out('Preço médio ponderado: '+money(ft.price)+'/L.','Fuel');
  if(/litros|volume/.test(t)&&!/quanto.*gastei/.test(t))return out(num(ft.liters)+' L comprados em '+ft.n+' abastecimentos.','Fuel');
  if(/gasto|gastei|paguei|desembolso/.test(t)&&!/consumido|estimado/.test(t))return out('Total pago em abastecimentos: '+money(ft.cost)+' em '+ft.n+' compras. Não equivale ao combustível consumido.','Fuel');
  if(/distancia medida|km medidos/.test(t))return out(num(ft.km,0)+' km medidos nos ciclos fechados.','Fuel');
  if(/valor medio|ticket.*abastec/.test(t))return out('Valor médio por compra: '+money(ft.avg)+' · '+num(div(ft.liters,ft.n))+' L/compra.','Fuel');
  if(/quant[oa]s?|total|resumo|painel|dashboard|abastecimentos/.test(t))return out(fuelLine(fuelType||'Todos os combustíveis',ft),'Fuel');
 }
 if(/despesas? por categoria|gastos? por categoria|maior despesa|qual.*mais.*gast|reembolso|pedagio|manutencao|alimentacao|gastos pessoais/.test(t)){
  let rows=group(ar,x=>x.category).map(([k,r])=>[k,sum(r,x=>x.net),sum(r,x=>x.refund),r.length]).sort((a,b)=>b[1]-a[1]);
  const cat=/pedagio/.test(t)?'Pedágio':/manutencao/.test(t)?'Manutenção':/pessoal|alimentacao/.test(t)?'Pessoal':null;
  if(cat)rows=rows.filter(x=>x[0]===cat);
  return out(rows.map(x=>x[0]+': '+money(x[1])+' líquidos · '+money(x[2])+' reembolsos · '+x[3]+' registros').join('\n')||'Sem despesas nessa categoria.','Financeiro');
 }
 if(/historico.*despesa|liste.*despesa/.test(t))return out(ar.slice().reverse().slice(0,10).map(x=>x.date+' · '+x.category+' · '+x.description+' · '+money(x.net)).join('\n')||'Sem despesas.','Financeiro');
 if(/margem|cobertura|combustivel consumido|combustivel estimado|resultado operacional/.test(t)){
  const margin=s.coveredRevenue-s.fuelEst;
  return out('Cobertura: '+s.covered.length+'/'+s.r.length+' corridas; combustível estimado '+money(s.covered.length?s.fuelEst:null)+'; margem após combustível '+money(s.covered.length?margin:null)+'; margem por hora em corrida '+money(div(margin,sum(s.covered,x=>x.seconds)/3600))+'; resultado operacional '+money(s.result)+'. '+(s.inconsistent.length?s.inconsistent.length+' ciclos com km incompatíveis. ':'')+'Margem não é lucro após todas as despesas.','Financeiro');
 }
 if(/reserva.*(?:km|manutencao)|meta.*saldo|meta.*caixa/.test(t)){const [a,b]=AuraCore.range('mes',now),m=Core.stats(F,a,b);return out('Meta mensal de saldo operacional: '+money(F.goals.cash)+'; realizado '+money(m.cash)+'; falta '+money(Math.max(0,F.goals.cash-m.cash))+'. Reserva por km: '+money(F.goals.reserve)+'; sugerida no mês '+money(m.reserve)+'. Não descontada do caixa.','Financeiro');}
 if(/pagamento|dinheiro.*cartao|forma.*pag/.test(t)){const byId=new Map(raw.rides.map(r=>[r[0],r[6]]));return out(group(driver,x=>byId.get(x.id)||'Sem info').map(([k,r])=>line(k,summarize(r))).join('\n')||'Sem corridas.','Driver');}
 if(/melhor.*(?:horario|hora|faixa)|horario de ouro|hora.*mais.*(?:ganh|rent)|pico.*corrid|mapa de calor|heatmap|por hora|por horario|melhor.*dia|por dia da semana|top.*dia|receita por dia|evolucao.*mensal|por mes|ticket.*mensal/.test(t)&&!/quanto (?:eu )?ganh.*por hora|faturamento por hora/.test(t)){
  const by=/mapa de calor|heatmap/.test(t)?x=>days[wd(x)]+' '+hour(x)+'h':/dia da semana|melhor.*dia/.test(t)?x=>days[wd(x)]:/top.*dia|receita por dia/.test(t)?day:/mensal|por mes/.test(t)?x=>x.date.slice(0,7):/faixa|horario de ouro/.test(t)?x=>{const h=hour(x);return h>=6&&h<12?'Manhã (06–12h)':h>=12&&h<15?'Almoço (12–15h)':h>=15&&h<19?'Tarde (15–19h)':h>=19&&h<22?'Noite (19–22h)':'Outros'}:x=>String(hour(x)).padStart(2,'0')+'h';
  let z=group(driver,by).map(([k,r])=>[k,summarize(r)]);
  if(/melhor|ouro|top|pico/.test(t)){const byDay=/melhor.*dia/.test(t);if(byDay)z=z.filter(x=>x[1].active>=2);else if(!/pico|top.*dia/.test(t))z=z.filter(x=>x[1].count>=5);z.sort((a,b)=>(byDay?b[1].daily-a[1].daily:/pico/.test(t)?b[1].count-a[1].count:/receita|fatur|top.*dia/.test(t)?b[1].gross-a[1].gross:b[1].eff-a[1].eff));}
  else z.sort((a,b)=>a[0].localeCompare(b[0]));
  return out(z.length?z.slice(0,24).map(([k,r])=>line(k,r)).join('\n')+'\nEficiência em corrida, não tempo online.':'Amostra insuficiente no período.','Driver');
 }
 if(/dias ativos|corridas por dia|receita media diaria|tempo medio|duracao media|distancia media/.test(t)){const x=summarize(driver);return out(x.active+' dias ativos · '+num(div(x.count,x.active))+' corridas/dia · '+money(x.daily)+'/dia · '+num(div(x.sec/60,x.count))+' min/corrida · '+num(div(x.km,x.count))+' km/corrida.','Driver');}
 return null;
}
let memory=null,pending=null;
async function handle(q,{readData,now=new Date()}){
 const t=norm(q);
 if(write(t)||/^\d+(?:[,.]\d+)?$/.test(t)){
  pending=null;
  if(!/ganh|fatur|meta|combustivel|abastec|despes|pedagio|manutenc|pessoal|saldo/.test(t))return {text:'Esse valor é ganho de corridas, combustível, outra despesa ou meta? Nenhum registro foi alterado.',source:'Aura · confirmação necessária',kind:'clarify'};
  return {text:'Entendi a categoria, mas a gravação por chat ainda não foi habilitada. Use o dashboard correspondente para salvar. Nenhum dado foi alterado.',source:'Aura · somente leitura',kind:'clarify'};
 }
 if(/^(?:sim|confirmo|pode salvar|pode registrar|combustivel|ganhos?|meta|despesa)[.! ]*$/.test(t))return {text:'Nenhuma alteração está pendente. Para registrar valores, use o dashboard correspondente.',source:'Aura · somente leitura',kind:'clarify'};
 if(!scope(t)&&!(/^(?:e )?(?:ontem|hoje|na 99|na uber|essa semana|esse mes|e o total|mais detalhes)[?! ]*$/.test(t)&&memory))return null;
 // Leave offer calculations, vehicle parameter statements, general strategy and unrelated conversation to LFX.
 if(/^(?:meu carro|meu consumo|a gasolina custa|o etanol custa)/.test(t)||/\b(oferta|simule|simular)\b/.test(t)||AuraDashboardContext.isStrategy(q))return null;
 if(!/\?|^(?:quanto|quantos|quantas|qual|quais|como|onde|quando|me mostre|mostra|liste|lista|resumo|historico|e |consumo|ticket|faturamento|saldo|lucro|despesas|corridas|ganhos|meta|abastecimentos|mapa de calor|custo|receita|melhor|horario|dias|total)\b/.test(t))return null;
 const b=await readData();let r=analyze(q,b,memory,now);if(r){memory={period:r.context.period,domain:r.context.domain};return r;}
 let parsed=AuraCore.parse(q,memory?.query||null,now);
 if(!parsed?.intent||['plano','saudacao','conversa','esclarecer'].includes(parsed.intent))return null;
 let s=AuraCore.snapshot(b.finance,b.rates,parsed.period,now);
 const text=AuraCore.answer(parsed.intent,s,parsed);
 if(!text)return null;
 memory={period:parsed.period,query:parsed};
 return {text,source:'VEXO LAB · dados locais · '+s.from+' a '+s.to,kind:'success'};
}
return {handle,analyze};
})();
