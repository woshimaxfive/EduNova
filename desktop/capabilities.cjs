const path = require('node:path');
const { trustedSender } = require('./config.cjs');

function sameOrigin(url, origin) {
  try { return new URL(url).origin === origin; } catch { return false; }
}

function trustedMedia(contents, permission, details, window, origin, check = false) {
  if (!window || window.isDestroyed() || contents !== window.webContents ||
      permission !== 'media' || details?.isMainFrame !== true ||
      !sameOrigin(contents.getURL(), origin) || !sameOrigin(details.requestingUrl, origin)) return false;
  if (details.securityOrigin && !sameOrigin(details.securityOrigin, origin)) return false;
  return check ? details.mediaType === 'audio' :
    Array.isArray(details.mediaTypes) && details.mediaTypes.length === 1 && details.mediaTypes[0] === 'audio';
}

const exportTypes = new Map([
  ['.json', 'JSON'], ['.md', 'Markdown'], ['.pdf', 'PDF'], ['.docx', 'Word'], ['.pptx', 'PowerPoint']
]);

function exportOptions(item, contents, frame, window, origin) {
  if (!trustedSender({ sender: contents, senderFrame: frame }, window, origin) ||
      !sameOrigin(item.getInitiatorOrigin(), origin)) return null;
  const urls = item.getURLChain();
  if (!urls.length || !urls.every(raw => {
    try {
      const url = new URL(raw);
      return url.origin === origin && (url.protocol === 'blob:' ||
        (url.protocol === 'http:' && /^\/api\/v1\/exports\/\d+\/download$/.test(url.pathname)));
    } catch { return false; }
  })) return null;
  // A page may suggest a basename, never a filesystem path or executable type.
  const filename = item.getFilename();
  const extension = path.extname(filename).toLowerCase();
  if (!exportTypes.has(extension) || filename.length > 180 ||
      /[<>:"/\\|?*\x00-\x1f\x7f]/.test(filename) ||
      [...filename].some(char => { const n = char.codePointAt(0); return (n >= 0x202a && n <= 0x202e) || (n >= 0x2066 && n <= 0x2069); }) ||
      /[. ]$/.test(filename) || /^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)/i.test(filename)) return null;
  return { title: '保存 EduNova 导出文件', defaultPath: filename,
    buttonLabel: '保存', filters: [{ name: exportTypes.get(extension), extensions: [extension.slice(1)] }],
    properties: ['showOverwriteConfirmation'] };
}

function installCapabilities(profile, window, origin, dialog) {
  let microphoneGranted = false, prompting = false, documentVersion = 0;
  window.webContents.on('did-start-navigation', (_event, _url, inPlace, mainFrame) => {
    if (mainFrame && !inPlace) { microphoneGranted = false; documentVersion += 1; }
  });
  profile.setPermissionCheckHandler((contents, permission, requestingOrigin, details) =>
    microphoneGranted && sameOrigin(requestingOrigin, origin) &&
    trustedMedia(contents, permission, details, window, origin, true));
  profile.setPermissionRequestHandler(async (contents, permission, callback, details) => {
    if (!trustedMedia(contents, permission, details, window, origin) || prompting) return callback(false);
    if (microphoneGranted) return callback(true);
    prompting = true;
    const version = documentVersion;
    try {
      const answer = await dialog.showMessageBox(window, { type: 'question', title: '麦克风权限',
        message: '允许 EduNova 使用麦克风进行语音输入吗？',
        detail: '点击语音输入后开始录音。本次页面打开期间有效，重新打开后会再次询问。',
        buttons: ['暂不允许', '允许'], defaultId: 0, cancelId: 0, noLink: true });
      microphoneGranted = answer.response === 1 && version === documentVersion &&
        trustedMedia(contents, permission, details, window, origin);
      callback(microphoneGranted);
    } catch { callback(false); }
    finally { prompting = false; }
  });
  profile.on('will-download', (event, item, contents, frame) => {
    let options;
    try { options = exportOptions(item, contents, frame, window, origin); } catch {}
    if (!options) return event.preventDefault();
    // No setSavePath: Electron owns the native save dialog and overwrite prompt.
    item.setSaveDialogOptions(options);
    item.once('done', (_event, state) => {
      if (state === 'interrupted' && !window.isDestroyed()) {
        void dialog.showMessageBox(window, { type: 'error', title: '导出未完成',
          message: '文件未能保存，请检查保存位置后重新导出。', buttons: ['知道了'] }).catch(() => {});
      }
    });
  });
}

module.exports = { trustedMedia, exportOptions, installCapabilities };
