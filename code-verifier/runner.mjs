import { parentPort } from "node:worker_threads";
import { loadPyodide } from "pyodide";
import { MAX_OUTPUT_LENGTH, normalizeOutput, policyScript } from "./policy.mjs";

const pyodide = await loadPyodide();
parentPort.postMessage({ type: "ready" });

parentPort.on("message", async ({ code, expectedOutput }) => {
  let stdout = "";
  let stderr = "";
  try {
    pyodide.setStdout({ batched: (value) => { stdout = `${stdout}${value}\n`.slice(0, MAX_OUTPUT_LENGTH + 1); } });
    pyodide.setStderr({ batched: (value) => { stderr = `${stderr}${value}\n`.slice(0, MAX_OUTPUT_LENGTH + 1); } });
    pyodide.globals.set("user_code", code);
    const policyResult = String(pyodide.runPython(policyScript) ?? "");
    if (policyResult) {
      parentPort.postMessage({ type: "result", ok: false, code: "policy_rejected", message: policyResult });
      return;
    }
    await pyodide.runPythonAsync(code);
    if (stdout.length > MAX_OUTPUT_LENGTH || stderr.length > MAX_OUTPUT_LENGTH) {
      parentPort.postMessage({ type: "result", ok: false, code: "output_too_large", message: "代码输出超过 20KB 限制。" });
      return;
    }
    if (normalizeOutput(stderr)) {
      parentPort.postMessage({ type: "result", ok: false, code: "runtime_error", message: "代码运行产生错误输出。" });
      return;
    }
    const actual = normalizeOutput(stdout);
    const expected = normalizeOutput(expectedOutput);
    if (!expected || actual !== expected) {
      parentPort.postMessage({ type: "result", ok: false, code: "output_mismatch", message: "实际输出与预期输出不一致。" });
      return;
    }
    parentPort.postMessage({ type: "result", ok: true, code: "passed", outputLength: actual.length });
  } catch {
    parentPort.postMessage({ type: "result", ok: false, code: "runtime_error", message: "代码运行失败。" });
  }
});
