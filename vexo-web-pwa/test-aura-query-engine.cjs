async function verify(E,core,fixture){
 const now=new Date(2026,10,25,18),raw=fixture(),rates={fuel:.6,reserve:.15,fixed:6,eff:10};let reads=0,passed=0,session=null;
 const check=(v,m)=>{if(!v)throw Error(m);passed++},env={core,now,readData:async()=>{reads++;return {finance:raw,rates}}};
 const s=(tool,args)=>({tool,args}),r=(a={})=>s('rides',{period:'hoje',platform:'all',source:'all',status:'finished',operation:'sum',metric:'valor',...a}),p=(...steps)=>({mode:'new',plan:{version:1,steps}});
 const run=async(c,fn)=>{const v=await E.run(c,session,env);check(fn(v),JSON.stringify(v));session=v.session;return v};
 await run(p(r({platform:'Uber'})),v=>v.results[0].value===99);
 await run(p(s('offer',{gross:30,km:12,minutes:25})),v=>v.results[0].margin===18.5);
 await run({mode:'revise',baseTurn:session.turn,step:0,changes:{km:15}},v=>v.results[0].margin===16.25&&v.results[0].inputs.minutes===25);
 await run(p(r({period:{from:'2026-11-24',to:'2026-11-24'}})),v=>v.results[0].value===45);
 const before=reads;await run(p(r(),r({period:'ontem'})),v=>v.results[0].value===209.2&&v.results[1].value===45);check(reads===before+1,'One snapshot');
 const old=session;await run(p(s('explain',{concepts:['faturamento','lucro']})),v=>v.results[0].items.length===2&&v.session===old);
 await run(p(r({operation:'count',clock:{start:360,end:719}})),v=>v.results[0].value===4);
 await run(p(r({operation:'count',source:'real'})),v=>v.results[0].value===0);
 await run(p(r({filters:[{field:'valor',op:'gt',value:25},{field:'km',op:'gte',value:13}]})),v=>v.results[0].value===55.2);
 await run(p(r({operation:'extreme',metric:'valor',direction:'desc',fields:['valor','inicio']})),v=>v.results[0].rows[0].id==='MOB-TEST-0');
 const id=session.recordIds[0][0];await run(p(r({recordId:id,operation:'list',fields:['destino']})),v=>v.results[0].rows[0].id===id&&v.results[0].rows[0].values.destino===null);
 await run(p(r({operation:'ratio',metric:'valor_km'})),v=>v.results[0].value===2.02);
 const previous=session;await run(p(s('clarify',{missing:'metric'})),v=>v.session===previous);
 for(const bad of [p(r({period:{from:'2026-02-31',to:'2026-03-01'}})),p(r({platform:'uber'})),p(r({filters:[{field:'__proto__',op:'gt',value:2}]})),p(s('offer',{gross:30,km:'15',minutes:25})),p(s('write',{data:1})),{mode:'revise',baseTurn:session.turn-1,step:0,changes:{period:'ontem'}},p(r({operation:'sum',metric:'valor_km'})),p(r({operation:'count',clock:{start:1500,end:1600}}))]){const n=reads;let rejected=false;try{await E.run(bad,session,env)}catch{rejected=true}check(rejected&&reads===n,'Invalid command reached data');}
 const fuel=(ranges,platform='all')=>p(s('fuel_spent',{ranges,platform})),range=(from,to=from)=>({from,to});
 const split=await run(fuel([range('2026-11-24'),range('2026-11-25')]),v=>v.results[0].value===240&&v.results[0].count===2);
 await run(fuel([range('2026-11-24','2026-11-25')]),v=>v.results[0].value===split.results[0].value);
 await run(fuel([range('2026-11-24','2026-11-25'),range('2026-11-25')]),v=>v.results[0].value===240&&v.results[0].count===2);
 const gapRaw=fixture();gapRaw.fills.unshift(['F0','2026-11-23T07:00:00',800,10,5,'Gasolina',true,'Posto']);
 const gap=await E.run(fuel([range('2026-11-23'),range('2026-11-25')]),null,{...env,readData:async()=>({finance:gapRaw,rates})});check(gap.results[0].value===170&&gap.results[0].count===2,'Exclude intermediate date');
 const beforeReject=reads;let rejected=false;try{await E.run(fuel([range('2026-11-24')],'99'),session,env)}catch{rejected=true}check(rejected&&reads===beforeReject,'No invented fuel allocation');
 check(JSON.stringify(raw)===JSON.stringify(fixture()),'Data modified');return passed;
}
verify(require('./aura-query-engine.js'),require('./aura-core.js'),require('./test-aura-fixture.cjs')).then(n=>console.log('Engine contracts: '+n+' approved')).catch(e=>{console.error(e);process.exitCode=1;});