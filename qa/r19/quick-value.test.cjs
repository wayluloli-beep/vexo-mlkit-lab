const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const assets = path.join(process.env.VEXO_SOURCE_DIR || path.join(__dirname, '..', 'aurora'),
  'app/src/main/assets/aurora');
const quickAsset = path.join(assets, 'quick-value.js');
const plain = value => JSON.parse(JSON.stringify(value));

function boot(document) {
  const context = {window: {}, document};
  Object.defineProperty(context, 'localStorage', {get() { throw Error('no guest storage'); }});
  vm.runInNewContext(fs.readFileSync(path.join(assets, 'turno.js'), 'utf8'), context);
  if (fs.existsSync(quickAsset)) vm.runInNewContext(fs.readFileSync(quickAsset, 'utf8'), context);
  const api = context.window.VexoQuickValue;
  assert.equal(typeof api?.calculate, 'function', 'cálculo rápido ainda não existe');
  return api;
}

test('calcula dinheiro brasileiro sem arredondar os centavos e não depende de armazenamento', () => {
  const api = boot();
  assert.deepEqual(plain(api.calculate({received: '1.230,50', spent: '70,25'})), {
    received: 123050, spent: 7025, net: 116025,
  });
  assert.deepEqual(plain(api.calculate({received: '0,32', spent: '0,31'})), {
    received: 32, spent: 31, net: 1,
  });
});

test('distingue gasto não informado de zero e mantém prejuízo com sinal', () => {
  const api = boot();
  assert.deepEqual(plain(api.calculate({received: '180,20', spent: '  '})), {received: 18020, spent: null, net: 18020});
  assert.deepEqual(plain(api.calculate({received: '0', spent: '0'})), {received: 0, spent: 0, net: 0});
  assert.deepEqual(plain(api.calculate({received: '0', spent: '42,10'})), {received: 0, spent: 4210, net: -4210});
});

test('valor inválido indica o campo certo em vez de calcular como zero', () => {
  const api = boot();
  for (const received of ['', '  ', '25,015', '-1', '1e3']) {
    assert.throws(() => api.calculate({received, spent: '0'}), err => err.field === 'received' && /recebeu/i.test(err.message));
  }
  for (const spent of ['3,511', '-1', '1e3']) {
    assert.throws(() => api.calculate({received: '8', spent}), err => err.field === 'spent' && /gastos/i.test(err.message));
  }
});

test('a prévia mostra a sobra e é descartada ao recolher a seção', () => {
  const fragment = fs.readFileSync(path.join(__dirname, 'quick-value-fragment.html'), 'utf8');
  const ids = new Map([...fragment.matchAll(/\bid="([^"]+)"/g)].map(([, id]) => {
    const events = new Map();
    return [id, {
      attributes: new Map(), hidden: true, value: '', textContent: '',
      addEventListener: (type, callback) => events.set(type, callback),
      setAttribute(name, value) {this.attributes.set(name, value);},
      removeAttribute(name) {this.attributes.delete(name);},
      focus() {this.focused = true;},
      emit(type, event) {events.get(type)?.(event);},
    }];
  }));
  const node = key => ids.get('quick-value' + (key ? '-' + key : ''));
  const block = node(), form = node('form'), received = node('received'), spent = node('spent');
  const result = node('answer'), amount = node('amount'), note = node('note');
  form.reset = () => {received.value = ''; spent.value = '';};
  boot({getElementById: id => ids.get(id)});
  assert.equal(block.hidden, false);
  block.open = true;
  received.value = '220';
  spent.value = '60';
  let prevented = false;
  form.emit('submit', {preventDefault() {prevented = true;}});
  assert.equal(prevented, true);
  assert.equal(result.hidden, false);
  assert.match(amount.textContent, /R\$\s*160,00/);
  assert.match(note.textContent, /gastos que você informou/);
  assert.equal(result.focused, true);

  spent.value = '-5';
  form.emit('input');
  assert.equal(amount.textContent, '');
  form.emit('submit', {preventDefault() {}});
  assert.equal(result.hidden, true);
  assert.equal(spent.attributes.get('aria-invalid'), 'true');
  assert.match(node('error').textContent, /gastos/);

  block.open = false;
  block.emit('toggle');
  assert.equal(received.value, '');
  assert.equal(spent.value, '');
  assert.equal(result.hidden, true);
  assert.equal(node('error').textContent, '');
  assert.equal(spent.attributes.has('aria-invalid'), false);
});
