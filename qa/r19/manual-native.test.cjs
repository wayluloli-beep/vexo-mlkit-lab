const test = require('node:test');
const assert = require('node:assert/strict');
const { readdirSync, readFileSync, existsSync } = require('node:fs');
const { join } = require('node:path');
const src = process.env.VEXO_SOURCE_DIR || join(__dirname, '..', 'aurora');
const main = join(src, 'app/src/main');
const kotlin = join(main, 'java/com/trackingracing');
const read = (...parts) => readFileSync(join(...parts), 'utf8');

test('manual Android source set contains no capture, ride lab or spreadsheet upload code', () => {
  assert.deepEqual(readdirSync(kotlin).sort(), ['AuroraActivity.kt', 'VexoManualWeb.kt']);
  const gradle = read(src, 'app/build.gradle.kts');
  assert.doesNotMatch(gradle, /mlkit|work-runtime|appcompat/);
  const manifest = read(main, 'AndroidManifest.xml');
  assert.doesNotMatch(manifest, /POST_NOTIFICATIONS|FOREGROUND_SERVICE|BLUETOOTH|_LOCATION|FileProvider|<service/);
  assert.doesNotMatch(read(kotlin, 'AuroraActivity.kt'), /PixelCopy|TextRecognition|ScreenCapture|Sync|tile\.openstreetmap\.org/);
});

test('manual bridge preserves the local package, WebView origin and persisted money and fuel keys', () => {
  const activity = read(kotlin, 'AuroraActivity.kt');
  const domain = read(kotlin, 'VexoManualWeb.kt');
  assert.match(domain, /appassets\.androidplatform\.net/);
  assert.match(read(src, 'app/build.gradle.kts'), /applicationId\s*=\s*"com\.trackingracing"/);
  for(const key of ['VexoAndroidOcr', 'aurora_balloon', 'km', 'price', 'vexo.gain-goal', 'hourly_cents']) {
    assert.ok(activity.includes('"' + key + '"'), key);
  }
  assert.deepEqual([...activity.matchAll(/@JavascriptInterface\s+fun\s+(\w+)/g)].map(m=>m[1]).sort(),
    ['appVersion', 'fuelPrice', 'hourlyGoalCents', 'kmPerLiter', 'saveFuel', 'setHourlyGoalCents']);
  assert.doesNotMatch(activity, /MODE_WORLD|loadDataWithBaseURL/);
  assert.ok(existsSync(join(src,'app/src/test/java/com/trackingracing/VexoManualWebTest.kt')));
});
