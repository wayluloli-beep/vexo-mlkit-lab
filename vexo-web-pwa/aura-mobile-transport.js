// Candidate only. No storage writes, voice calls or changes to the deployed client.
const AuraMobileTransport=(()=>{
const FALLBACK='Rede instável agora, repete pra mim em instantes.';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function boundedAttempt(request,ms){
 const controller=new AbortController();let timer;
 try{return await Promise.race([Promise.resolve().then(()=>request(controller.signal)),new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Object.assign(Error('Tempo limite'),{code:'timeout'}));},ms);})]);}
 finally{clearTimeout(timer);}
}
async function interpret(request,{attempt=boundedAttempt,wait=pause}={}){
 let last='network';
 for(let i=0;i<2;i++){
  try{
   const response=await attempt(async signal=>{
    const r=await request(signal);
    if(!r.ok)throw Object.assign(Error('HTTP '+r.status),{status:r.status});
    return await r.json();
   },2500);
   return {kind:'response',response,attempts:i+1};
  }catch(e){
   last=e.status?'HTTP '+e.status:e.code==='timeout'||e.name==='AbortError'?'timeout':e instanceof TypeError?'network':'invalid_response';
   // Do not immediately retry quota exhaustion or malformed payloads.
   if(i===0&&['HTTP 503','timeout','network'].includes(last)){await wait(500);continue;}
   return {kind:'unavailable',reason:last,attempts:i+1,text:FALLBACK,voice:FALLBACK};
  }
 }
 return {kind:'unavailable',reason:last,attempts:2,text:FALLBACK,voice:FALLBACK};
}
return {interpret,boundedAttempt};
})();
if(typeof module!=='undefined')module.exports=AuraMobileTransport;