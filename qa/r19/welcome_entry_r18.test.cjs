const test = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const html = readFileSync(join(process.env.VEXO_SOURCE_DIR || join(__dirname,'..','aurora'), 'app/src/main/assets/aurora/onboarding.html'),'utf8');
const part = (begin, end) => {
  const start=html.indexOf(begin), stop=html.indexOf(end,start+begin.length);
  assert.ok(start>=0 && stop>start, `${begin} not found`);
  return html.slice(start,stop);
};
const helper = html.includes('function enterWelcome(') ? part('function enterWelcome(', 'planEnter.onclick=') : '';
function load({phase='interview',accepted=true,failWrite=false}={}) {
  const key='vexo.entry.sequence.x4',profile='vexo.gain-profile.v1';
  const store = new Map([[key,phase],[profile,'existing profile']]);
  const localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>{if(failWrite)throw Error('Quota');store.set(k,v);}};
  const navigations=[], routes=[], input={hidden:true,textContent:''};
  const screen={innerHTML:'',className:'',querySelector:()=>({}),on:{},addEventListener(event,fn){this.on[event]=fn}};
  const ctx=vm.createContext({page:'home',busy:false,stack:['home'],s:{},screen,window:{VexoGainPlan:{hasDraft:()=>false}},shell:{dataset:{}},planFinish:{},localStorage,launchSequenceKey:key,
    entryDisclosure:{hasAccepted:()=>accepted}, location:{replace:url=>navigations.push(url)}, $:()=>input,icon:()=>'<svg></svg>',
    wrap:(_,title,sub,body)=>`<h1>${title}</h1><p>${sub}</p>${body}`,
    route:(...args)=>routes.push(args),interviewRequired:()=>localStorage.getItem(key)==='interview'});
  vm.runInContext(`${helper}\n${part('function paint(){','function updateCar(')}\n${part('screen.addEventListener("click",','document.addEventListener("keydown",')}\npaint();`,ctx);
  const click=action=>screen.on.click({target:{closest:()=>({dataset:{action}})}});
  return {screen,click,navigations,routes,store,key,profile,input};
}
test('first welcome has direct and optional paths, with no mandatory form',()=>{
  const x=load();
  assert.match(x.screen.innerHTML,/<h1>E aí, motora\?<\/h1>/);
  assert.match(x.screen.innerHTML,/data-action="enter-welcome"[^>]*>Entrar no Vexo/);
  assert.match(x.screen.innerHTML,/data-action="begin"[^>]*>Configurar meu plano/);
  assert.doesNotMatch(x.screen.innerHTML,/<(?:form|input|select)\b/);
});
test('one tap passes from welcome into app, never replacing an existing profile',()=>{
  const x=load();
  x.click('enter-welcome'); x.click('enter-welcome');
  assert.deepEqual(x.navigations,['./index.html']);
  assert.equal(x.store.get(x.key),'app');
  assert.equal(x.store.get(x.profile),'existing profile');
  assert.deepEqual(x.routes,[]);
});
test('without accepted terms direct entry sends user back to terms',()=>{
  const x=load({accepted:false}); x.click('enter-welcome');
  assert.deepEqual(x.routes,[['disclosure',false]]);
  assert.equal(x.store.get(x.key),'interview');
  assert.deepEqual(x.navigations,[]);
});
test('when progress cannot be saved do not navigate and explain retry',()=>{
  const x=load({failWrite:true}); x.click('enter-welcome');
  assert.equal(x.store.get(x.key),'interview');
  assert.equal(x.input.hidden,false);
  assert.match(x.input.textContent,/tente.*novo/i);
  assert.deepEqual(x.navigations,[]);
});
test('detailed plan is optional and still available after entering before',()=>{
  const fresh=load();fresh.click('begin');
  assert.deepEqual(fresh.routes,[['work']]);assert.deepEqual(fresh.navigations,[]);
  const returning=load({phase:'app'});returning.click('begin');
  assert.match(returning.screen.innerHTML,/Quanto precisa sobrar no bolso\?/);
  assert.deepEqual(returning.routes,[['work']]);
});
