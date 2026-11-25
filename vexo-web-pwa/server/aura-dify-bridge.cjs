/* Server only. Mount behind existing authenticated VEXO session and an atomic quota store. */
'use strict';
const groups={
 drive:'corridas_finalizadas faturamento_bruto_brl km_corridas tempo_corridas_min tempo_online_min cancelamentos intervalo_medio_entre_corridas_min amostras_intervalo faturamento_por_hora_em_corrida_brl faturamento_por_km_brl'.split(' '),
 fuel:'consumo_km_l custo_combustivel_km_brl base_consumo ciclos_completos abastecimentos litros_abastecidos abastecido_brl preco_medio_litro_brl'.split(' '),
 finance:'caixa_operacional_brl caixa_apos_pessoais_brl resultado_operacional_brl despesas_operacionais_brl despesas_pessoais_brl corridas_com_cobertura_combustivel ciclos_inconsistentes meta_mensal_brl faturamento_mes_brl falta_meta_mensal_brl meta_diaria_brl'.split(' ')
};
const exact=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===k.length&&k.every(x=>Object.prototype.hasOwnProperty.call(v,x));
const date=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s+'T00:00:00Z'))&&new Date(s+'T00:00:00Z').toISOString().slice(0,10)===s;
const num=v=>v===null||(typeof v==='number'&&Number.isFinite(v)&&Math.abs(v)<=1e12);
function valid(c){
 if(!exact(c,['schema','periodo','de','ate','escopo','simulacoes_excluidas',...Object.keys(groups)])||c.schema!=='vexo-dashboard-v1'||!['hoje','ontem','semana','mes'].includes(c.periodo)||!date(c.de)||!date(c.ate)||c.de>c.ate||c.escopo!=='corridas_reais_identificadas_e_custos_registrados'||!num(c.simulacoes_excluidas))return false;
 return Object.entries(groups).every(([g,ks])=>exact(c[g],ks)&&ks.every(k=>k==='base_consumo'?['ciclos_completos','parametro_configurado'].includes(c[g][k]):num(c[g][k])));
}
function createHandler({apiKey,authorize,reserve,fetchImpl=globalThis.fetch,timeoutMs=25000}={}){
 if(typeof apiKey!=='string'||!apiKey.trim()||typeof authorize!=='function'||typeof reserve!=='function'||typeof fetchImpl!=='function')throw Error('Configuracao segura obrigatoria');
 const error=(status,code)=>({status,body:{error:code}});
 return async function(request){
  // authorize must derive an opaque stable user id from a verified session, never from request body.
  let session;try{session=await authorize(request);}catch{return error(401,'unauthorized');}
  if(typeof session?.userId!=='string'||!/^[-a-zA-Z0-9_]{16,128}$/.test(session.userId))return error(401,'unauthorized');
  const b=request.body;
  if(!exact(b,['question','context'])||typeof b.question!=='string'||!b.question.trim()||b.question.length>600||!valid(b.context))return error(400,'invalid_context');
  const snapshot=JSON.stringify(b.context);if(snapshot.length>6000)return error(400,'invalid_context');
  // Atomic shared quota reservation: two model calls per current Dify workflow.
  try{if(await reserve(session.userId,2)!==true)return error(429,'quota_reached');}catch{return error(503,'quota_unavailable');}
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
   const response=await fetchImpl('https://api.dify.ai/v1/chat-messages',{method:'POST',headers:{Authorization:'Bearer '+apiKey,'Content-Type':'application/json'},body:JSON.stringify({inputs:{vexo_context:snapshot},query:b.question.trim(),response_mode:'blocking',user:session.userId,auto_generate_name:false}),signal:controller.signal});
   if(!response.ok)return error(response.status===429?429:502,'aura_unavailable');
   const data=await response.json();if(typeof data?.answer!=='string'||!data.answer.trim()||data.answer.length>12000)return error(502,'invalid_answer');
   // No conversation_id reuse: fresh dashboard context each request, until freshness is validated.
   return {status:200,body:{answer:data.answer.trim()}};
  }catch{return error(controller.signal.aborted?504:502,'aura_unavailable');}finally{clearTimeout(timer);}
 };
}
module.exports={createHandler,valid};
