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
  assert.doesNotMatch(read(kotlin, 'AuroraActivity.kt'), /PixelCopy|TextRecognition|ScreenCapture|Sincronizador|WorkManager|tile\.openstreetmap\.org/);
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
    ['appVersion', 'fuelPrice', 'hourlyGoalCents', 'kmPerLiter', 'readManualTurn', 'readPrivacyPrefs', 'saveFuel', 'setHourlyGoalCents', 'writeManualTurn', 'writePrivacyPrefs']);
  assert.doesNotMatch(activity, /MODE_WORLD|loadDataWithBaseURL/);
  assert.ok(existsSync(join(src,'app/src/test/java/com/trackingracing/VexoManualWebTest.kt')));
});

test('platform backup is disabled on both supported Android generations', () => {
  const manifest = read(main, 'AndroidManifest.xml');
  assert.match(manifest, /android:allowBackup="false"/);
  assert.match(manifest, /android:fullBackupContent="false"/);
  assert.match(manifest, /android:dataExtractionRules="@xml\/vexo_data_extraction_rules"/);
  const rules = read(main, 'res/xml/vexo_data_extraction_rules.xml');
  for (const section of ['cloud-backup','device-transfer']) {
    const body = rules.split('<' + section + '>')[1]?.split('</' + section + '>')[0] || '';
    for (const domain of ['root','sharedpref','database','device_root','device_sharedpref','device_database']) {
      assert.ok(body.includes('<exclude domain="' + domain + '" path="."'), section + ' ' + domain);
    }
  }
});
