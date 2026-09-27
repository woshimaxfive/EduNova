const fs = require('node:fs');
const path = require('node:path');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const { readConfig } = require('./config.cjs');

async function prepareInstalled(resourcesPath, dataPath) {
  const payload = path.join(resourcesPath, 'edunova');
  const python = path.join(payload, 'runtime', 'python', 'python.exe');
  const script = path.join(payload, 'app', 'scripts', 'desktop_prepare.py');
  fs.mkdirSync(dataPath, { recursive: true });
  await promisify(execFile)(python, ['-B', '-X', 'utf8', script, 'prepare', '--payload', payload, '--data', dataPath], {
    cwd: dataPath, windowsHide: true, timeout: 30000, maxBuffer: 256 * 1024,
    env: { ...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1' },
  });
  const config = readConfig(path.join(dataPath, 'runtime', 'desktop.json'));
  validateProfilePath(config.userData, dataPath);
  return config;
}
function validateProfilePath(userData, dataPath) {
  // Windows can redirect AppData for packaged launchers. Compare physical
  // directories, while still rejecting a genuinely different profile.
  if (fs.realpathSync.native(userData) !== fs.realpathSync.native(path.join(dataPath, 'profile'))) {
    throw new Error('用户数据目录不一致。');
  }
}
module.exports = { prepareInstalled, validateProfilePath };
