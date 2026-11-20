import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {sentenceFor,createHandler,synthesizeWithGoogle} from './server.mjs';

test('only structured and bounded data can be voiced',()=>{
  assert.match(sentenceFor({kind:'intro'}),/E aí, motora/);
  assert.match(sentenceFor({kind:'offer_metrics',perKmCents:340,perHourCents:4500}),/R\$[\s\u00a0]3,40/);
  assert.equal(sentenceFor({kind:'offer_metrics',perKmCents:-1}),null);
  assert.equal(sentenceFor({kind:'offer_metrics',perHourCents:1.5}),null);
  assert.equal(sentenceFor({kind:'offer_metrics',perKmCents:1,passengerName:'ABC'}),null);
  assert.equal(sentenceFor({kind:'offer_metrics',screenImage:'BASE64'}),null);
  assert.equal(sentenceFor({kind:'intro',text:'arbitrary speech'}),null);
});
test('Google REST request sends only text and uses ADC bearer',async()=>{
  let captured;
  const fakeAudio=Buffer.alloc(600,42);
  const b64=fakeAudio.toString('base64');
  const result=await synthesizeWithGoogle('Aura',{auth:{getAccessToken:async()=>({token:'fake-token'})},
    fetcher:async(url,options)=>{captured={url,options};return {ok:true,json:async()=>({audioContent:b64})};}});
  assert.equal(result.length,600);
  assert.equal(captured.url,'https://texttospeech.googleapis.com/v1/text:synthesize');
  assert.equal(captured.options.headers.Authorization,'Bearer fake-token');
  const body=JSON.parse(captured.options.body);
  assert.equal(body.voice.name,'pt-BR-Chirp3-HD-Achernar');
  assert.equal(body.audioConfig.audioEncoding,'MP3');
});
test('HTTP endpoint enforces App Check, denies free-text, serves MP3',async()=>{
  const h=createHandler({
    verifyAppCheck:async(token)=>{if(token!=='valid-appcheck-token')throw new Error('invalid');},
    synthesize:async()=>Buffer.alloc(400,0x41)
  });
  const server=http.createServer(h);
  server.listen(0,'127.0.0.1');await once(server,'listening');
  try{
    const base='http://127.0.0.1:'+server.address().port+'/v1/aura/voice';
    const req=(body,token='valid-appcheck-token')=>fetch(base,{
      method:'POST',headers:{'Content-Type':'application/json','X-Firebase-AppCheck':token},
      body:JSON.stringify(body)
    });
    let response=await req({kind:'intro'},'invalid-appcheck-token');
    assert.equal(response.status,401);
    response=await req({kind:'unknown'});
    assert.equal(response.status,400);
    response=await req({kind:'offer_metrics',perKmCents:340});
    assert.equal(response.status,200);
    assert.equal(response.headers.get('content-type'),'audio/mpeg');
    assert.equal((await response.arrayBuffer()).byteLength,400);
  }finally{server.close();await once(server,'close');}
});
