import { loadPyodide } from '/runtime/pyodide.mjs';
import { MAX_OUTPUT_LENGTH, normalizeOutput, policyScript } from '/policy.mjs';

const runtime = loadPyodide({ indexURL: self.location.origin + '/runtime/' });
runtime.then(() => self.postMessage({ type: 'ready' })).catch(() => {
  self.postMessage({ type: 'result', ok: false, code: 'runtime_error', message: '代码运行环境启动失败。' });
});
self.onmessage = async ({ data: { code, expectedOutput } }) => {
  let stdout = '', stderr = '';
  const result = value => self.postMessage({ type: 'result', ...value });
  try {
    const pyodide = await runtime;
    pyodide.setStdout({ batched: value => { stdout = `${stdout}${value}\n`.slice(0, MAX_OUTPUT_LENGTH + 1); } });
    pyodide.setStderr({ batched: value => { stderr = `${stderr}${value}\n`.slice(0, MAX_OUTPUT_LENGTH + 1); } });
    pyodide.globals.set('user_code', code);
    const violation = String(pyodide.runPython(policyScript) ?? '');
    if (violation) { result({ ok: false, code: 'policy_rejected', message: violation }); return; }
    await pyodide.runPythonAsync(code);
    if (stdout.length > MAX_OUTPUT_LENGTH || stderr.length > MAX_OUTPUT_LENGTH) {
      result({ ok: false, code: 'output_too_large', message: '代码输出超过 20KB 限制。' }); return;
    }
    if (normalizeOutput(stderr)) { result({ ok: false, code: 'runtime_error', message: '代码运行产生错误输出。' }); return; }
    const actual = normalizeOutput(stdout), expected = normalizeOutput(expectedOutput);
    if (!expected || actual !== expected) {
      result({ ok: false, code: 'output_mismatch', message: '实际输出与预期输出不一致。' }); return;
    }
    result({ ok: true, code: 'passed', outputLength: actual.length });
  } catch { result({ ok: false, code: 'runtime_error', message: '代码运行失败。' }); }
};
