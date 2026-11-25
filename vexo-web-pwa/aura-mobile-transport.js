/* Single 5s end-to-end HTTP budget, only retry HTTP 503 if time remains. */
const AuraMobileTransport=(()=>{
const FALLBACK='Rede instável agora, repete pra mim em instantes.';
async function run(request,{signal,onSlow=()=>{},budget=5000}={}){
 const controller=new AbortController(),started=Date.now();let timer,slow,abort,expired=false;
 const outcome=(status,attempts=0)=>({kind:status==='CANCELED'?'canceled':'unavailable',status,attempts,text:FALLBACK});
 const work=async()=>{for(let attempt=0;attempt<2;attempt++){
  if(controller.signal.aborted)return outcome(expired?'TIMEOUT_5S':'CANCELED',attempt);
  try{const r=await request(controller.signal,attempt);if(controller.signal.aborted)return outcome(expired?'TIMEOUT_5S':'CANCELED',attempt+1);
  if(r.status===503&&attempt===0&&budget-(Date.now()-started)>900){await new Promise(resolve=>setTimeout(resolve,500));continue;}
  if(!r.ok)return outcome('HTTP_'+r.status,attempt+1);
  const response=await r.json();return {kind:'response',status:'OK',response,attempts:attempt+1};
  }catch(e){return outcome(controller.signal.aborted?(expired?'TIMEOUT_5S':'CANCELED'):'NETWORK_ERROR',attempt+1);}
 }return outcome('HTTP_503',2);};
 try{
 const stop=new Promise(resolve=>{abort=()=>{controller.abort();resolve(outcome(expired?'TIMEOUT_5S':'CANCELED'));};if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});timer=setTimeout(()=>{expired=true;abort()},budget);slow=setTimeout(()=>{if(!controller.signal.aborted)onSlow()},1500);});
 return await Promise.race([stop,work()]);
 }finally{clearTimeout(timer);clearTimeout(slow);signal?.removeEventListener('abort',abort);}
}
return {run};
})();
if(typeof module!=='undefined')module.exports=AuraMobileTransport;