const { app, BrowserWindow, ipcMain, dialog, session } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { readConfig, trustedSender } = require('./config.cjs');
const { RuntimeBridge } = require('./runtime-bridge.cjs');
const { installCapabilities } = require('./capabilities.cjs');
const { prepareInstalled } = require('./prepare.cjs');
const { startVerifier } = require('./verifier.cjs');

app.enableSandbox();
let window, bridge, verifier, quitting = false, stopped = false;
let config, installedData;
try {
  if (process.env.EDUNOVA_DESKTOP_CONFIG) config = readConfig(process.env.EDUNOVA_DESKTOP_CONFIG);
  else if (app.isPackaged) {
    installedData = path.join(app.getPath('appData'), 'EduNova');
    config = { userData: path.join(installedData, 'profile') };
    require('node:fs').mkdirSync(config.userData, { recursive: true });
  } else throw new Error('Missing development configuration');
  app.setPath('userData', config.userData);
} catch {
  app.whenReady().then(() => {
    dialog.showErrorBox('EduNova 无法启动', '桌面运行配置缺失或无效，请检查本地配置文件。');
    app.exit(2);
  });
}
if (config && !app.requestSingleInstanceLock()) app.exit(0);
else if (config) {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } });
  app.on('before-quit', event => {
    if (stopped) return;
    event.preventDefault();
    if (quitting) return;
    quitting = true;
    if (window && !window.isDestroyed()) window.setTitle('EduNova · 正在关闭后台服务');
    Promise.resolve(bridge?.close()).finally(async () => {
      await verifier?.close();
      stopped = true; app.quit();
    });
  });
  app.on('window-all-closed', () => app.quit());
  app.whenReady().then(async () => {
    const partition = 'persist:edunova-desktop';
    const profile = session.fromPartition(partition);
    const loading = pathToFileURL(path.join(__dirname, 'loading.html')).href;
    profile.webRequest.onBeforeRequest((details, callback) => {
      let allowed = details.url === loading;
      try { allowed ||= new URL(details.url).origin === config.origin || ['data:', 'blob:'].includes(new URL(details.url).protocol); } catch {}
      callback({ cancel: !allowed });
    });
    window = new BrowserWindow({
      title: 'EduNova', width: 1360, height: 900, minWidth: 900, minHeight: 650,
      backgroundColor: '#f7f8fa', autoHideMenuBar: true,
      webPreferences: { preload: path.join(__dirname, 'preload.cjs'), partition,
        nodeIntegration: false, nodeIntegrationInSubFrames: false, nodeIntegrationInWorker: false,
        contextIsolation: true, sandbox: true, webSecurity: true, webviewTag: false }
    });
    window.removeMenu();
    window.on('closed', () => app.quit());
    profile.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
    const navigation = (event, url) => {
      try { if (new URL(url).origin === config.origin) return; } catch {}
      event.preventDefault();
    };
    window.webContents.on('will-navigate', navigation);
    window.webContents.on('will-redirect', navigation);
    window.webContents.on('will-attach-webview', event => event.preventDefault());
    window.webContents.on('render-process-gone', () => app.quit());
    for (const [channel, handler] of [
      ['edunova:status', () => bridge.request('status')],
      ['edunova:quit', () => { setImmediate(() => app.quit()); return { closing: true }; }]
    ]) ipcMain.handle(channel, (event, ...args) => {
      if (!trustedSender(event, window, config.origin) || args.length) throw new Error('不允许的桌面请求。');
      return handler();
    });
    await window.loadFile(path.join(__dirname, 'loading.html'));
    try {
      if (installedData) config = await prepareInstalled(process.resourcesPath, installedData);
      if (quitting || window.isDestroyed()) return;
      installCapabilities(profile, window, config.origin, dialog);
      if (config.verifier) verifier = await startVerifier(config.verifier);
      if (quitting) { await verifier?.close(); return; }
      bridge = new RuntimeBridge(config);
      await bridge.request('start');
      if (!quitting && !window.isDestroyed()) await window.loadURL(config.url);
    } catch {
      if (!quitting && !window.isDestroyed()) {
        window.setTitle('EduNova · 启动失败');
        await dialog.showMessageBox(window, { type: 'error', title: 'EduNova 启动失败', message: '后台服务未能启动。', detail: '请检查本地运行记录，然后重新打开应用。', buttons: ['关闭'] });
      }
      app.quit();
    }
  }).catch(() => app.quit());
}
