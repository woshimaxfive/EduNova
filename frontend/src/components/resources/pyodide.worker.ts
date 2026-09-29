/// <reference lib="webworker" />

import { type PyodideInterface } from "pyodide";
import pyodidePackage from "pyodide/package.json";

type RunMessage = {
  type: "run";
  code: string;
};

type WorkerResponse =
  | { type: "ready" }
  | { type: "stdout"; value: string }
  | { type: "result"; value: string }
  | { type: "error"; value: string };

const workerScope = self as DedicatedWorkerGlobalScope;
const MAX_OUTPUT_LENGTH = 20_000;
let pyodidePromise: Promise<PyodideInterface> | null = null;
const runtimeDiagnostics: string[] = [];

type PyodideLoaderModule = {
  loadPyodide: (options: {
    indexURL: string;
    stdLibURL: string;
    stdout: (message: string) => void;
    stderr: (message: string) => void;
  }) => Promise<PyodideInterface>;
};

function post(message: WorkerResponse) {
  workerScope.postMessage(message);
}

function readableError(error: unknown) {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }
  const text = String(error);
  return text && text !== "[object Object]" ? text : "Python 运行失败。";
}

function loadRuntime() {
  if (!pyodidePromise) {
    const indexURL = `${workerScope.location.origin}/pyodide/${pyodidePackage.version}/`;
    pyodidePromise = import(/* @vite-ignore */ `${indexURL}pyodide.mjs`)
      .then((module: PyodideLoaderModule) => module.loadPyodide({
        indexURL,
        stdLibURL: `${indexURL}python_stdlib.zip?runtime=${pyodidePackage.version}`,
        stdout: (message) => runtimeDiagnostics.push(message.slice(0, 1000)),
        stderr: (message) => runtimeDiagnostics.push(message.slice(0, 1000))
      }));
  }
  return pyodidePromise;
}

const policyScript = String.raw`
import ast

ALLOWED_IMPORTS = {
    "collections", "dataclasses", "functools", "heapq", "itertools",
    "math", "random", "statistics", "typing"
}
BLOCKED_CALLS = {"eval", "exec", "compile", "open", "__import__", "input", "help"}

tree = ast.parse(user_code)
violations = []
for node in ast.walk(tree):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        names = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
        if any(name not in ALLOWED_IMPORTS for name in names):
            violations.append("仅允许导入安全的 Python 标准库模块。")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
        violations.append("当前代码包含被禁用的动态执行或文件操作。")
    if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
        violations.append("当前代码包含被禁用的底层属性访问。")

"\n".join(dict.fromkeys(violations))
`;

workerScope.onmessage = async (event: MessageEvent<RunMessage>) => {
  if (event.data.type !== "run") {
    return;
  }
  try {
    const pyodide = await loadRuntime();
    post({ type: "ready" });
    let output = "";
    pyodide.setStdout({
      batched: (value) => {
        output = `${output}${value}\n`.slice(0, MAX_OUTPUT_LENGTH);
        post({ type: "stdout", value: output });
      }
    });
    pyodide.setStderr({
      batched: (value) => {
        output = `${output}${value}\n`.slice(0, MAX_OUTPUT_LENGTH);
        post({ type: "stdout", value: output });
      }
    });
    pyodide.globals.set("user_code", event.data.code);
    const policyResult = String(pyodide.runPython(policyScript) ?? "");
    if (policyResult) {
      post({ type: "error", value: policyResult });
      return;
    }
    await pyodide.runPythonAsync(event.data.code);
    post({ type: "result", value: output || "代码运行完成，没有标准输出。" });
  } catch (error) {
    const diagnostics = runtimeDiagnostics.slice(-4).join("\n");
    post({ type: "error", value: [readableError(error), diagnostics].filter(Boolean).join("\n") });
  }
};

export {};
