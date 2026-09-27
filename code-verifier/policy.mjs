export const MAX_OUTPUT_LENGTH = 20_000;

export const policyScript = String.raw`
import ast

ALLOWED_IMPORTS = {
    "collections", "dataclasses", "functools", "heapq", "itertools",
    "math", "random", "statistics", "typing"
}
BLOCKED_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "input", "help",
    "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir"
}

tree = ast.parse(user_code)
violations = []
for node in ast.walk(tree):
    # Reject references too: checking only Call nodes allows aliases such as
    # runner = eval or mapping = vars to bypass the direct-call restriction.
    if isinstance(node, ast.Name) and (node.id in BLOCKED_CALLS or node.id.startswith("__")):
        violations.append("当前代码包含被禁用的内置能力引用。")
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        names = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
        if any(name not in ALLOWED_IMPORTS for name in names):
            violations.append("仅允许导入安全的 Python 标准库模块。")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
        violations.append("当前代码包含被禁用的动态执行或文件操作。")
    if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
        violations.append("当前代码包含被禁用的底层属性访问。")
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("__"):
        violations.append("当前代码包含被禁用的底层属性名称。")

"\n".join(dict.fromkeys(violations))
`;

export function normalizeOutput(value) {
  return String(value ?? "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.replace(/\s+$/g, ""))
    .join("\n")
    .trim();
}
