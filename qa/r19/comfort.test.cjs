const assert = require('node:assert/strict');
const { readFileSync, existsSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { runInNewContext } = require('node:vm');

const source = process.env.VEXO_SOURCE_DIR || join(__dirname, '../aurora');
const script = join(source, 'app/src/main/assets/aurora/comfort.js');
const node = props => Object.assign(new EventTarget(), props);
function start(data = new Map(), { insetPage = false, blocked = false } = {}) {
  const elements = {
    'comfort-oled': node({ checked: false }),
    'comfort-hand': node({ value: 'off' }),
    'comfort-status': { textContent: '' },
  };
  const browser = node({ localStorage: {
    getItem(key) { if (blocked) throw Error('Storage unavailable'); return data.get(key) ?? null; },
    setItem(key, value) { if (blocked) throw Error('Storage unavailable'); data.set(key, value); },
  } });
  const root = { dataset: {} };
  const theme = { content: '#0b1117' };
  assert.ok(existsSync(script), 'Comfort preferences must be initialized by comfort.js');
  runInNewContext(readFileSync(script, 'utf8'), {
    window: browser,
    document: {
      documentElement: root,
      getElementById: id => insetPage ? null : elements[id],
      querySelector: () => theme,
    },
  });
  return { browser, root: root.dataset, theme, oled: elements['comfort-oled'], hand: elements['comfort-hand'], status: elements['comfort-status'] };
}

const change = control => control.dispatchEvent(new Event('change'));
test('appearance and handedness are off by default and persist independently', () => {
  const store = new Map([['vexo.turno.test-sentinel', 'preserve']]);
  const active = start(store);
  assert.equal(active.oled.checked, false);
  assert.equal(active.hand.value, 'off');
  assert.equal(active.theme.content, '#0b1117');
  assert.equal(store.size, 1);
  active.oled.checked = true;
  change(active.oled);
  active.hand.value = 'right';
  change(active.hand);
  let reloaded = start(store);
  assert.equal(reloaded.root.comfortOled, 'on');
  assert.equal(reloaded.root.comfortHand, 'right');
  assert.equal(reloaded.oled.checked, true);
  assert.equal(reloaded.hand.value, 'right');
  assert.equal(reloaded.theme.content, '#000000');
  reloaded.oled.checked = false;
  change(reloaded.oled);
  reloaded.hand.value = 'left';
  change(reloaded.hand);
  reloaded = start(store);
  assert.equal(reloaded.root.comfortOled, undefined);
  assert.equal(reloaded.root.comfortHand, 'left');
  assert.equal(reloaded.theme.content, '#0b1117');
  assert.equal(store.get('vexo.turno.test-sentinel'), 'preserve');
});

test('a page without settings receives the saved OLED preference and storage changes', () => {
  const store = new Map();
  const active = start(store);
  active.oled.checked = true;
  change(active.oled);
  const inset = start(store, { insetPage: true });
  assert.equal(inset.root.comfortOled, 'on');
  active.oled.checked = false;
  change(active.oled);
  inset.browser.dispatchEvent(Object.assign(new Event('storage'), { key: Array.from(store.keys())[0] }));
  assert.equal(inset.root.comfortOled, undefined);
  assert.equal(inset.theme.content, '#0b1117');
});

test('storage failure leaves visual controls usable and reports that changes are temporary', () => {
  const current = start(new Map(), { blocked: true });
  current.oled.checked = true;
  change(current.oled);
  assert.equal(current.root.comfortOled, 'on');
  assert.match(current.status.textContent, /só nesta tela/i);
});
