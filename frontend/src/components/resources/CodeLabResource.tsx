import { ArrowCounterClockwise, Play, Stop } from "@phosphor-icons/react";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { useEffect, useMemo, useRef, useState } from "react";

import { type ResourceCodeArtifact } from "../../api/resources";
import { preflightPythonCode } from "./pythonPolicy";

type WorkerMessage = {
  type: "ready" | "stdout" | "result" | "error";
  value?: string;
};

const RUNTIME_LOAD_TIMEOUT_MS = 30_000;
const CODE_EXECUTION_TIMEOUT_MS = 5_000;

export function CodeLabResource({ artifact }: { artifact: ResourceCodeArtifact }) {
  const entryFile = useMemo(
    () => artifact.files.find((item) => item.path === artifact.entry_file) ?? artifact.files[0],
    [artifact.entry_file, artifact.files]
  );
  const [code, setCode] = useState(entryFile?.content ?? "");
  const [output, setOutput] = useState("点击运行，在浏览器隔离环境中查看输出。\n首次运行需要加载 Python 运行时。");
  const [status, setStatus] = useState<"idle" | "loading" | "running" | "completed" | "failed">("idle");
  const workerRef = useRef<Worker | null>(null);
  const timeoutRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      workerRef.current?.terminate();
    },
    []
  );

  function clearTimer() {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }

  function stopWorker(nextStatus: "idle" | "failed" = "idle") {
    clearTimer();
    workerRef.current?.terminate();
    workerRef.current = null;
    setStatus(nextStatus);
  }

  function runCode() {
    const policyError = preflightPythonCode(code);
    if (policyError) {
      setOutput(policyError);
      setStatus("failed");
      return;
    }
    if (typeof Worker === "undefined") {
      setOutput("当前浏览器不支持 Web Worker，无法运行代码。")
      setStatus("failed");
      return;
    }
    stopWorker();
    setOutput("正在加载 Python 运行时...");
    setStatus("loading");
    const worker = new Worker(new URL("./pyodide.worker.ts", import.meta.url), { type: "module" });
    workerRef.current = worker;
    worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
      const message = event.data;
      if (message.type === "ready") {
        clearTimer();
        setStatus("running");
        setOutput("正在运行...");
        timeoutRef.current = window.setTimeout(() => {
          stopWorker("failed");
          setOutput("运行超过 5 秒，已停止本次代码。");
        }, CODE_EXECUTION_TIMEOUT_MS);
        return;
      }
      if (message.type === "stdout") {
        setOutput(message.value ?? "");
        return;
      }
      if (message.type === "result") {
        clearTimer();
        setOutput(message.value ?? "代码运行完成。")
        setStatus("completed");
        worker.terminate();
        workerRef.current = null;
        return;
      }
      clearTimer();
      setOutput(message.value ?? "Python 运行失败。")
      setStatus("failed");
      worker.terminate();
      workerRef.current = null;
    };
    worker.onerror = () => {
      clearTimer();
      setOutput("Python 运行环境加载失败，请稍后重试。")
      setStatus("failed");
      worker.terminate();
      workerRef.current = null;
    };
    timeoutRef.current = window.setTimeout(() => {
      stopWorker("failed");
      setOutput("Python 运行环境加载超时，请检查网络后重试。");
    }, RUNTIME_LOAD_TIMEOUT_MS);
    worker.postMessage({ type: "run", code });
  }

  return (
    <div className="resource-code-shell">
      <div className="resource-code-toolbar">
        <div>
          <strong>{entryFile?.path ?? "study_case.py"}</strong>
          <span>Python · 浏览器隔离运行</span>
        </div>
        <div>
          <button type="button" aria-label="重置代码" title="重置" onClick={() => setCode(entryFile?.content ?? "")}>
            <ArrowCounterClockwise size={17} aria-hidden="true" />
          </button>
          {status === "loading" || status === "running" ? (
            <button type="button" aria-label="停止运行代码" title="停止" onClick={() => stopWorker()}>
              <Stop size={17} weight="fill" aria-hidden="true" />
            </button>
          ) : (
            <button className="primary-action" type="button" aria-label="运行 Python 代码" onClick={runCode}>
              <Play size={17} weight="fill" aria-hidden="true" />
              <span>运行</span>
            </button>
          )}
        </div>
      </div>
      <CodeMirror
        aria-label="Python 代码编辑器"
        value={code}
        minHeight="300px"
        extensions={[python()]}
        onChange={setCode}
        basicSetup={{ foldGutter: false, highlightActiveLine: true, lineNumbers: true }}
      />
      <div className={`resource-code-output ${status}`} aria-live="polite">
        <div>
          <strong>运行结果</strong>
          <span>{status === "completed" ? "已完成" : status === "failed" ? "已停止" : status === "running" ? "运行中" : "本地运行"}</span>
        </div>
        <pre>{output}</pre>
      </div>
      <div className="resource-code-tasks">
        <strong>改造任务</strong>
        <ul>{artifact.tasks.map((task) => <li key={task}>{task}</li>)}</ul>
        <details>
          <summary>预期输出</summary>
          <pre>{artifact.expected_output}</pre>
        </details>
      </div>
    </div>
  );
}
