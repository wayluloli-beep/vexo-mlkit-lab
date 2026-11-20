const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const assets = path.join(process.env.VEXO_SOURCE_DIR || path.join(__dirname, '..', 'aurora'), 'app/src/main/assets/aurora');
const key = 'vexo.privacy-values.v1';

class Element extends EventTarget {
  constructor() { super(); this.attributes = new Map(); this.hidden = false; this.value = ''; this.checked = false; }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  setAttribute(name, value) { this.attributes.set(name, value); }
  removeAttribute(name) { this.attributes.delete(name); }
  toggleAttribute(name, on) { if (on) this.setAttribute(name, ''); else this.removeAttribute(name); }
  click() { this.dispatchEvent(new Event('click')); }
}

function home(storage = new Map()) {
  const document = new EventTarget(), window = new EventTarget();
  const elements = new Map(['privacy-values', 'privacy-toggle', 'privacy-auto', 'privacy-status', 'turno-form'].map(id => [id, new Element()]));
  const fields = ['uber', 'indrive', 'cash', 'km'].map(name => Object.assign(new Element(), {name}));
  const [field, indrive, cash, km] = fields, timers = new Map(), observed = new Map();
  let now = 1, serial = 0, onMutations;
  document.documentElement = new Element();
  document.getElementById = id => elements.get(id);
  elements.get('turno-form').querySelectorAll = selector => fields.filter(input =>
    selector === "input[inputmode='decimal']:not([name='km'])" ? input.name !== 'km' : selector.includes("[name='" + input.name + "']")
  );
  const ctx = {
    document, window, Date: {now: () => now},
    localStorage: {getItem: k => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v)},
    clearTimeout: id => timers.delete(id),
    setTimeout: (fn, ms) => { const id = ++serial; timers.set(id, [now + ms, fn]); return id; },
    MutationObserver: class { constructor(callback) { onMutations = callback; } observe(target, options) { observed.set(target, options.attributeFilter); } },
  };
  const file = path.join(assets, 'privacy-values.js');
  if (fs.existsSync(file)) vm.runInNewContext(fs.readFileSync(file, 'utf8'), ctx);
  const isMasked = () => document.documentElement.getAttribute('data-vexo-values-hidden') !== null;
  const startupMasked = isMasked();
  document.dispatchEvent(new Event('DOMContentLoaded'));
  const button = elements.get('privacy-toggle'), auto = elements.get('privacy-auto');
  return {
    document, window, button, auto, field, indrive, cash, km, storage, isMasked, startupMasked,
    setAuto(checked) { auto.checked = checked; auto.dispatchEvent(new Event('change')); },
    supplyHint(value, target = field) {
      target.setAttribute('placeholder', value);
      if (observed.get(target)?.includes('placeholder')) onMutations([{target, attributeName: 'placeholder'}]);
    },
    advance(ms) {
      const until = now + ms;
      while (timers.size) {
        const next = [...timers].sort((a, b) => a[1][0] - b[1][0])[0];
        if (next[1][0] > until) break;
        now = next[1][0];
        timers.delete(next[0]);
        next[1][1]();
      }
      now = until;
    },
  };
}

test('manual masking takes one tap and is restored before Home initializes', () => {
  const page = home();
  assert.equal(page.button.textContent, 'Ocultar valores');
  page.button.click();
  assert.equal(page.button.textContent, 'Mostrar valores');
  assert.equal(page.isMasked(), true);
  const reopened = home(page.storage);
  assert.equal(reopened.startupMasked, true);
  reopened.button.click();
  assert.equal(reopened.isMasked(), false);
  assert.equal(home(page.storage).startupMasked, false);
});

test('previous monetary placeholders disappear when masked but previously typed values survive', () => {
  const page = home();
  page.button.click();
  page.supplyHint('Último: 163,52');
  page.supplyHint('Último: 35,01', page.indrive);
  page.supplyHint('Último: 21,00', page.cash);
  page.supplyHint('Último: 137', page.km);
  assert.equal(page.field.getAttribute('placeholder'), null);
  assert.equal(page.indrive.getAttribute('placeholder'), null);
  assert.equal(page.cash.getAttribute('placeholder'), null);
  assert.equal(page.km.getAttribute('placeholder'), 'Último: 137');
  page.field.value = '123,57';
  page.button.click();
  assert.equal(page.field.getAttribute('placeholder'), 'Último: 163,52');
  assert.equal(page.indrive.getAttribute('placeholder'), 'Último: 35,01');
  assert.equal(page.cash.getAttribute('placeholder'), 'Último: 21,00');
  assert.equal(page.field.value, '123,57');
});

test('auto mask is opted in, waits for 30 idle seconds, and does not replace manual preference', () => {
  const page = home();
  assert.equal(page.auto.checked, false);
  page.advance(31000);
  assert.equal(page.isMasked(), false);
  page.setAuto(true);
  page.advance(25000);
  page.document.dispatchEvent(new Event('input'));
  page.advance(10000);
  assert.equal(page.isMasked(), false);
  page.advance(20000);
  assert.equal(page.isMasked(), true);
  const reopened = home(page.storage);
  assert.equal(reopened.auto.checked, true);
  assert.equal(reopened.startupMasked, false);
  page.button.click();
  assert.equal(page.isMasked(), false);
  page.button.click();
  page.setAuto(false);
  assert.equal(page.isMasked(), true);
});

test('invalid stored privacy settings cannot enable automatic hiding', () => {
  const page = home(new Map([[key, '{"manual":"false","auto":"true"}']]));
  assert.equal(page.auto.checked, false);
  assert.equal(page.isMasked(), false);
});
