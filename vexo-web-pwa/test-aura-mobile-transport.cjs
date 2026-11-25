async function verify(T){
 let n=0;const ok=(b,m)=>{if(!b)throw Error(m);n++};
 let calls=0,waits=[],budgets=[];
 const attempt=async(fn,ms)=>{budgets.push(ms);return fn(null)},wait=async ms=>waits.push(ms);
 const r=await T.interpret(async()=>{calls++;return calls===1?{ok:false,status:503}:{ok:true,json:async()=>({intent:'QUERY_DATA'})}},{attempt,wait});
 ok(r.kind==='response'&&r.attempts===2&&calls===2,'503 recovery');ok(JSON.stringify(waits)==='[500]'&&JSON.stringify(budgets)==='[2500,2500]','budget');
 calls=0;const f=await T.interpret(async()=>{calls++;return {ok:false,status:503}},{attempt,wait});ok(f.kind==='unavailable'&&f.attempts===2&&calls===2&&f.voice.includes('Rede instável'),'fallback');
 calls=0;const quota=await T.interpret(async()=>{calls++;return {ok:false,status:429}},{attempt,wait});ok(quota.kind==='unavailable'&&calls===1,'no quota retry');
 let i=0;const timeout=await T.interpret(async()=>({ok:true,json:async()=>({intent:'QUERY_DATA'})}),{attempt:async(fn)=>{if(i++===0)throw Object.assign(Error('timeout'),{code:'timeout'});return fn(null)},wait});ok(timeout.kind==='response'&&timeout.attempts===2,'timeout recovery');
 const bad=await T.interpret(async()=>({ok:true,json:async()=>{throw SyntaxError('invalid JSON')}}),{attempt,wait});ok(bad.kind==='unavailable'&&bad.attempts===1,'no retry malformed payload');
 return n;
}
verify(require('./aura-mobile-transport.js')).then(n=>console.log('Mobile transport: '+n+' checks')).catch(e=>{console.error(e);process.exitCode=1;});