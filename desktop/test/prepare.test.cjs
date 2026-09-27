const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { validateProfilePath } = require('../prepare.cjs');

test('accepts redirected profile paths but rejects different directories', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'edunova-profile-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const data = path.join(root, 'data');
  const profile = path.join(data, 'profile');
  const alias = path.join(root, 'redirected');
  const other = path.join(root, 'other');
  fs.mkdirSync(profile, { recursive: true });
  fs.mkdirSync(other);
  fs.symlinkSync(data, alias, process.platform === 'win32' ? 'junction' : 'dir');
  assert.doesNotThrow(() => validateProfilePath(profile, alias));
  assert.throws(() => validateProfilePath(other, alias), /用户数据目录不一致/);
});
