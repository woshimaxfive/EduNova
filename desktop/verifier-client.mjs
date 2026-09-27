const worker = new Worker('/worker.mjs', { type: 'module' });
window.codeJob.receive(payload => worker.postMessage(payload));
worker.onmessage = ({ data }) => {
  if (data.type === 'ready') window.codeJob.ready();
  else if (data.type === 'result') { worker.terminate(); window.codeJob.result(data); }
};
worker.onerror = () => window.codeJob.result({ ok: false, code: 'runtime_error', message: '代码运行环境异常。' });
