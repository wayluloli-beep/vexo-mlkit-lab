// Aura Sync Cloud TTS proxy for Cloud Run, never runs inside the APK.
// The Android client sends an App Check token and only typed financial metrics.
// No screen images, passenger names, route addresses, or raw OCR payloads are accepted.
import http from 'node:http';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const VOICE = 'pt-BR-Chirp3-HD-Achernar';
const TTS_ENDPOINT = 'https://texttospeech.googleapis.com/v1/text:synthesize';
const INTRO = 'E aí, motora. Eu sou a Aura, sua copiloto. Me diz quanto você quer botar no bolso hoje que eu filtro as corridas pra você.';
const BRL = new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});

export function sentenceFor(request) {
  if (request === null || typeof request !== 'object' || Array.isArray(request)) return null;
  const {kind} = request;
  if (kind === 'intro' && Object.keys(request).length===1) return INTRO;
  if (kind !== 'offer_metrics') return null;
  const keys = Object.keys(request);
  if (!keys.every(k=>['kind','perKmCents','perHourCents'].includes(k))) return null;
  const values = [];
  const km = request.perKmCents;
  const hour = request.perHourCents;
  if (km !== undefined) {
    if (!Number.isInteger(km) || km < 0 || km > 20000) return null;
    values.push(BRL.format(km / 100)+' por quilômetro');
  }
  if (hour !== undefined) {
    if (!Number.isInteger(hour) || hour < 0 || hour > 30000) return null;
    values.push(BRL.format(hour / 100)+' por hora');
  }
  if (!values.length) return null;
  // Numbers are based on validated client metrics; no imperative 'accept ride'.
  return 'Aura Sync. Esta solicitação está em '+values.join(' e ')+'. Confira o trajeto antes de decidir.';
}

export async function synthesizeWithGoogle(text,{auth,fetcher=fetch}={}) {
  if (typeof text !== 'string' || !text || text.length>280) throw new Error('text length');
  if (!auth) throw new Error('Google ADC unavailable');
  const tokenResponse = await auth.getAccessToken();
  const token = typeof tokenResponse==='string'?tokenResponse:tokenResponse?.token;
  if (!token) throw new Error('Google access token unavailable');
  const result = await fetcher(TTS_ENDPOINT,{
    method:'POST',
    headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
    body:JSON.stringify({
      input:{text},
      voice:{languageCode:'pt-BR',name:VOICE},
      audioConfig:{audioEncoding:'MP3'}
    }),
    signal:AbortSignal.timeout(9000)
  });
  if (!result.ok) throw new Error('Google TTS request failed: '+result.status);
  const response=await result.json();
  const encoded=response?.audioContent;
  if (typeof encoded!=='string' || encoded.length>1400000 || !/^[a-zA-Z0-9+/]+={0,2}$/.test(encoded))
    throw new Error('Google audio payload invalid');
  const audio=Buffer.from(encoded,'base64');
  if (audio.length<256 || audio.length>900000) throw new Error('Google audio size invalid');
  return audio;
}

export function createHandler({verifyAppCheck,synthesize,now=()=>Date.now()}){
  if (typeof verifyAppCheck!=='function' || typeof synthesize!=='function') throw new Error('injection required');
  const rates=new Map();
  return async function handler(req,res){
    const headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Access-Control-Allow-Origin':'null'};
    const respond=(status,json)=>{
      if(res.headersSent)return;
      res.writeHead(status,{...headers,'Content-Type':'application/json; charset=utf-8'});
      res.end(JSON.stringify({error:json}));
    };
    if(req.method!=='POST' || req.url!=='/v1/aura/voice')return respond(404,'not_found');
    if(!String(req.headers['content-type']||'').toLowerCase().startsWith('application/json'))
      return respond(415,'json_required');
    const appCheck=String(req.headers['x-firebase-appcheck']||'');
    if(appCheck.length<16 || appCheck.length>5000)return respond(401,'app_check_required');
    try { await verifyAppCheck(appCheck); } catch {return respond(401,'app_check_invalid');}
    // Cost protection; deploy additionally with Cloud Run quotas and billing budgets.
    const key=createHash('sha256').update(appCheck).digest('hex');
    const stamp=now(),previous=rates.get(key);
    const limit=previous && stamp-previous.start<60000?previous:{start:stamp,count:0};
    limit.count++;rates.set(key,limit);
    if(limit.count>10)return respond(429,'rate_limited');
    if(rates.size>3000)rates.clear();
    let chunks=[],size=0;
    try {
      for await (const part of req) {
        size+=part.length;
        if(size>800) return respond(413,'request_too_large');
        chunks.push(part);
      }
      const body=JSON.parse(Buffer.concat(chunks).toString('utf8'));
      const text=sentenceFor(body);
      if(!text)return respond(400,'invalid_utterance');
      const audio=await synthesize(text);
      if(!Buffer.isBuffer(audio)||audio.length<256||audio.length>900000)
        return respond(502,'invalid_audio');
      res.writeHead(200,{...headers,'Content-Type':'audio/mpeg','Content-Length':audio.length});
      res.end(audio);
    } catch {
      respond(502,'voice_unavailable');
    }
  };
}

async function boot(){
  // ADC uses the Cloud Run service account; no JSON key is needed in source.
  const [{GoogleAuth},{initializeApp,applicationDefault},{getAppCheck}]=await Promise.all([
    import('google-auth-library'),import('firebase-admin/app'),import('firebase-admin/app-check')
  ]);
  initializeApp({credential:applicationDefault(),projectId:process.env.GOOGLE_CLOUD_PROJECT});
  const service= new GoogleAuth({scopes:['https://www.googleapis.com/auth/cloud-platform']});
  const client=await service.getClient();
  const handler=createHandler({
    verifyAppCheck:(token)=>getAppCheck().verifyToken(token),
    synthesize:(text)=>synthesizeWithGoogle(text,{auth:client})
  });
  const port=Number(process.env.PORT||8080);
  if(!Number.isInteger(port)||port<1||port>65535)throw new Error('PORT invalid');
  http.createServer(handler).listen(port,'0.0.0.0');
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1]){
  boot().catch(()=>{process.stderr.write('Aura backend could not start\n');process.exitCode=1;});
}
