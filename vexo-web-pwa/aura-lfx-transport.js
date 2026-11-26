/* Aura LFX: aggregated read-only context, explicit one-time authorization, no embedded keys. */
(()=>{'use strict';
const endpoint='https://vexo-aura-lfx-probe.onrender.com/chat',accessKey='vexo-aura-lfx-access-v1',sessionKey='vexo-aura-lfx-session-v1';
let access='',session='',lastPeriod='hoje';
try{access=sessionStorage.getItem(accessKey)||'';session=sessionStorage.getItem(sessionKey)||'';}catch{}
function authorize(){
 if(access)return true;
 const token=window.prompt('Conectar a Aura online? Somente indicadores agregados de corridas, despesas, combustível e metas serão enviados para análise. Cole seu código de acesso da Aura; nenhuma corrida será alterada.');
 if(typeof token!=='string'||token.trim().length<24)return false;
 access=token.trim();try{sessionStorage.setItem(accessKey,access);}catch{}return true;
}
function disconnect(){access='';session='';lastPeriod='hoje';try{sessionStorage.removeItem(accessKey);sessionStorage.removeItem(sessionKey);}catch{}}
function periodFor(question){const q=String(question).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();if(/\b(hoje|agora)\b/.test(q))return lastPeriod='hoje';if(/\b(ontem|semana|7 dias|mes|mensal)\b/.test(q))return lastPeriod=AuraDashboardContext.periodFor(q);return lastPeriod;}
async function request(question,{readData,core,history=[],signal}={}){
 if(!authorize())return null;
 const context=AuraDashboardContext.project(await readData(),core,{period:periodFor(question)});
 const turns=history.slice(-9,-1).filter(x=>['user','aura'].includes(x.role)&&typeof x.text==='string').map(x=>({role:x.role==='aura'?'model':'user',text:x.text.slice(0,800)}));
 const ctrl=new AbortController(),abort=()=>ctrl.abort(),timeout=setTimeout(abort,40000);
 if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
 try{
  const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+access},body:JSON.stringify({question,context,session,history:turns}),signal:ctrl.signal});
  if(response.status===401){disconnect();throw Error('Acesso da Aura inválido.');}
  if(!response.ok)throw Error('Aura online indisponível.');
  const d=await response.json();
  if(typeof d.answer!=='string'||!d.answer.trim()||d.answer.length>12000||typeof d.session!=='string')throw Error('Resposta inválida.');
  session=d.session;try{sessionStorage.setItem(sessionKey,session);}catch{}
  return {text:d.answer.trim(),source:d.source==='motor'?'Motor VEXO · dados atualizados':d.source==='motor+gemini'?'Aura · motor VEXO + Gemini':'Aura · Gemini + indicadores atualizados',kind:'advice',intent:'AURA_LFX'};
 }finally{clearTimeout(timeout);signal?.removeEventListener('abort',abort);}
}
window.VexoAuraLfx={request,disconnect,connected:()=>Boolean(access)};
})();