const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const filename = process.env.VEXO_HTML || process.argv[2];
if (!filename) throw new Error('Set VEXO_HTML to the R13 or R14 index.html');
const html = fs.readFileSync(filename, 'utf8');
const local = html.match(/<script id="vexo-local-ocr">([\s\S]*?)<\/script>/)?.[1];
const report = html.match(/(window\.VexoTreino = \(\(\) => \{[\s\S]*?^\}\)\(\);)/m)?.[1];
assert.ok(local && report, 'expected production OCR and report scripts');
function load() {
  const w = new EventTarget();
  vm.runInNewContext(`${local}\n${report}`, {window:w, performance});
  return w;
}
const runId = '2026-11-20T12:00:00.000Z';
const tokenA = '1795176000000-0';
const tokenB = '1795176000000-1';
const rideA = {id:'pop-a', price:8.3, rating:4.8, isNegocia:false,
  pickup:{minutes:4, distanceLabel:'1.1 km', address:'Rua A'},
  dropoff:{minutes:13, distanceLabel:'5.1 km', address:'Rua B'}};
const rideB = {...rideA, id:'pop-b', price:16.9};
function dispatch(w, detail) {
  return w.dispatchEvent(new CustomEvent('aurora-native-ocr', {detail, cancelable:true}));
}

test('a delayed frame for A cannot update the bubble or history after B takes over', () => {
  const w = load(), rows = [];
  let active = tokenA;
  const off = w.VexoLocalOcr.subscribe(data => rows.push(data), () => active);
  assert.equal(dispatch(w, {cardToken:tokenA, offer:rideA, capturedAtMs:71, ocrMs:18}), true);
  active = tokenB;
  assert.equal(dispatch(w, {cardToken:tokenA, offer:rideA, capturedAtMs:72, ocrMs:25}), false, 'stale event must be canceled');
  assert.equal(dispatch(w, {cardToken:tokenB, offer:rideB, capturedAtMs:90, ocrMs:20}), true);
  assert.deepEqual(rows.map(row => row.offer.id), ['pop-a', 'pop-b']);
  assert.deepEqual(rows.map(row => row.row.cardToken), [tokenA, tokenB]);
  off();
});

test('hidden or closed watch rejects both missing and once-valid tokens', () => {
  const w = load(), seen = [];
  let active = tokenA;
  w.VexoLocalOcr.subscribe(x => seen.push(x), () => active);
  assert.equal(dispatch(w, {offer:rideA}), false);
  active = '';
  assert.equal(dispatch(w, {cardToken:tokenA, offer:rideA}), false);
  assert.deepEqual(seen, []);
});

test('consumer rejection is reported to the native dispatch acknowledgment', () => {
  const w = load();
  w.VexoLocalOcr.subscribe(() => false, () => tokenA);
  assert.equal(dispatch(w, {cardToken:tokenA, offer:rideA}), false);
});

test('report attributes reads to the card token, never to the receipt wall-clock interval', () => {
  const w = load();
  const run = {id:runId, start:100, log:[
    {step:1, wallMs:1000, frameCallbackAtMs:0},
    {step:2, wallMs:2000, frameCallbackAtMs:1000},
    {step:3, wallMs:3000, frameCallbackAtMs:2000},
  ], run:{steps:[{phase:'offer',ride:rideA}, {phase:'offer',ride:rideB}, {phase:'online'}]}};
  const rows = [
    {source:'ocr-simulador', session:runId, cardToken:tokenA, ride:rideA, time:2350, receivedAtMs:1200, capturedAtMs:71},
    {source:'ocr-simulador', session:runId, cardToken:tokenB, ride:rideB, time:2900, receivedAtMs:1460, capturedAtMs:90},
    {source:'ocr-simulador', session:'not-this-run', cardToken:tokenB, ride:rideA, time:2200, receivedAtMs:1240, capturedAtMs:1},
    {source:'ocr-simulador', session:runId, ride:rideB, time:2500, receivedAtMs:1300, capturedAtMs:94},
  ];
  const result = w.VexoTreino.report(run, rows, 3000);
  assert.equal(result[0].reads, 1, 'old card cannot lose a read merely because the receipt wall clock changed');
  assert.equal(result[0].checks['Preço'], true);
  assert.equal(result[1].reads, 1, 'other sessions and unbound rows cannot enter the report');
  assert.equal(result[1].checks['Preço'], true);
  assert.equal(result[1].latency, 360);
});

test('a valid applied reading gets an acceptance marker and a canceled or empty reading does not', () => {
  const w = load();
  const good = {cardToken:tokenA, offer:rideA, capturedAtMs:71, ocrMs:18};
  assert.equal(dispatch(w, good), true);
  assert.equal(good.accepted, undefined, 'dispatch without a subscriber is not acceptance');
  w.VexoLocalOcr.subscribe(() => {}, () => tokenA);
  assert.equal(dispatch(w, good), true);
  assert.equal(good.accepted, true);
  const blank = {cardToken:tokenA};
  assert.equal(dispatch(w, blank), true);
  assert.equal(blank.accepted, undefined);
  const stale = {cardToken:tokenB, offer:rideB};
  assert.equal(dispatch(w, stale), false);
  assert.equal(stale.accepted, undefined);
});

test('local crop is bounded to the visible card and contains only geometry', () => {
  const {VexoLocalOcr: api} = load();
  const card = {left:-12,top:330,right:368,bottom:815,price:8.3};
  assert.deepEqual(Array.from(api.visibleBounds(card, 360, 800)), [0,330,360,800,360,800]);
  assert.equal(api.visibleBounds({...card,top:850}, 360, 800), null);
  assert.equal(api.visibleBounds({...card,left:NaN},360,800), null);
});
