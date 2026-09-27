const fs = require('node:fs');
const path = require('node:path');
function readConfig(filename) {
  if (!filename || !path.isAbsolute(filename)) throw new Error('需要绝对路径的桌面配置文件。');
  const config = JSON.parse(fs.readFileSync(filename, 'utf8'));
  if (config.startTimeoutSeconds !== undefined && (!Number.isInteger(config.startTimeoutSeconds)
    || config.startTimeoutSeconds < 30 || config.startTimeoutSeconds > 300)) throw new Error('Invalid startup timeout');
  for (const key of ['python', 'bridge', 'manifest', 'userData']) {
    if (typeof config[key] !== 'string' || !path.isAbsolute(config[key])) throw new Error(`Invalid ${key}`);
    if (key !== 'userData' && !fs.statSync(config[key]).isFile()) throw new Error(`Missing ${key}`);
  }
  const url = new URL(config.url);
  if (config.verifier && (!Number.isInteger(config.verifier.port) || config.verifier.port < 1024
    || config.verifier.port > 65535 || !path.isAbsolute(config.verifier.assets)
    || !fs.statSync(config.verifier.assets).isDirectory())) throw new Error('Invalid code verifier configuration');
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.username || url.password) throw new Error('URL must be explicit loopback HTTP');
  const manifest = JSON.parse(fs.readFileSync(config.manifest, 'utf8'));
  if (!manifest.services?.some(service => service.health_url && new URL(service.health_url).origin === url.origin)) throw new Error('Window origin must belong to a managed service');
  fs.mkdirSync(config.userData, { recursive: true });
  return { ...config, url: url.href, origin: url.origin };
}
function trustedSender(event, window, origin) {
  if (!window || window.isDestroyed() || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame) return false;
  try { return new URL(event.senderFrame.url).origin === origin; } catch { return false; }
}
module.exports = { readConfig, trustedSender };
