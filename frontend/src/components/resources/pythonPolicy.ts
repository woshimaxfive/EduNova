const allowedImports = new Set([
  "collections",
  "dataclasses",
  "functools",
  "heapq",
  "itertools",
  "math",
  "random",
  "statistics",
  "typing"
]);

const blockedCalls = /\b(?:eval|exec|compile|open|__import__|input|help)\s*\(/;
const blockedInterop = /\b(?:js|pyodide|micropip|urllib|requests|socket|subprocess|pathlib|aiohttp)\b/;

export function preflightPythonCode(code: string): string | null {
  if (blockedCalls.test(code)) {
    return "当前代码包含被禁用的动态执行、输入或文件操作。";
  }
  if (blockedInterop.test(code)) {
    return "当前代码包含被禁用的网络、文件或浏览器互操作模块。";
  }
  for (const line of code.split("\n")) {
    const importMatch = line.trim().match(/^(?:from|import)\s+([a-zA-Z0-9_]+)/);
    if (importMatch && !allowedImports.has(importMatch[1])) {
      return "仅允许导入安全的 Python 标准库模块。";
    }
  }
  return null;
}
