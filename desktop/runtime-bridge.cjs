const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');

class RuntimeBridge {
  constructor(config) {
    this.pending = new Map();
    this.sequence = 0;
    this.waitSeconds = config.startTimeoutSeconds || 90;
    this.child = spawn(config.python, ['-B', '-X', 'utf8', config.bridge, '--manifest', config.manifest, '--wait-seconds', String(this.waitSeconds)], {
      cwd: require('node:path').dirname(config.manifest), windowsHide: true, stdio: ['pipe', 'pipe', 'pipe']
    });
    // Raw diagnostics may contain host paths. Do not expose them to renderer.
    this.child.stderr.on('data', () => {});
    this.lines = createInterface({ input: this.child.stdout });
    this.lines.on('line', (line) => {
      let message;
      try { message = JSON.parse(line); } catch { return; }
      const item = this.pending.get(message.id);
      if (!item) return;
      this.pending.delete(message.id); clearTimeout(item.timer);
      if (message.ok) item.resolve(message.result);
      else item.reject(new Error('后台服务操作失败，请检查本地运行记录。'));
    });
    this.closed = new Promise(resolve => {
      this.child.once('exit', resolve);
      this.child.once('error', resolve);
    });
    const fail = () => {
      for (const item of this.pending.values()) {
        clearTimeout(item.timer); item.reject(new Error('后台连接已断开。'));
      }
      this.pending.clear();
    };
    this.child.on('exit', fail); this.child.on('error', fail);
    this.child.stdin.on('error', fail);
  }
  request(method) {
    if (!['start', 'status', 'stop'].includes(method)) return Promise.reject(new Error('Unsupported method'));
    if (this.child.exitCode !== null || this.child.stdin.destroyed) return Promise.reject(new Error('后台连接已断开。'));
    const id = String(++this.sequence);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error('后台服务响应超时。')); }, (this.waitSeconds + 10) * 1000);
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(JSON.stringify({ id, method }) + '\n');
    });
  }
  async close() {
    // EOF asks our Python bridge to close only its own controller. If it is
    // stuck, killing the owned bridge closes its controller's host pipe.
    this.child.stdin.end();
    const timer = setTimeout(() => this.child.kill(), 95000);
    try { await this.closed; } finally { clearTimeout(timer); this.lines.close(); }
  }
}
module.exports = { RuntimeBridge };
