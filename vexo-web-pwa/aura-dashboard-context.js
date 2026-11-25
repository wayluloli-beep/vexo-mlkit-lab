/* Contexto agregado, somente leitura. Nenhuma chave ou registro individual sai por este módulo. */
const AuraDashboardContext=(()=>{
'use strict';
const norm=q=>String(q||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const finite=n=>typeof n==='number'&&Number.isFinite(n)?n:null;
const round=n=>finite(n)===null?null:Math.round((n+Number.EPSILON)*100)/100;
const periodFor=q=>/\bontem\b/.test(norm(q))?'ontem':/\b(?:semana|7 dias)\b/.test(norm(q))?'semana':/\b(?:mes|mensal)\b/.test(norm(q))?'mes':'hoje';
const isStrategy=q=>/plano de acao|estrategia|o que (?:devo|posso) fazer|como (?:melhorar|aumentar|bater|atingir|alcancar)|como estou indo|diagnostico|analise de desempenho|o que (?:devo|posso) melhorar/.test(norm(q));
function project(bundle,core,{period='hoje',now=new Date()}={}){
 if(!bundle?.finance||typeof core?.snapshot!=='function'||!['hoje','ontem','semana','mes'].includes(period))throw Error('Contexto indisponivel');
 const raw=bundle.finance;
 if(!['rides','fills','expenses'].every(k=>Array.isArray(raw[k]))||!raw.goals)throw Error('Dados invalidos');
 const isSim=id=>typeof id==='string'&&id.startsWith('MOB-');
 const clean={...raw,rides:raw.rides.filter(r=>!isSim(r[0])),expenses:raw.expenses.filter(r=>!isSim(r[6]))};
 const all=core.snapshot(raw,bundle.rates,period,now);
 const s=core.snapshot(clean,bundle.rates,period,now);
 const month=period==='mes'?s:core.snapshot(clean,bundle.rates,'mes',now);
 const goal=finite(raw.goals.revenue),goalSet=goal!==null&&goal>0?goal:null;
 const p={schema:'vexo-dashboard-v1',periodo:period,de:s.from,ate:s.to,escopo:'corridas_reais_identificadas_e_custos_registrados',simulacoes_excluidas:finite(all.simulated),
 drive:{corridas_finalizadas:finite(s.count),faturamento_bruto_brl:round(s.gross),km_corridas:round(s.km),tempo_corridas_min:finite(s.seconds)===null?null:round(s.seconds/60),tempo_online_min:null,cancelamentos:finite(s.canceled),intervalo_medio_entre_corridas_min:round(s.gap),amostras_intervalo:finite(s.gapSamples),faturamento_por_hora_em_corrida_brl:round(s.grossHour),faturamento_por_km_brl:round(s.grossKm)},
 fuel:{consumo_km_l:round(s.consumption),custo_combustivel_km_brl:round(s.fuelKm),base_consumo:s.cycles>0?'ciclos_completos':'parametro_configurado',ciclos_completos:finite(s.cycles),abastecimentos:finite(s.fillCount),litros_abastecidos:round(s.liters),abastecido_brl:round(s.paidFuel),preco_medio_litro_brl:round(s.avgPrice)},
 finance:{caixa_operacional_brl:round(s.cash),caixa_apos_pessoais_brl:round(s.afterPersonal),resultado_operacional_brl:round(s.result),despesas_operacionais_brl:round(s.opCost),despesas_pessoais_brl:round(s.personalCost),corridas_com_cobertura_combustivel:finite(s.coverage),ciclos_inconsistentes:finite(s.invalid),meta_mensal_brl:round(goalSet),faturamento_mes_brl:round(month.gross),falta_meta_mensal_brl:goalSet!==null&&finite(month.gross)!==null?round(Math.max(0,goalSet-month.gross)):null,meta_diaria_brl:null}};
 if(JSON.stringify(p).length>6000)throw Error('Contexto muito longo');
 return p;
}
async function advise(question,{readData,core,transport,now=new Date(),signal}={}){
 if(typeof transport!=='function'||typeof readData!=='function'||!isStrategy(question))return null;
 const q=String(question).trim().slice(0,600),context=project(await readData(),core,{period:periodFor(q),now});
 const answer=await transport({question:q,context},{signal});
 if(typeof answer?.answer!=='string'||!answer.answer.trim()||answer.answer.length>12000)throw Error('Resposta indisponivel');
 return {text:answer.answer.trim(),source:'Aura · Dify + dados agregados',kind:'advice',intent:'ADVICE'};
}

// Only whole, explicit, single-metric questions. No guessing and no financial updates.
function localWire(question,core,now=new Date()){
 const q=norm(question).replace(/[?.!]+$/,'').trim();
 const suffix='(?:hoje|ontem|(?:nesta|nessa|esta|essa|na) semana|(?:neste|nesse|este|esse|no) mes|nos ultimos 7 dias)';
 const patterns=[
 ['FINANCE','GROSS_REVENUE','(?:quanto (?:eu )?(?:ganhei|faturei)|qual (?:foi )?meu faturamento) '+suffix],
 ['FINANCE','NET_PROFIT','(?:qual (?:foi )?(?:o )?meu lucro|quanto (?:eu )?lucrei) '+suffix],
 ['RIDES','RIDE_COUNT','(?:quantas corridas (?:eu )?(?:fiz|finalizei)|quantas corridas) '+suffix],
 ['FUEL','FUEL_SPENT','(?:quanto (?:eu )?gastei (?:com|de|em) combustivel|quanto paguei (?:de|em) combustivel) '+suffix],
 ['FUEL','FUEL_EFFICIENCY_KM_L','(?:qual (?:e )?(?:o )?meu consumo|quantos km por litro(?: meu carro faz)?)'],
 ['GOALS','GOAL_STATUS','(?:qual (?:e )?(?:a )?minha meta mensal|quanto falta para minha meta mensal)']
 ];
 const match=patterns.find(x=>new RegExp('^'+x[2]+'
})();
if(typeof module!=='undefined')module.exports=AuraDashboardContext;
).test(q));
 if(!match||typeof core?.range!=='function')return null;
 const [domain,metric]=match;
 const p=['FUEL_EFFICIENCY_KM_L','GOAL_STATUS'].includes(metric)?'hoje':periodFor(q);
 const [start_date,end_date]=core.range(p,now);
 return {intent:'QUERY_DATA',data_queries:[{domain,metric,start_date,end_date,query_platform:'ALL'}]};
}
return {project,advise,isStrategy,periodFor,localWire};
})();
if(typeof module!=='undefined')module.exports=AuraDashboardContext;
