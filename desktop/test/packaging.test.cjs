const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { REQUIRED, checkPayload, builderConfig } = require('../packaging.cjs');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'edunova-payload-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const files = REQUIRED.map(relative => {
    const data = Buffer.from('synthetic packaging fixture: ' + relative);
    const target = path.join(root, relative);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, data);
    return { path: relative, bytes: data.length, sha256: crypto.createHash('sha256').update(data).digest('hex') };
  });
  const manifest = { schemaVersion: 1, redistributionReviewed: true, files };
  const save = () => fs.writeFileSync(path.join(root, 'payload-manifest.json'), JSON.stringify(manifest), 'utf8');
  save();
  return { root, manifest, save };
}

test('accepts a complete hash-verified payload, not arbitrary staging contents', t => {
  const { root } = fixture(t);
  assert.equal(checkPayload(root).fileCount, REQUIRED.length);
});
test('rejects changed files and missing runtime components', t => {
  const { root } = fixture(t);
  fs.appendFileSync(path.join(root, REQUIRED[0]), 'changed');
  assert.throws(() => checkPayload(root), /校验失败/);
  fs.unlinkSync(path.join(root, REQUIRED[0]));
  assert.throws(() => checkPayload(root), /缺少安装资源/);
});
test('does not ship local credentials, unlisted files or trial fixtures', t => {
  const { root } = fixture(t);
  for (const name of ['.env', 'probe_local.py', 'unexpected.json']) {
    const file = path.join(root, 'app', name);
    fs.writeFileSync(file, 'synthetic', 'utf8');
    assert.throws(() => checkPayload(root), /配置、测试文件|未登记/);
    fs.unlinkSync(file);
  }
});
test('rejects path traversal and duplicate manifest entries', t => {
  const { root, manifest, save } = fixture(t);
  manifest.files.push({ ...manifest.files[0], path: 'app/../../outside' }); save();
  assert.throws(() => checkPayload(root), /无效路径/);
  manifest.files.pop(); manifest.files.push(manifest.files[0]); save();
  assert.throws(() => checkPayload(root), /重复条目/);
});

test('allows registered OpenAI upload modules while rejecting user upload directories', t => {
  const { root, manifest, save } = fixture(t);
  for (const kind of ['resources', 'types']) {
    const relative = `runtime/python/Lib/site-packages/openai/${kind}/uploads/__init__.py`;
    const bytes = Buffer.from('# synthetic SDK module\n');
    fs.mkdirSync(path.dirname(path.join(root, relative)), { recursive: true });
    fs.writeFileSync(path.join(root, relative), bytes);
    manifest.files.push({ path: relative, bytes: bytes.length,
      sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
  }
  save();
  assert.equal(checkPayload(root).fileCount, REQUIRED.length + 2);
  for (const relative of ['app/uploads', 'runtime/python/uploads']) {
    fs.mkdirSync(path.join(root, relative), { recursive: true });
    assert.throws(() => checkPayload(root), /本地工作数据/);
    fs.rmdirSync(path.join(root, relative));
  }
});
test('unreviewed redistribution blocks installer creation', t => {
  const { root, manifest, save } = fixture(t);
  manifest.redistributionReviewed = false; save();
  assert.throws(() => checkPayload(root), /分发材料尚未核对/);
  const result = checkPayload(root, { localTest: true });
  assert.equal(result.redistributionReviewed, false);
  assert.equal(result.localTest, true);
  assert.equal(JSON.parse(fs.readFileSync(path.join(root, 'payload-manifest.json'), 'utf8')).redistributionReviewed, false);
  fs.appendFileSync(path.join(root, REQUIRED[0]), 'tampered');
  assert.throws(() => checkPayload(root, { localTest: true }), /校验失败/);
});

test('local test builds have separate output and visibly distinct artifact names', () => {
  const config = builderConfig('C:\\synthetic-payload', { localTest: true });
  assert.equal(config.directories.output, 'dist/local-test');
  assert.match(config.nsis.artifactName, /LocalTest/);
  assert.equal(builderConfig('C:\\synthetic-payload').directories.output, 'dist/release');
});
test('installer preserves user data and includes only runtime host files', () => {
  const config = builderConfig('C:\\synthetic-payload');
  assert.equal(config.nsis.deleteAppDataOnUninstall, false);
  assert.equal(config.nsis.allowElevation, false);
  assert.equal(config.nsis.runAfterFinish, false);
  assert.equal(config.npmRebuild, false);
  assert.equal(config.files.includes('packaging.cjs'), false);
  assert.equal(config.files.some(file => file.includes('test')), false);
});
