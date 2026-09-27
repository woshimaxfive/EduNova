// Installer tooling only. This file is not included in the installed app.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const REQUIRED = [
  'runtime/python/python.exe',
  'runtime/search-python/python.exe',
  'runtime/node/node.exe',
  'runtime/postgresql/bin/postgres.exe',
  'runtime/redis/redis-server.exe',
  'app/backend/app/desktop_app.py',
  'app/frontend/index.html',
  'app/scripts/desktop_prepare.py',
  'app/scripts/desktop_host_bridge.py',
  'app/scripts/desktop_runtime.py',
  'app/scripts/desktop_worker.py',
  'app/scripts/desktop_search.py',
  'app/vendor/searxng/searx/webapp.py',
  'app/vendor/searxng/searx/version_frozen.py',
  'app/verifier/policy.mjs',
  'app/verifier/runtime/pyodide.mjs',
  'app/verifier/runtime/pyodide.asm.wasm',
  'app/verifier/runtime/python_stdlib.zip',
  'notices/THIRD_PARTY_NOTICES.md',
];

function checkPayload(directory, { localTest = false } = {}) {
  if (!directory || !path.isAbsolute(directory)) {
    throw new Error('EDUNOVA_PAYLOAD_DIR 必须指向独立的安装包资源目录。');
  }
  const root = fs.realpathSync(directory);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'payload-manifest.json'), 'utf8'));
  if (manifest.schemaVersion !== 1 || !Array.isArray(manifest.files) || !manifest.files.length) {
    throw new Error('安装资源清单缺失或格式错误。');
  }
  const expected = new Map();
  for (const item of manifest.files) {
    if (typeof item.path !== 'string' || !/^(app|runtime|models|notices|sources)\//.test(item.path)
      || item.path.split('/').some(part => !part || part === '.' || part === '..')
      || item.path.includes('\\') || item.path.includes(':') || expected.has(item.path)
      || !/^[a-f0-9]{64}$/.test(item.sha256) || !Number.isSafeInteger(item.bytes) || item.bytes < 0) {
      throw new Error('安装资源清单包含无效路径、重复条目或校验值。');
    }
    expected.set(item.path, item);
  }
  const actual = new Set();
  function walk(folder, prefix = '') {
    for (const entry of fs.readdirSync(folder, { withFileTypes: true })) {
      const relative = prefix + entry.name;
      if (entry.isSymbolicLink()) throw new Error(`安装资源不允许符号链接：${relative}`);
      if (entry.isDirectory()) {
        // These are SDK source modules, not the application's writable uploads.
        const sdkUploads = /^runtime\/python\/Lib\/site-packages\/openai\/(resources|types)\/uploads$/.test(relative);
        if (/^(\.git|\.planning|acceptance|__pycache__|node_modules|pgdata)$/i.test(entry.name)
          || (entry.name.toLowerCase() === 'uploads' && !sdkUploads)) {
          throw new Error(`安装资源包含本地工作数据：${relative}`);
        }
        walk(path.join(folder, entry.name), relative + '/');
        continue;
      }
      if (!entry.isFile()) throw new Error(`安装资源不是普通文件：${relative}`);
      if (relative === 'payload-manifest.json') continue;
      if (/^(\.env(?:\..*)?|.*\.(?:log|pyc|pyo|db|sqlite|sqlite3)|pgpass|init-password)$/i.test(entry.name)
        || (relative.startsWith('app/') && /^(?:probe_|desktop_jobs\.|windows_rq_probe_worker\.)/i.test(entry.name))) {
        throw new Error(`安装资源包含配置、测试文件或用户数据：${relative}`);
      }
      const item = expected.get(relative);
      if (!item) throw new Error(`存在未登记的安装资源：${relative}`);
      const bytes = fs.readFileSync(path.join(folder, entry.name));
      if (bytes.length !== item.bytes || crypto.createHash('sha256').update(bytes).digest('hex') !== item.sha256) {
        throw new Error(`安装资源校验失败：${relative}`);
      }
      actual.add(relative);
    }
  }
  walk(root);
  for (const relative of [...expected.keys(), ...REQUIRED]) {
    if (!actual.has(relative)) throw new Error(`缺少安装资源：${relative}`);
  }
  if (manifest.redistributionReviewed !== true && !localTest) {
    throw new Error('随包组件分发材料尚未核对完成，不能生成安装器。');
  }
  return { directory: root, fileCount: actual.size, localTest,
    redistributionReviewed: manifest.redistributionReviewed === true };
}

function builderConfig(payloadDirectory, { localTest = false } = {}) {
  return {
    appId: 'org.edunova.desktop',
    productName: 'EduNova',
    directories: { output: localTest ? 'dist/local-test' : 'dist/release' },
    asar: true,
    npmRebuild: false,
    files: ['main.cjs', 'config.cjs', 'prepare.cjs', 'runtime-bridge.cjs', 'capabilities.cjs',
      'verifier.cjs', 'verifier-preload.cjs', 'verifier-client.mjs', 'verifier-worker.mjs',
      'preload.cjs', 'loading.html', 'package.json'],
    extraResources: [{ from: payloadDirectory, to: 'edunova', filter: ['**/*'] }],
    win: { target: [{ target: 'nsis', arch: ['x64'] }], signAndEditExecutable: true },
    nsis: {
      oneClick: false, perMachine: false, allowElevation: false,
      allowToChangeInstallationDirectory: true,
      createDesktopShortcut: true, createStartMenuShortcut: true,
      deleteAppDataOnUninstall: false, runAfterFinish: false,
      artifactName: localTest ? 'EduNova-LocalTest-Setup-${version}-${arch}.${ext}'
        : 'EduNova-Setup-${version}-${arch}.${ext}',
    },
    beforePack: () => { checkPayload(payloadDirectory, { localTest }); },
  };
}

async function main() {
  const directory = process.env.EDUNOVA_PAYLOAD_DIR;
  const localTest = process.argv.includes('--local-test');
  const result = checkPayload(directory, { localTest });
  if (localTest) console.warn('本地产物仅供安装验收；此选项不代表第三方组件已获分发核对通过。');
  if (process.argv.includes('--check')) {
    console.log(JSON.stringify(result));
    return;
  }
  if (process.platform !== 'win32') throw new Error('当前安装包构建仅支持 Windows。');
  // The bundled Nsis7z extractor cannot decode auto-selected ARM64 filters.
  // Use the existing builder override; do not patch the installed dependency.
  process.env.ELECTRON_BUILDER_7Z_FILTER = 'BCJ';
  const { build, Platform, Arch } = require('electron-builder');
  const targets = Platform.WINDOWS.createTarget(process.argv.includes('--dir') ? 'dir' : 'nsis', Arch.x64);
  await build({ projectDir: __dirname, config: builderConfig(result.directory, { localTest }), targets, publish: 'never' });
}

if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { REQUIRED, checkPayload, builderConfig };
