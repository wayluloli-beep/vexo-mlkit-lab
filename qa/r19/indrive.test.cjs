const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const assets = path.join(process.env.VEXO_SOURCE_DIR || path.join(__dirname, '..', 'aurora'),
  'app/src/main/assets/aurora');
const script = fs.readFileSync(path.join(assets, 'turno.js'), 'utf8');
const start = 1_770_000_000_000;
const hour = 3_600_000;

function core() {
  const context = {window: {}};
  vm.runInNewContext(script, context);
  return context.window.VexoTurno;
}

function memory() {
  const data = new Map();
  return {getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value)};
}

const plain = value => JSON.parse(JSON.stringify(value));

test('inDrive tem lançamento próprio e entra uma só vez na soma dos recebimentos', () => {
  const api = core();
  const store = memory();
  api.begin(store, start);
  const fields = {uber: '150,50', nove: '69,50', indrive: '35,25', outros: '5,75', fuel: '50', extra: '10', km: '100'};
  const expected = {
    received: 26100, spent: 6000, net: 20100, km: 100,
    entries: {uber: 15050, nove: 6950, indrive: 3525, outros: 575, fuel: 5000, extra: 1000, km: 100000}
  };
  assert.deepEqual(plain(api.preview(fields)), expected);
  assert.deepEqual(plain(api.close(store, fields, start + hour)), {
    startedAt: start, endedAt: start + hour, ...expected, perHour: 20100, perKm: 201
  });
  assert.equal(core().read(store).history[0].entries.indrive, 3525);
  assert.equal(api.today(api.read(store), start + hour).received, 26100);
});

test('inDrive pode ser o único recebimento e aceita zero explícito', () => {
  const api = core();
  assert.equal(api.preview({indrive: '18,90'}).received, 1890);
  assert.equal(api.preview({indrive: '0'}).received, 0);
  assert.equal(api.preview({indrive: '', outros: '3'}).entries.indrive, null);
  assert.throws(() => api.preview({indrive: ''}), /Informe pelo menos um recebimento/);
});

test('valor inválido do inDrive aponta para o campo certo sem encerrar o turno', () => {
  const api = core();
  const store = memory();
  api.begin(store, start);
  const before = store.getItem(api.key);
  for (const indrive of ['-1', '9,001', '1e3']) {
    const fields = {uber: '2', indrive};
    const invalidInDrive = err => err.field === 'indrive' && /inDrive/.test(err.message);
    assert.throws(() => api.preview(fields), invalidInDrive);
    assert.throws(() => api.close(store, fields, start + hour), invalidInDrive);
    assert.equal(store.getItem(api.key), before);
  }
});

test('rascunho preserva inDrive sem reclassificar o histórico ou o rascunho R18', () => {
  const api = core();
  const store = memory();
  const legacy = {
    active: {startedAt: start + hour, draft: {uber: ' 2, ', outros: '5,50'}},
    history: [{
      startedAt: start, endedAt: start + hour, received: 1500, spent: 0, net: 1500, km: null,
      entries: {uber: null, nove: null, outros: 1500, fuel: null, extra: null, km: null},
      perHour: 1500, perKm: null
    }]
  };
  store.setItem(api.key, JSON.stringify(legacy));
  assert.deepEqual(plain(api.read(store)), legacy);
  assert.equal(Object.hasOwn(api.preview({outros: '5,50'}).entries, 'indrive'), false);
  api.saveDraft(store, {...legacy.active.draft, indrive: ' 12, ', appTotal: '100'});
  const reopened = core();
  const saved = plain(reopened.read(store));
  assert.deepEqual(saved.active.draft, {uber: ' 2, ', outros: '5,50', indrive: ' 12, '});
  assert.deepEqual(saved.history, legacy.history);
});
