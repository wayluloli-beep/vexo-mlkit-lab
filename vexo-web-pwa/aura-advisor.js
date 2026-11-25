/* Read-only operational analysis. Synthetic rides are excluded from work advice. */
const AuraAdvisor=(()=>{
const normalize=x=>String(x||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const money=x=>x.toLocaleString('pt-BR',{style:'currency',currency:'BRL'}),round=x=>Math.round((x+Number.EPSILON)*100)/100;
const fmt=x=>x.toLocaleString('pt-BR',{maximumFractionDigits:2});
const concepts={faturamento:'Faturamento bruto é a soma das corridas finalizadas antes dos custos. Não é lucro.',lucro:'Resultado operacional desconta combustível consumido e despesas operacionais. Sem cobertura suficiente, não há lucro integral calculável.',caixa:'Caixa operacional é faturamento menos abastecimentos pagos e despesas operacionais. Combustível pago não é necessariamente combustível consumido.',hora:'Faturamento por hora em corrida não inclui toda a jornada online e não é lucro por hora.',km:'Faturamento por km não é lucro por km. Deslocamentos fora dos registros podem aumentar seus custos.',cancelamento:'Cancelar uma corrida aceita é diferente de recusar uma oferta.',espera:'Intervalos entre corridas podem incluir pausas. Sem medir a jornada online, não sabemos quanto tempo você aguardou ofertas.'};
function intent(q){
 const t=normalize(q);
 if(/^(?:o que (?:e|significa)|qual (?:e )?a diferenca|me explica o que|como (?:e|se) calcula)\b/.test(t)){
 const concept=/lucro|resultado operacional/.test(t)?'lucro':/saldo|caixa/.test(t)?'caixa':/por hora/.test(t)?'hora':/por km/.test(t)?'km':/cancel|recus/.test(t)?'cancelamento':/espera|ocioso/.test(t)?'espera':/faturamento|ganho bruto|receita bruta/.test(t)?'faturamento':null;if(concept)return {kind:'concept',concept};}
 if(/compensa|vale a pena|boa oferta|aceitar|quanto sobra/.test(t)&&/corrid|oferta|viagem/.test(t)){
 const v=[...t.matchAll(/r\$\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*reais\b/g)],k=[...t.matchAll(/(\d+(?:[.,]\d+)?)\s*km\b/g)],m=[...t.matchAll(/(\d+(?:[.,]\d+)?)\s*(?:minutos|min)\b/g)],n=x=>Number(x.replace(',','.'));
 if(v.length===1&&k.length===1&&m.length===1){const gross=n(v[0][1]||v[0][2]),km=n(k[0][1]),minutes=n(m[0][1]);if(gross>=0&&gross<=100000&&km>0&&km<=3000&&minutes>0&&minutes<=2880)return {kind:'offer',gross,km,minutes};}
 if(v.length||k.length||m.length||/essa|esta|atual/.test(t))return {kind:'clarify'};
 }
 if(/hoje.*ontem|ontem.*hoje/.test(t)&&/compar|melhor|pior|ganh|fatur|diferenc|mais|menos|rendeu|produtiv/.test(t))return {kind:'compare'};
 if(/meta|objetivo/.test(t)&&/ritmo|ating|alcanc|bater|quanto por dia|quanto preciso|chegar|dias falt/.test(t))return {kind:'goal'};
 if(/uber.*99|99.*uber|qual (?:app|plataforma)/.test(t)&&/compensa|vale a pena|melhor|rentavel|estrateg|prioriz/.test(t))return {kind:'platform'};
 if(/jornada|tempo online|tempo logado|horas online|quanto tempo trabalhei/.test(t))return {kind:'shift'};
 if(/(?:por que|porque|motivo|razao).*(?:ganh|fatur|pouco|lucro|saldo|rod|rend)|diagnostico|analise de desempenho|como estou indo|como foi meu dia|o que devo melhorar|o que posso melhorar|estou indo bem|meu desempenho/.test(t))return {kind:'diagnose'};
 return null;
}
const rows=s=>s.records.filter(r=>r.situacao==='finished'&&!r.simulated);
const totals=a=>({count:a.length,gross:round(a.reduce((n,r)=>n+r.valor,0)),km:round(a.reduce((n,r)=>n+r.km,0)),minutes:a.reduce((n,r)=>n+r.duracao/60,0)});
const excluded=s=>s.simulated?' '+s.simulated+' registro(s) simulados excluídos.':'';
async function resolve(q,previous,{readData,core,now=new Date()}){
 const a=intent(q);if(!a)return null;
 const result=text=>({text,source:'Aura · análise local',context:previous});
 if(a.kind==='concept')return result(concepts[a.concept]);
 if(a.kind==='clarify')return result('Informe valor total, distância total (embarque + trajeto) e tempo total em minutos. Exemplo: R$ 30, 12 km e 25 min.');
 const b=await readData(),rate=b.rates||{},raw=b.finance,t=normalize(q),period=/\bontem\b/.test(t)?'ontem':/\bsemana\b/.test(t)?'semana':/\bmes\b/.test(t)?'mes':/\bhoje\b/.test(t)?'hoje':previous?.period||'hoje',snap=p=>core.snapshot(raw,rate,p,now);
 if(a.kind==='offer'){
 if(![rate.fuel,rate.reserve,rate.fixed].every(x=>Number.isFinite(x)&&x>=0))return result('Confira combustível, reserva e fixos nos parâmetros.');
 const f=round(a.km*rate.fuel),r=round(a.km*rate.reserve),c=round(a.minutes/60*rate.fixed),margin=round(a.gross-f-r-c);
 return result('Margem estimada: '+money(margin)+' ('+money(margin*60/a.minutes)+'/h em corrida). Combustível '+money(f)+', reserva '+money(r)+', fixos '+money(c)+'. '+(margin<=0?'A margem não é positiva. Reveja a oferta.':'A margem é positiva. Avalie retorno sem passageiro, espera e sua meta.')+' Não garante lucro.');
 }
 if(a.kind==='goal'){
 const month=snap('mes'),m=totals(rows(month)),g=Number(raw.goals.revenue);
 if(!Number.isFinite(g)||g<=0)return result('Defina uma meta mensal de faturamento no Finance.');
 const days=new Date(now.getFullYear(),now.getMonth()+1,0).getDate()-now.getDate()+1,remaining=Math.max(0,round(g-m.gross));
 return result('Meta mensal '+money(g)+'. Faturamento real '+money(m.gross)+'. Falta '+money(remaining)+'.'+excluded(month)+' Restam '+days+' dias corridos incluindo hoje; média necessária '+money(remaining/days)+' por dia. Ajuste aos dias em que pretende trabalhar. Não é previsão.');
 }
 if(a.kind==='compare'){
 const cut=[now.getHours(),now.getMinutes(),now.getSeconds()].map(x=>String(x).padStart(2,'0')).join(':'),up=p=>{const s=snap(p);return totals(rows(s).filter(r=>r.fim&&r.fim.slice(0,10)===s.to&&r.fim.slice(11)<=cut))},x=up('hoje'),y=up('ontem');
 if(!x.count||!y.count)return result('Ainda não há corridas reais finalizadas nos dois dias até '+cut.slice(0,5)+' para uma comparação justa.');
 return result('Até '+cut.slice(0,5)+', hoje '+money(x.gross)+' em '+x.count+' corridas reais; ontem '+money(y.gross)+' em '+y.count+'. Diferença '+money(round(x.gross-y.gross))+'. Hoje '+fmt(x.km)+' km / '+fmt(x.minutes)+' min; ontem '+fmt(y.km)+' km / '+fmt(y.minutes)+' min. Não mede toda a jornada online.');
 }
 const s=snap(period),rr=rows(s),r=totals(rr),absent='Não há corridas reais finalizadas suficientes nesse período para avaliar seu desempenho.'+excluded(s);
 if(a.kind==='shift')return result((r.count?'Tempo em corridas reais: '+fmt(r.minutes)+' min.'+excluded(s):absent)+' Não há medição da jornada online ou pausas.');
 if(a.kind==='platform'){
 const u=totals(rr.filter(x=>x.plataforma==='Uber')),n=totals(rr.filter(x=>x.plataforma==='99'));
 if(u.count<3||n.count<3||!u.minutes||!n.minutes)return result('Amostra insuficiente: Uber '+u.count+'; 99 '+n.count+' corridas reais. São necessárias ao menos 3 em cada com duração registrada.'+excluded(s));
 const uh=u.gross*60/u.minutes,nh=n.gross*60/n.minutes;
 return result('Faturamento por hora em corrida: Uber '+money(uh)+'; 99 '+money(nh)+'. '+(uh===nh?'Empate.':(uh>nh?'Uber':'99')+' apresentou maior valor na amostra.')+' Não mede espera, lucro ou demanda futura.'+excluded(s));
 }
 if(!r.count)return result(absent+' Registre trabalho real antes de alterar a estratégia.');
 const advice=[];if(s.canceled>=10||s.cancelRate!=null&&s.cancelRate>10)advice.push('Revise '+s.canceled+' cancelamentos; confirme embarque e destino antes de aceitar.');
 if(s.gap!=null&&s.gap>8)advice.push('Intervalo médio '+fmt(s.gap)+' min. Se estiver online esperando ofertas, avalie a região quando estacionado.');
 if(r.km>0&&Number.isFinite(rate.fuel))advice.push('Combustível estimado '+money(r.km*rate.fuel)+'. Faturamento após apenas esse custo '+money(r.gross-r.km*rate.fuel)+'. Não é lucro.');
 if(!advice.length)advice.push('Registre custos e intervalos da jornada para identificar gargalos.');
 return result(r.count+' corridas reais, '+money(r.gross)+', '+fmt(r.km)+' km, '+fmt(r.minutes)+' min.'+excluded(s)+'\n'+advice.join('\n')+'\nNão há dados para atribuir causa exata ou prever demanda.');
}
return {resolve,intent};
})();
if(typeof module!=='undefined')module.exports=AuraAdvisor;