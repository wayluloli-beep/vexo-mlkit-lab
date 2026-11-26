(()=>{'use strict';
const $=id=>document.getElementById(id),KEY='vexo-aura-chat-v1',PROXY='https://vexo-aura-flash-bridge-xs69.onrender.com/aura/v5',MEMORY='vexo-aura-session-v5',DEBUG='vexo-aura-field-log-v5';
let history=[],previous=AuraAdapter.empty(),busy=false,voice=false,recognizer=null,lastReply='',active=null,epoch=0,listenId=null,logs=[],pending_clarification=null;
try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');if(saved&&Array.isArray(saved.history)){history=saved.history.filter(x=>['user','aura'].includes(x.role)&&typeof x.text==='string').slice(-40);voice=saved.voice===true}}catch{}
try{previous=AuraAdapter.restore(JSON.parse(localStorage.getItem(MEMORY)||'null'));const saved=JSON.parse(localStorage.getItem(DEBUG)||'[]');if(Array.isArray(saved))logs=saved.slice(-100)}catch{}
function persist(){try{localStorage.setItem(KEY,JSON.stringify({history:history.slice(-40),voice}))}catch{setStatus('Armazenamento da conversa indisponível.')}}
function setStatus(x){$('status').textContent=x}
function render(){const node=$('thread');node.replaceChildren();if(!history.length){const m=document.createElement('div');m.className='msg aura';m.textContent='Olá! Sou a Aura, sua copiloto. Posso consultar seus ganhos, custos e desempenho para montar um plano de ação.';node.append(m)}for(const x of history){const m=document.createElement('div');m.className='msg '+x.role;m.textContent=x.text;if(x.source){const s=document.createElement('span');s.className='source';s.textContent=x.source;m.append(s)}node.append(m)}node.scrollTop=node.scrollHeight}
function append(role,text,source){history.push({role,text,source});history=history.slice(-40);persist();render()}
function voiceAvailable(){return Boolean(window.VexoVoice?.speak||window.speechSynthesis&&window.SpeechSynthesisUtterance)}
function stop(){try{if(window.VexoVoice?.stop)window.VexoVoice.stop();else window.speechSynthesis?.cancel()}catch{}$('orb').classList.remove('active')}
function speak(text){if(!voiceAvailable()){setStatus('Voz indisponível neste dispositivo.');return}stop();try{if(window.VexoVoice?.speak){window.VexoVoice.speak(text.slice(0,2500));return}const u=new SpeechSynthesisUtterance(text);u.lang='pt-BR';u.rate=1;u.onstart=()=>$('orb').classList.add('active');u.onend=u.onerror=()=>$('orb').classList.remove('active');window.speechSynthesis.speak(u)}catch{setStatus('Não foi possível reproduzir a voz.')}}
function voiceLabel(){$('voice').setAttribute('aria-pressed',String(voice));$('voice').title=voice?'Desativar voz':'Ativar voz';$('voice').style.color=voice?'#8adce8':'#94a3b8'}
$('voice').onclick=()=>{voice=!voice;voiceLabel();persist();if(voice){if(lastReply)speak(lastReply);else if(!voiceAvailable())setStatus('Voz indisponível neste dispositivo.')}else stop()};
$('orb').onclick=()=>{if(window.speechSynthesis?.speaking){stop();return}if(lastReply)speak(lastReply);else speak('Olá, sou a Aura. Como posso ajudar?')};
function record(text_stt,intent_retornada,latencia_total_ms,status_rede,timing=[]){
 const row={texto_stt:text_stt??null,intent_retornada:intent_retornada??null,latencia_total_ms:Math.max(0,Math.round(latencia_total_ms)),status_rede,request_timing:timing.map(t=>({...t}))};logs.push(row);logs=logs.slice(-100);
 try{localStorage.setItem(DEBUG,JSON.stringify(logs))}catch{}
}
window.vexoAuraDebugLogs=()=>JSON.stringify(logs,null,2);
let hold;
$('status').addEventListener('pointerdown',()=>{hold=setTimeout(()=>{try{if(window.VexoVoice?.copyDebug)window.VexoVoice.copyDebug(window.vexoAuraDebugLogs());else navigator.clipboard?.writeText(window.vexoAuraDebugLogs())}catch{}},900)});
for(const evt of ['pointerup','pointercancel','pointerleave'])$('status').addEventListener(evt,()=>clearTimeout(hold));
function cancel(){epoch++;if(active){active.controller.abort();record(active.stt,active.intent,performance.now()-active.started,'CANCELED',active.timing);active=null;}busy=false;$('send').disabled=false;stop();if(recognizer){try{recognizer.abort()}catch{}recognizer=null;}}
window.vexoAuraSuspend=()=>{cancel();setStatus('Copiloto · pronta');};
window.addEventListener('pagehide',()=>cancel());
function id(){return globalThis.crypto?.randomUUID?.()||('aura-'+Date.now()+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2))}
async function ask(q,stt=false,quick=null){
 q=String(q||'').trim().slice(0,600);if(!q)return;listenId=null;cancel();
 const pending=pending_clarification;pending_clarification=null;
 const token=epoch,controller=new AbortController(),started=performance.now(),requestId=id();const timing=[];active={controller,started,stt:stt?q:null,intent:null,timing};busy=true;$('send').disabled=true;$('question').value='';append('user',q);
 const current=()=>epoch===token&&!controller.signal.aborted;
 let status='OK',intent=null;
 try{
  const readData=()=>Vexo.invoke('auraDados');
  let result;
  const dashboard=await AuraDashTools.handle(q,{readData});
  if(!current())return;
  if(dashboard){lastReply=dashboard.text;append('aura',dashboard.text,dashboard.source);setStatus('Copiloto · pronta');record(stt?q:null,'DASHBOARD_TOOL',performance.now()-started,'LOCAL_QUERY',timing);if(voice||stt)speak(dashboard.text);return;}
  const local=quick?null:AuraAdapter.resolvePending(q,pending,previous);
  const guard=quick||local?null:AuraAdapter.localGuard(q,previous);
  const localQuery=quick||local||guard?null:AuraDashboardContext.localWire(q,AuraCore);
  if(local){status='LOCAL_CLARIFICATION';intent='SIMULATE_RIDE';active.intent=intent;
   result=local.error?{text:local.error,kind:'clarify',context:previous,intent}:await AuraAdapter.execute(local.wire,previous,{engine:AuraQueryEngine,core:AuraCore,readData});
   result={...result,source:'Aura · esclarecimento local'};if(result.kind==='unavailable')status='LOCAL_UNAVAILABLE';
  }else if(guard){status='LOCAL_CLARIFICATION';intent='CLARIFY';active.intent=intent;
   if(current())pending_clarification=guard.pending||null;
   result={text:guard.text,kind:'clarify',context:previous,intent,source:'Aura · esclarecimento local'};
  }else if(localQuery){
   intent='QUERY_DATA';active.intent=intent;status='LOCAL_QUERY';
   result=await AuraAdapter.execute(localQuery,previous,{engine:AuraQueryEngine,core:AuraCore,readData});
   result={...result,source:'Dados locais · sem consumo de API'};
  }else if((!quick||quick==='plano')&&window.VexoAuraLfx){
   intent='AURA_LFX';active.intent=intent;
   try{
    result=await window.VexoAuraLfx.request(q,{readData,core:AuraCore,history,signal:controller.signal});
    if(!result)throw Error('Online not authorized');
    result={...result,context:previous,intent};
   }catch(e){
    if(!current())return;
    status='LFX_LOCAL_FALLBACK';
    if(quick||AuraDashboardContext.isStrategy(q)){
      result=await AuraAdvisor.resolve(q,null,{readData,core:AuraCore})||{text:'Não consegui conectar a Aura online. Consulte seus indicadores locais.',source:'Aura · modo local',kind:'unavailable',context:previous};
    }else{
      result={text:'Não consegui conectar a conversa online. As consultas diretas aos seus indicadores continuam disponíveis.',source:'Aura · modo local',kind:'unavailable',context:previous};
    }
   }
  }else if(quick){const b=await readData(),s=AuraCore.snapshot(b.finance,b.rates,'hoje');result={text:AuraCore.answer(quick,s),source:'Dados locais · atalho',kind:'concept',context:previous,intent:'LOCAL_SHORTCUT'};}
  else{
   const response=await AuraMobileTransport.run((signal,attempt)=>{timing.push({request_id:requestId,attempt,client_send_ms:Date.now(),server_receive_ms:null,gemini_api_ms:null,server_total_ms:null});return fetch(PROXY,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({protocol:5,question:q,context:previous,request_id:requestId,attempt}),signal});},{signal:controller.signal,onAttempt:(attempt,meta)=>{const t=timing.find(x=>x.attempt===attempt);if(t)Object.assign(t,meta);},onSlow:()=>{if(current())setStatus('Calculando…')}});
   if(!current())return;
   status=response.status;
   if(response.kind!=='response'){result={text:response.text,source:'Rede · '+status,kind:'unavailable',context:previous};}
   else{
    if(response.response?.protocol!==5)throw Error('Protocolo incompatível');
    const wire=AuraAdapter.validate(response.response.plan);intent=wire.intent;active.intent=intent;
    result=await AuraAdapter.execute(wire,previous,{engine:AuraQueryEngine,core:AuraCore,readData});
    if(result.kind==='unavailable')status='LOCAL_UNAVAILABLE';
    if(current())pending_clarification=AuraAdapter.pendingFor(q,wire,previous);
   }
  }
  if(!current())return;
  intent=result.intent||intent;
  if(result.kind==='success'){try{localStorage.setItem(MEMORY,JSON.stringify(result.context));previous=result.context;}catch{status='STORAGE_ERROR';}}
  lastReply=result.text;append('aura',result.text,result.source);setStatus('Copiloto · pronta');record(stt?q:null,intent,performance.now()-started,status,timing);if(voice||stt)speak(result.text);
 }catch(e){if(current()){status=intent?'LOCAL_ERROR':'INVALID_PLAN';record(stt?q:null,intent,performance.now()-started,status,timing);lastReply='Não consegui validar a consulta. Pode repetir?';append('aura',lastReply,'Consulta indisponível');setStatus('Copiloto · pronta');if(voice||stt)speak(lastReply);}}
 finally{if(epoch===token){active=null;busy=false;$('send').disabled=false;}}
}
$('form').onsubmit=e=>{e.preventDefault();ask($('question').value)};$('question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask($('question').value)}});
document.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>ask(b.dataset.q,false,b.dataset.q==='Qual meu plano de ação hoje?'?'plano':b.dataset.q==='Qual o custo por km?'?'custo_km':null));
window.vexoAuraRecognized=(text,token)=>{if(!listenId||token!==listenId)return;listenId=null;recognizer=null;if(typeof text==='string'&&text.trim())ask(text,true);else{setStatus('Copiloto · pronta');record(null,null,0,'STT_NO_RESULT');}};
$('mic').onclick=()=>{if(listenId)return;cancel();const token=id();listenId=token;if(window.VexoVoice?.listen){try{window.VexoVoice.listen(token);setStatus('Ouvindo…');return}catch{listenId=null;setStatus('Microfone indisponível.');return}}
 const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R){listenId=null;setStatus('Microfone indisponível nesta WebView. Digite sua pergunta.');return}
 try{recognizer=new R();recognizer.lang='pt-BR';recognizer.interimResults=false;recognizer.onresult=e=>window.vexoAuraRecognized(e.results[0][0].transcript,token);recognizer.onerror=()=>window.vexoAuraRecognized(null,token);recognizer.onend=()=>{if(listenId===token)window.vexoAuraRecognized(null,token);$('orb').classList.remove('active')};$('orb').classList.add('active');recognizer.start();setStatus('Ouvindo…')}catch{window.vexoAuraRecognized(null,token)}
};
voiceLabel();render();lastReply=history.filter(x=>x.role==='aura').at(-1)?.text||'';
})();