// The existing HTTP grading contract, executed in fresh sandboxed Chromium jobs.
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { BrowserWindow, ipcMain, session } = require('electron');

const RUNTIME_FILES = ['pyodide.mjs', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];
const RESULT_CODES = new Set(['passed', 'policy_rejected', 'output_too_large', 'runtime_error', 'output_mismatch']);
const failure = (code, message) => ({ ok: false, code, message });

async function startVerifier(config) {
  const origin = `http://127.0.0.1:${config.port}`;
  const jobs = new Set();
  let closed = false;
  const files = new Map([
    ['/client.mjs', path.join(__dirname, 'verifier-client.mjs')],
    ['/worker.mjs', path.join(__dirname, 'verifier-worker.mjs')],
    ['/policy.mjs', path.join(config.assets, 'policy.mjs')],
    ...RUNTIME_FILES.map(name => ['/runtime/' + name, path.join(config.assets, 'runtime', name)]),
  ]);
  for (const filename of files.values()) await fs.access(filename);
  function verify(payload) {
    return new Promise(resolve => {
      const profile = session.fromPartition('edunova-code-' + crypto.randomUUID(), { cache: false });
      profile.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
      profile.setPermissionCheckHandler(() => false);
      profile.on('will-download', event => event.preventDefault());
      profile.webRequest.onBeforeRequest((request, callback) => {
        let allowed = false;
        try {
          const url = new URL(request.url);
          allowed = request.method === 'GET' && url.origin === origin && !url.search
            && (url.pathname === '/' || files.has(url.pathname));
        } catch {}
        callback({ cancel: !allowed });
      });
      const window = new BrowserWindow({ show: false, webPreferences: {
        session: profile, preload: path.join(__dirname, 'verifier-preload.cjs'),
        sandbox: true, contextIsolation: true, webSecurity: true, webviewTag: false,
        nodeIntegration: false, nodeIntegrationInSubFrames: false, nodeIntegrationInWorker: false,
        backgroundThrottling: false, spellcheck: false,
      } });
      window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
      window.webContents.on('will-navigate', event => event.preventDefault());
      window.webContents.on('will-redirect', event => event.preventDefault());
      window.webContents.on('will-attach-webview', event => event.preventDefault());
      let finished = false, ready = false;
      let timer = setTimeout(() => finish(failure('runtime_unavailable', '代码运行环境启动超时。')), 30000);
      const owned = event => !window.isDestroyed() && event.sender === window.webContents
        && event.senderFrame === window.webContents.mainFrame && event.senderFrame.url === origin + '/';
      function finish(result) {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        ipcMain.removeListener('edunova:verify-ready', onReady);
        ipcMain.removeListener('edunova:verify-result', onResult);
        jobs.delete(cancel);
        if (!window.isDestroyed()) window.destroy();
        profile.clearStorageData().catch(() => {});
        resolve(result);
      }
      function cancel() { finish(failure('runtime_unavailable', '代码验证服务已关闭。')); }
      function onReady(event) {
        if (!owned(event) || ready) return;
        ready = true;
        clearTimeout(timer);
        timer = setTimeout(() => finish(failure('timeout', '代码运行超过 5 秒限制。')), 5000);
        window.webContents.send('edunova:verify-job', payload);
      }
      function onResult(event, result) {
        if (!owned(event) || !result || !RESULT_CODES.has(result.code)) return;
        const outputLength = Number.isInteger(result.outputLength) && result.outputLength >= 0
          && result.outputLength <= 20001 ? result.outputLength : 0;
        finish({ ok: ready && result.ok === true && result.code === 'passed', code: result.code,
          outputLength, message: typeof result.message === 'string' ? result.message.slice(0, 200) : '代码验证已完成。' });
      }
      jobs.add(cancel);
      ipcMain.on('edunova:verify-ready', onReady);
      ipcMain.on('edunova:verify-result', onResult);
      window.webContents.once('render-process-gone', () => finish(failure('runtime_error', '代码验证进程异常结束。')));
      window.once('closed', () => finish(failure('runtime_error', '代码验证窗口已关闭。')));
      window.loadURL(origin + '/').catch(() => finish(failure('runtime_unavailable', '代码运行资源无法加载。')));
    });
  }
  function json(response, status, result) {
    response.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    response.end(JSON.stringify(result));
  }
  const server = http.createServer(async (request, response) => {
    try {
      if (closed || request.headers.host !== `127.0.0.1:${config.port}`) {
        json(response, 403, failure('forbidden', '无效请求来源。')); return;
      }
      if (request.method === 'GET' && request.url === '/health') { json(response, 200, { ok: true }); return; }
      if (request.method === 'POST' && request.url === '/verify') {
        if (request.headers.origin || request.headers['sec-fetch-site']) {
          json(response, 403, failure('forbidden', '不接受浏览器发起的验证请求。')); return;
        }
        if (jobs.size >= 2) { json(response, 429, failure('busy', '代码验证繁忙，请稍后重试。')); return; }
        let bytes = 0;
        const chunks = [];
        for await (const chunk of request) {
          bytes += chunk.length;
          if (bytes > 100000) { json(response, 413, failure('payload_too_large', '代码验证请求过大。')); return; }
          chunks.push(chunk);
        }
        const payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        if (typeof payload.code !== 'string' || !payload.code.trim() || typeof payload.expectedOutput !== 'string') {
          json(response, 400, failure('invalid_request', '代码或预期输出无效。')); return;
        }
        // Recheck after awaiting the body: requests may arrive concurrently.
        if (closed || jobs.size >= 2) { json(response, 429, failure('busy', '代码验证繁忙。')); return; }
        json(response, 200, await verify({ code: payload.code, expectedOutput: payload.expectedOutput }));
        return;
      }
      if (request.method !== 'GET' || (request.url !== '/' && !files.has(request.url))) {
        json(response, 404, failure('not_found', '资源不存在。')); return;
      }
      const body = request.url === '/'
        ? Buffer.from('<!doctype html><meta charset="utf-8"><title>EduNova code worker</title><script type="module" src="/client.mjs"></script>')
        : await fs.readFile(files.get(request.url));
      const type = request.url === '/' ? 'text/html' : /\.m?js$/.test(request.url) ? 'text/javascript'
        : request.url.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream';
      const connect = ['pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'].map(name => origin + '/runtime/' + name).join(' ');
      response.writeHead(200, { 'content-type': type, 'content-length': body.length,
        'x-content-type-options': 'nosniff', 'cache-control': 'no-store',
        'content-security-policy': `default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src ${connect}; worker-src ${request.url === '/worker.mjs' ? "'none'" : "'self'"}; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`,
      });
      response.end(body);
    } catch {
      if (!response.headersSent) json(response, 400, failure('invalid_request', '代码验证请求无效。'));
      else response.end();
    }
  });
  server.requestTimeout = 10000;
  server.headersTimeout = 10000;
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(config.port, '127.0.0.1', resolve); });
  return { async close() {
    closed = true;
    for (const cancel of [...jobs]) cancel();
    await new Promise(resolve => { server.close(resolve); server.closeAllConnections(); });
  } };
}
module.exports = { startVerifier };
