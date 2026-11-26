/* Aura LFX: aggregated read-only context, explicit one-time authorization, no embedded keys. */
(()=>{'use strict';
const endpoint='https://vexo-aura-lfx-probe.onrender.com/chat',accessKey='vexo-aura-lfx-access-v1',sessionKey='vexo-aura-lfx-session-v1';
let access='',session='',lastPeriod='hoje';
try{access=sessionStorage.getItem(accessKey)||'';session=sessionStorage.getItem(sessionKey)||'';}catch{}
const $=id=>document.getElementById(id);
let verified=false,expanded=false;
function paint(message=''){
 const toggle=$('connection-toggle'),fields=$('connection-fields'),detail=$('connection-detail'),feedback=$('connection-feedback');
 if(!toggle||!fields)return;
 toggle.textContent=access?'Desconectar':expanded?'Fechar':'Conectar';
 toggle.setAttribute('aria-expanded',String(!access&&expanded));
 fields.hidden=Boolean(access)||!expanded;
 detail.textContent=verified?'Conectada · Gemini + motor':access?'Código configurado · teste enviando uma mensagem':'Modo local · conecte uma vez nesta sessão';
 feedback.textContent=message;
}
function openFields(message=''){
 expanded=true;paint(message);$('connection-code')?.focus();
}
function authorize(){
 if(access)return true;
 openFields('Informe o código de acesso para usar a conversa online. Consultas locais continuam disponíveis.');
 return false;
}
function disconnect(){
 access='';session='';lastPeriod='hoje';verified=false;expanded=false;
 try{sessionStorage.removeItem(accessKey);sessionStorage.removeItem(sessionKey);}catch{}
 paint('Aura online desconectada. Seus registros permanecem no aparelho.');
}
async function activate(){
 const input=$('connection-code'),token=String(input?.value||'').trim(),button=$('connection-save');
 if(token.length<24){openFields('Código incompleto. Confira e tente novamente.');return;}
 button.disabled=true;paint('Verificando código com o servidor…');
 try{
  const resp=await fetch(endpoint.replace(/\/chat$/,'/auth/check'),{method:'POST',headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(25000)});
  if(resp.status===401){openFields('Código inválido. Cole novamente o código correto.');return;}
  if(!resp.ok)throw Error('unavailable');
  const result=await resp.json();if(result.authenticated!==true)throw Error('unavailable');
  access=token;session='';verified=true;expanded=false;
  try{sessionStorage.setItem(accessKey,access);sessionStorage.removeItem(sessionKey);}catch{}
  input.value='';paint(result.ready?'Conexão verificada.':'Conexão verificada; servidor inicializando.');$('question')?.focus();
 }catch{openFields('Não consegui verificar o acesso. Tente novamente.');}
 finally{button.disabled=false;}
}
$('connection-toggle')?.addEventListener('click',()=>{
 if(access){disconnect();return;}
 if(expanded){expanded=false;paint();return;}
 openFields('Somente indicadores agregados serão enviados à Aura. Nenhuma corrida ou despesa será alterada.');
});
$('connection-save')?.addEventListener('click',activate);
$('connection-code')?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();activate();}});
paint();
function periodFor(question){const q=String(question).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();if(/\b(hoje|agora)\b/.test(q))return lastPeriod='hoje';if(/\b(ontem|semana|7 dias|mes|mensal)\b/.test(q))return lastPeriod=AuraDashboardContext.periodFor(q);return lastPeriod;}
async function request(question,{readData,core,history=[],signal}={}){
 if(!authorize())return null;
 const context=AuraDashboardContext.project(await readData(),core,{period:periodFor(question)});
 const turns=history.slice(-9,-1).filter(x=>['user','aura'].includes(x.role)&&typeof x.text==='string').map(x=>({role:x.role==='aura'?'model':'user',text:x.text.slice(0,800)}));
 const ctrl=new AbortController(),abort=()=>ctrl.abort(),timeout=setTimeout(abort,40000);
 if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
 try{
  const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+access},body:JSON.stringify({question,context,session,history:turns}),signal:ctrl.signal});
  if(response.status===401){disconnect();openFields('Código inválido. Confira o código e tente novamente.');throw Error('Acesso da Aura inválido.');}
  if(!response.ok){paint('Serviço temporariamente indisponível. Seu acesso e contexto foram preservados.');throw Error('Aura online indisponível ('+response.status+').');}
  const d=await response.json();
  if(typeof d.answer!=='string'||!d.answer.trim()||d.answer.length>12000||typeof d.session!=='string')throw Error('Resposta inválida.');
  session=d.session;verified=true;paint();try{sessionStorage.setItem(sessionKey,session);}catch{}
  return {text:d.answer.trim(),source:d.source==='motor'?'Motor VEXO · dados atualizados':d.source==='motor+gemini'?'Aura · motor VEXO + Gemini':'Aura · Gemini + indicadores atualizados',kind:'advice',intent:'AURA_LFX'};
 }finally{clearTimeout(timeout);signal?.removeEventListener('abort',abort);}
}
window.VexoAuraLfx={request,disconnect,connected:()=>Boolean(access)};
})();