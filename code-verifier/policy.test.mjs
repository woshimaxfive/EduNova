import assert from "node:assert/strict";
import test from "node:test";
import { Worker } from "node:worker_threads";

// Exercise the real Pyodide runner. Each case gets a fresh interpreter just
// like production. These are policy regressions, not OS sandbox acceptance.
function run(code, expectedOutput) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./runner.mjs", import.meta.url));
    let finished = false;
    const finish = async (error, result) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      await worker.terminate();
      if (error) reject(error);
      else resolve(result);
    };
    const timer = setTimeout(() => finish(new Error("Runner test exceeded 40 seconds")), 40_000);
    worker.on("error", (error) => finish(error));
    worker.on("exit", (code) => {
      if (!finished) finish(new Error(`Runner exited without a result: ${code}`));
    });
    worker.on("message", (message) => {
      if (message.type === "ready") worker.postMessage({ code, expectedOutput });
      if (message.type === "result") finish(null, message);
    });
  });
}

const cases = [
  ["ordinary arithmetic", "print(6 * 7)", "42", "passed"],
  ["allowed import and alias", "from collections import deque as Queue\nq = Queue([1, 2])\nprint(q.popleft())", "1", "passed"],
  ["ordinary class constructor", "class Stack:\n    def __init__(self):\n        self.items = [3]\ns = Stack()\nprint(s.items.pop())", "3", "passed"],
  ["wrong expected output", "print(2)", "3", "output_mismatch"],
  ["direct forbidden call", "eval('6 * 7')", "42", "policy_rejected"],
  ["aliased eval", "runner = eval\nprint(runner('6 * 7'))", "42", "policy_rejected"],
  ["forbidden callable in a container", "runners = [eval]\nprint(runners[0]('6 * 7'))", "42", "policy_rejected"],
  ["forbidden callable as argument", "print(list(map(eval, ['6 * 7']))[0])", "42", "policy_rejected"],
  ["builtins dictionary alias regression", "v = vars\nb = v(__builtins__)\nf = b['ev' + 'al']\nprint(f('6 * 7'))", "42", "policy_rejected"],
  ["dunder name reference", "b = __builtins__\nprint(42)", "42", "policy_rejected"],
  ["forbidden import", "import os\nprint(42)", "42", "policy_rejected"],
];

for (const [name, code, expectedOutput, expectedCode] of cases) {
  test(name, { timeout: 45_000 }, async () => {
    const result = await run(code, expectedOutput);
    assert.equal(result.code, expectedCode, JSON.stringify(result));
    assert.equal(result.ok, expectedCode === "passed");
  });
}
