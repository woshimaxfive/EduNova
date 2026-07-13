import http from "node:http";
import { Worker } from "node:worker_threads";

const PORT = Number(process.env.PORT || 8090);
const RUN_TIMEOUT_MS = Number(process.env.CODE_RUN_TIMEOUT_MS || 5000);
const READY_TIMEOUT_MS = Number(process.env.CODE_READY_TIMEOUT_MS || 30000);
const MAX_BODY_BYTES = 100_000;

function json(response, status, payload) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(JSON.stringify(payload));
}

function verify(payload) {
  return new Promise((resolve) => {
    const worker = new Worker(new URL("./runner.mjs", import.meta.url));
    let readyTimer;
    let runTimer;
    let finished = false;
    const finish = (result) => {
      if (finished) return;
      finished = true;
      clearTimeout(readyTimer);
      clearTimeout(runTimer);
      worker.terminate();
      resolve(result);
    };
    readyTimer = setTimeout(() => finish({ ok: false, code: "runtime_unavailable", message: "代码运行环境启动超时。" }), READY_TIMEOUT_MS);
    worker.on("message", (message) => {
      if (message?.type === "ready") {
        clearTimeout(readyTimer);
        worker.postMessage(payload);
        runTimer = setTimeout(() => finish({ ok: false, code: "timeout", message: "代码运行超过 5 秒限制。" }), RUN_TIMEOUT_MS);
        return;
      }
      if (message?.type === "result") finish(message);
    });
    worker.on("error", () => finish({ ok: false, code: "runtime_error", message: "代码验证服务运行失败。" }));
    worker.on("exit", (code) => {
      if (!finished && code !== 0) finish({ ok: false, code: "runtime_error", message: "代码验证进程异常结束。" });
    });
  });
}

http.createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    json(response, 200, { ok: true });
    return;
  }
  if (request.method !== "POST" || request.url !== "/verify") {
    json(response, 404, { ok: false, code: "not_found" });
    return;
  }
  let body = "";
  for await (const chunk of request) {
    body += chunk;
    if (Buffer.byteLength(body) > MAX_BODY_BYTES) {
      json(response, 413, { ok: false, code: "payload_too_large", message: "代码验证请求过大。" });
      return;
    }
  }
  try {
    const payload = JSON.parse(body);
    if (typeof payload.code !== "string" || typeof payload.expectedOutput !== "string" || !payload.code.trim()) {
      json(response, 400, { ok: false, code: "invalid_request", message: "代码或预期输出无效。" });
      return;
    }
    json(response, 200, await verify({ code: payload.code, expectedOutput: payload.expectedOutput }));
  } catch {
    json(response, 400, { ok: false, code: "invalid_request", message: "代码验证请求格式无效。" });
  }
}).listen(PORT, "0.0.0.0");
