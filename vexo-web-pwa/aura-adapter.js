/* Candidate adapter: approved v5 wire contract -> typed read-only engine. */
const AuraAdapter=(()=>{
'use strict';
const fail=m=>{throw Error(m)},obj=x=>x!==null&&typeof x==='object'&&!Array.isArray(x),keys=(x,ks)=>{if(!obj(x)||Object.keys(x).length!==ks.length||!ks.every(k=>Object.prototype.hasOwnProperty.call(x,k)))fail('invalid_keys');},one=(v,vs)=>{if(!vs.includes(v))fail('invalid_enum');return v},day=x=>{if(typeof x!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(x)||!Number.isFinite(Date.parse(x+'T00:00:00Z'))||new Date(x+'T00:00:00Z').toISOString().slice(0,10)!==x)fail('invalid_date');return x;};
const fields=['fare_brl','distance_km','duration_min'],domains={GROSS_REVENUE:'FINANCE',NET_PROFIT:'FINANCE',EXPENSES:'FINANCE',FUEL_SPENT:'FUEL',FUEL_EFFICIENCY_KM_L:'FUEL',RIDE_COUNT:'RIDES',AVG_PER_KM:'RIDES',AVG_PER_HOUR:'RIDES',GOAL_STATUS:'GOALS'};
const metrics={GROSS_REVENUE:'ganhos',NET_PROFIT:'lucro',EXPENSES:'despesas',FUEL_EFFICIENCY_KM_L:'consumo_kml',RIDE_COUNT:'corridas',AVG_PER_KM:'ganho_km',AVG_PER_HOUR:'ganho_hora',GOAL_STATUS:'meta'};
const money=x=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(x),fmt=x=>x.split('-').reverse().join('/');
const empty=()=>({active_ride_simulation:null,last_query_context:null});
function validate(p){
 if(!obj(p))fail('invalid_envelope');
 const variant={SIMULATE_RIDE:['intent','ride_simulation'],QUERY_DATA:['intent','data_queries'],CONCEPTUAL_EXPLANATION:['intent','conceptual_topic'],CLARIFY:['intent','clarification_reason'],OUT_OF_SCOPE:['intent']}[p.intent];if(!Array.isArray(variant))fail('invalid_intent');keys(p,variant);
 if(p.intent==='SIMULATE_RIDE'){const a=p.ride_simulation;keys(a,[...fields,'ride_platform']);one(a.ride_platform,['UBER','99','UNKNOWN']);for(const k of fields){const n=a[k];if(n!==null&&(typeof n!=='number'||!Number.isFinite(n)||n<(k==='fare_brl'?0:.01)||n>(k==='fare_brl'?100000:k==='distance_km'?3000:2880)))fail('invalid_number');}}
 if(p.intent==='QUERY_DATA'){if(!Array.isArray(p.data_queries)||!p.data_queries.length||p.data_queries.length>4)fail('invalid_queries');for(const q of p.data_queries){keys(q,['domain','metric','start_date','end_date','query_platform']);if(!Object.prototype.hasOwnProperty.call(domains,q.metric)||domains[q.metric]!==q.domain)fail('invalid_domain_metric');if(day(q.start_date)>day(q.end_date))fail('invalid_range');one(q.query_platform,['ALL','UBER','99']);}}
 if(p.intent==='CLARIFY')one(p.clarification_reason,['AMBIGUOUS_UNIT','MISSING_CONTEXT']);
 if(p.intent==='CONCEPTUAL_EXPLANATION'&&(typeof p.conceptual_topic!=='string'||!p.conceptual_topic.trim()||p.conceptual_topic.length>120))fail('invalid_concept');
 return p;
}
function restore(s){try{
 let n=empty();keys(s,['active_ride_simulation','last_query_context']);
 if(s.active_ride_simulation){const {platform,...r}=s.active_ride_simulation;const p=validate({intent:'SIMULATE_RIDE',ride_simulation:{...r,ride_platform:platform}});if(fields.some(k=>p.ride_simulation[k]===null))fail('partial');n=commit(n,p);}
 if(s.last_query_context){const p=validate({intent:'QUERY_DATA',data_queries:s.last_query_context.queries.map(({platform_filter,...q})=>({...q,query_platform:platform_filter}))});n=commit(n,p);}
 return n;
 }catch{return empty();}}
function commit(state,p){
 if(p.intent==='SIMULATE_RIDE'){const {ride_platform,...r}=p.ride_simulation;return {...state,active_ride_simulation:{...r,platform:ride_platform}};}
 if(p.intent==='QUERY_DATA'){const queries=p.data_queries.map(({query_platform,...q})=>({...q,platform_filter:query_platform}));return {...state,last_query_context:{queries}};}
 return state;
}
function plan(p){
 if(p.intent==='SIMULATE_RIDE'){const r=p.ride_simulation;return [{tool:'offer',args:{gross:r.fare_brl,km:r.distance_km,minutes:r.duration_min}}];}
 const steps=[],fuel=p.data_queries.filter(q=>q.metric==='FUEL_SPENT'&&q.query_platform==='ALL');
 if(fuel.length)steps.push({tool:'fuel_spent',args:{platform:'all',ranges:fuel.map(q=>({from:q.start_date,to:q.end_date}))}});
 for(const q of p.data_queries){if(q.metric==='FUEL_SPENT'){if(q.query_platform!=='ALL')return null;continue;}
 steps.push({tool:'metric',args:{period:{from:q.start_date,to:q.end_date},platform:q.query_platform==='ALL'?'all':q.query_platform==='UBER'?'Uber':'99',metric:metrics[q.metric]}});}
 return steps;
}
async function execute(wire,state,{engine,core,readData,now=new Date()}){
 const p=validate(wire),unchanged=(text,kind='clarify')=>({text,kind,context:state,intent:p.intent,source:'Aura · consulta segura'});
 if(p.intent==='OUT_OF_SCOPE')return unchanged('Essa ação ou consulta não está disponível neste motor de teste. Nenhum dado foi alterado.','unsupported');
 if(p.intent==='CLARIFY')return unchanged(p.clarification_reason==='AMBIGUOUS_UNIT'?'Qual é a unidade: reais, quilômetros ou minutos?':'Pode completar a pergunta?');
 if(p.intent==='CONCEPTUAL_EXPLANATION'){const topics={diferenca_faturamento_lucro:'Faturamento é o valor bruto recebido. Resultado operacional desconta o combustível consumido e despesas operacionais registradas. Caixa é diferente de lucro.',calculo_lucro_liquido:'O VEXO calcula o resultado operacional usando faturamento, combustível consumido e despesas operacionais registradas. Sem cobertura suficiente de combustível, não informa lucro integral.'};return unchanged(Object.prototype.hasOwnProperty.call(topics,p.conceptual_topic)?topics[p.conceptual_topic]:'Qual conceito financeiro você quer entender?', 'concept');}
 if(p.intent==='SIMULATE_RIDE'){const missing=fields.filter(k=>p.ride_simulation[k]===null);if(missing.length)return unchanged('Qual '+missing.map(k=>({fare_brl:'o valor em reais',distance_km:'a distância total em km',duration_min:'o tempo total em minutos'}[k])).join(' e ')+'?');}
 const steps=plan(p);if(!steps)return unchanged('Não existe rateio confiável de combustível por plataforma.','unavailable');
 const {results}=await engine.run({mode:'new',plan:{version:1,steps}},null,{core,readData,now});
 if(results.some(r=>r.kind==='unavailable'))return unchanged(results.map(r=>r.reason||r.text||'Consulta indisponível.').join('\n'),'unavailable');
 const text=results.map(r=>{
 if(r.kind==='offer')return 'Simulação: '+money(r.inputs.gross)+' · '+r.inputs.km+' km · '+r.inputs.minutes+' min.\nMargem estimada: '+money(r.margin)+'. Combustível: '+money(r.fuel)+', reserva: '+money(r.reserve)+', fixo: '+money(r.fixed)+'. Estimativa, não lucro realizado.';
 if(r.kind==='fuel_spent')return 'Combustível pago: '+money(r.value)+' em '+r.count+' abastecimento(s). Períodos: '+r.evidence.ranges.map(q=>fmt(q.from)+(q.to===q.from?'':' a '+fmt(q.to))).join('; ')+'. Não é necessariamente combustível consumido.';
 if(r.kind==='metric')return fmt(r.period.from)+(r.period.to===r.period.from?'':' a '+fmt(r.period.to))+': '+r.text;
 return '';
 }).filter(Boolean).join('\n\n');
 if(!text)fail('empty_result');return {text,kind:'success',context:commit(state,p),intent:p.intent,source:'Gemini · cálculo local VEXO'};
}

const normal=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
function pendingFor(question,wire,state){
 if(wire?.intent!=='CLARIFY'||wire.clarification_reason!=='AMBIGUOUS_UNIT'||!state?.active_ride_simulation)return null;
 const m=normal(question).match(/^(?:e\s+)?(?:se\s+(?:fosse|forem)\s+|por\s+|(?:fosse|forem)\s+)?(\d{1,6}(?:[,.]\d{1,2})?)\s*[?!]*$/);
 if(!m)return null;const value=Number(m[1].replace(',','.'));if(!Number.isFinite(value)||value<0||value>100000)return null;
 return {type:'AMBIGUOUS_UNIT',candidate_value:value,target_intent:'SIMULATE_RIDE',expires_after_turns:1};
}
function unitField(question){
 const u=normal(question).replace(/[.!?;,:]+$/g,'').trim().replace(/^a unidade (?:e|eh)\s+/,'').replace(/^(?:(?:em|de|no|na|o|a|os|as)\s+)+/,'').trim();
 if(['r$','real','reais'].includes(u))return 'fare_brl';
 if(['km','quilometro','quilometros','kilometro','kilometros'].includes(u))return 'distance_km';
 if(['min','minuto','minutos'].includes(u))return 'duration_min';return null;
}
function resolvePending(question,pending,state){
 if(!pending||pending.type!=='AMBIGUOUS_UNIT'||pending.target_intent!=='SIMULATE_RIDE'||pending.expires_after_turns!==1||!state?.active_ride_simulation)return null;
 const field=unitField(question);if(!field)return null;
 const {platform,...r}=state.active_ride_simulation;
 try{return {wire:validate({intent:'SIMULATE_RIDE',ride_simulation:{...r,[field]:pending.candidate_value,ride_platform:platform}})}}catch{return {error:'O valor não é válido para essa unidade. Informe o valor e a unidade novamente.'};}
}

function localGuard(question,state){
 const u=unitField(question);
 if(u){const names={fare_brl:'reais',distance_km:'quilômetros',duration_min:'minutos'};return {kind:'unit_without_pending',text:'Qual valor você quer aplicar em '+names[u]+'? Informe o valor junto com a unidade.'};}
 if(!state?.active_ride_simulation)return null;
 // Whole-utterance whitelist, not a general parser. Bare platform 99 is deliberately excluded.
 const m=normal(question).match(/^(?:e(?:\s+por|\s+se(?:\s+(?:for|forem|fosse|fossem))?)?|por|para|pra|com|em)\s+(\d{1,6}(?:[,.]\d{1,2})?)\s*[?!.]*$/);
 if(!m||m[1]==='99')return null;
 const value=Number(m[1].replace(',','.'));if(!Number.isFinite(value)||value<0||value>100000)return null;
 return {kind:'ambiguous',text:'Qual é a unidade: reais, quilômetros ou minutos?',pending:{type:'AMBIGUOUS_UNIT',candidate_value:value,target_intent:'SIMULATE_RIDE',expires_after_turns:1}};
}
return {validate,execute,empty,restore,pendingFor,resolvePending,localGuard};
})();
if(typeof module!=='undefined')module.exports=AuraAdapter;