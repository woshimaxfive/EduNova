import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import mermaid from "mermaid";
import { type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createResourceExportJob,
  listResourceExportJobs,
  type GeneratedResource,
  type ResourceArtifact,
  type ResourceType
} from "../../api/resources";
import { ResourceRenderer } from "./ResourceRenderer";
import { normalizeMindmapMarkdown } from "./mindmapMarkdown";

vi.mock("markmap-lib", () => ({
  Transformer: class {
    transform() {
      return { root: { content: "启发式搜索", children: [] } };
    }
  }
}));

const markmapFit = vi.fn().mockResolvedValue(undefined);
vi.mock("markmap-view", () => ({
  Markmap: {
    create: vi.fn(() => ({ fit: markmapFit, rescale: vi.fn(), destroy: vi.fn() }))
  }
}));

it("normalizes common LaTeX arrows before Markmap rendering", () => {
  expect(normalizeMindmapMarkdown("相同元素 $\\rightarrow$ 不同结构")).toBe("相同元素 → 不同结构");
  expect(normalizeMindmapMarkdown("前置 $\\leftarrow$ 当前 $\\leftrightarrow$ 后续")).toBe("前置 ← 当前 ↔ 后续");
});

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg aria-label="diagram"><text>过程图</text></svg>' })
  }
}));

vi.mock("@uiw/react-codemirror", () => ({
  default: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <textarea aria-label="Python 代码编辑器" value={value} onChange={(event) => onChange(event.target.value)} />
  )
}));

vi.mock("../../api/resources", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/resources")>();
  return {
    ...actual,
    createResourceExportJob: vi.fn(),
    listResourceExportJobs: vi.fn()
  };
});

vi.mock("../../api/exports", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/exports")>();
  return { ...actual, downloadExportJob: vi.fn() };
});

function makeResource(resourceType: ResourceType, artifact: ResourceArtifact): GeneratedResource {
  return {
    id: "901",
    course_id: "101",
    knowledge_point_id: "501",
    resource_type: resourceType,
    title: `${resourceType}资源`,
    content_json: {
      schema_version: 2,
      format: "rich",
      markdown: `# ${resourceType}资源`,
      artifact,
      metadata: { generation_mode: "model_enhanced", review_mode: "model_and_rules" }
    },
    citation_json: [],
    status: "completed",
    review_status: "passed",
    confidence_score: 0.88,
    agent_trace_id: "trace_resource",
    created_at: "2026-07-10T08:00:00Z",
    updated_at: "2026-07-10T08:00:00Z"
  };
}

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("ResourceRenderer", () => {
  beforeEach(() => {
    vi.mocked(listResourceExportJobs).mockResolvedValue({ data: [], trace_id: "trace_exports" });
    vi.mocked(createResourceExportJob).mockResolvedValue({
      data: {
        job_id: "1001",
        status: "queued",
        format: "pptx",
        export_type: "resource_artifact",
        resource_id: "901",
        filename: null,
        content_type: null,
        error_message: null,
        created_at: "2026-07-10T08:00:00Z",
        updated_at: "2026-07-10T08:00:00Z"
      },
      trace_id: "trace_export"
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders structured document sections and an interactive quiz", async () => {
    const user = userEvent.setup();
    const documentResource = makeResource("doc", {
      kind: "document",
      sections: [{
        heading: "概念解释",
        body: "**A-star** 会结合已走代价和估计代价。\n\n1. 计算 `g(n)`\n2. 估计 `h(n)`\n\n```python\nscore = g + h\n```"
      }],
      citation_refs: [701]
    });
    const quizResource = makeResource("quiz", {
      kind: "quiz",
      questions: [
        {
          id: "q1",
          type: "single_choice",
          prompt: "哪项是正确学习动作？",
          options: [{ key: "A", text: "验证条件" }, { key: "B", text: "只背结论" }],
          answer: "A",
          explanation: "需要验证适用条件。",
          citation_refs: [701]
        }
      ],
      citation_refs: [701]
    });
    const { rerender } = renderWithQuery(<ResourceRenderer resource={documentResource} />);

    expect(screen.getByRole("heading", { name: "概念解释" })).toBeInTheDocument();
    expect(screen.getByText("A-star", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/计算/).closest("ol")).toBeInTheDocument();
    expect(screen.getByText("score = g + h").closest("pre")).toBeInTheDocument();
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ResourceRenderer resource={quizResource} />
      </QueryClientProvider>
    );
    await user.click(screen.getByRole("button", { name: /A.*验证条件/ }));
    await user.click(screen.getByRole("button", { name: "查看答案与解析" }));
    expect(screen.getByText("参考答案：A")).toBeInTheDocument();
    expect(screen.getByText("需要验证适用条件。")).toBeInTheDocument();
  });

  it("renders Markmap and animated Mermaid scenes", async () => {
    const user = userEvent.setup();
    const mindmap = makeResource("mindmap", {
      kind: "mindmap",
      markmap_markdown: "# 启发式搜索\n## 核心概念",
      tree: { id: "root", title: "启发式搜索", children: [] },
      citation_refs: [701]
    });
    const animation = makeResource("animation", {
      kind: "animation",
      scenes: [
        { id: "s1", title: "识别条件", narration: "先识别问题条件。", duration_ms: 3000, diagram: "flowchart LR\n A --> B" },
        { id: "s2", title: "验证结果", narration: "再验证输出。", duration_ms: 3000, diagram: "flowchart LR\n B --> C" }
      ],
      default_scene_duration_ms: 3000,
      citation_refs: [701]
    });
    const { rerender } = renderWithQuery(<ResourceRenderer resource={mindmap} />);

    expect(await screen.findByRole("img", { name: "知识点思维导图" })).toBeInTheDocument();
    await waitFor(() => expect(markmapFit).toHaveBeenCalled());
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ResourceRenderer resource={animation} />
      </QueryClientProvider>
    );
    expect(screen.getByRole("heading", { name: "识别条件" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "下一个动画场景" }));
    expect(screen.getByRole("heading", { name: "验证结果" })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "验证结果过程图解" })).toBeInTheDocument();
  });

  it("shows a student-friendly fallback instead of raw Mermaid source", async () => {
    vi.mocked(mermaid.render).mockRejectedValueOnce(new Error("parse error"));
    const animation = makeResource("animation", {
      kind: "animation",
      scenes: [
        { id: "s1", title: "错误图解", narration: "文字讲解仍然可用。", duration_ms: 3000, diagram: "flowchart LR\n A[3, |8|] --> B" }
      ],
      default_scene_duration_ms: 3000,
      citation_refs: [701]
    });

    renderWithQuery(<ResourceRenderer resource={animation} />);

    expect(await screen.findByText("这幅过程图暂时无法渲染，文字讲解仍可继续使用。")).toBeInTheDocument();
    const summary = screen.getByText("查看图解源码");
    expect(summary).toBeInTheDocument();
    expect(summary.closest("details")).not.toHaveAttribute("open");
  });

  it("runs reviewed Python in a browser worker and exposes expected output", async () => {
    class FakeWorker {
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;

      postMessage() {
        this.onmessage?.(new MessageEvent("message", { data: { type: "ready" } }));
        this.onmessage?.(new MessageEvent("message", { data: { type: "result", value: "priority=2.8" } }));
      }

      terminate() {}
    }
    vi.stubGlobal("Worker", FakeWorker);
    const codeResource = makeResource("code", {
      kind: "code_lab",
      language: "python",
      runtime: "pyodide",
      entry_file: "study_case.py",
      files: [{ path: "study_case.py", content: "print('priority=2.8')" }],
      instructions: ["点击运行"],
      expected_output: "priority=2.8",
      tasks: ["调整代价"],
      citation_refs: [701]
    });
    renderWithQuery(<ResourceRenderer resource={codeResource} />);

    fireEvent.click(await screen.findByRole("button", { name: "运行 Python 代码" }, { timeout: 10_000 }));
    expect((await screen.findAllByText("priority=2.8")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("调整代价")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("blocks unsafe Python before starting the worker", async () => {
    const codeResource = makeResource("code", {
      kind: "code_lab",
      language: "python",
      runtime: "pyodide",
      entry_file: "unsafe.py",
      files: [{ path: "unsafe.py", content: "from js import fetch\nprint(fetch)" }],
      instructions: [],
      expected_output: "",
      tasks: ["移除网络访问"],
      citation_refs: []
    });
    renderWithQuery(<ResourceRenderer resource={codeResource} />);

    fireEvent.click(await screen.findByRole("button", { name: "运行 Python 代码" }, { timeout: 10_000 }));
    expect(screen.getByText("当前代码包含被禁用的网络、文件或浏览器互操作模块。")).toBeInTheDocument();
  });

  it("renders slide navigation and automatically queues a PPTX export", async () => {
    const slideResource = makeResource("slide", {
      kind: "slide_deck",
      theme: { name: "edunova-light", aspect_ratio: "16:9", accent: "#0f8f83" },
      slides: [
        { id: "p1", title: "课程背景", bullets: ["为什么要学"], speaker_notes: "先说明目标。", layout: "title", citation_refs: [701] },
        { id: "p2", title: "关键步骤", bullets: ["识别条件"], speaker_notes: "逐步验证。", layout: "title_and_content", citation_refs: [701] }
      ],
      citation_refs: [701]
    });
    renderWithQuery(<ResourceRenderer resource={slideResource} />);

    expect(screen.getByRole("heading", { name: "课程背景" })).toBeInTheDocument();
    await waitFor(() => expect(createResourceExportJob).toHaveBeenCalledWith(Number.parseInt(slideResource.id, 10)));
  });

  it("keeps legacy Mermaid resources readable", async () => {
    const legacy: GeneratedResource = {
      ...makeResource("mindmap", {
        kind: "mindmap",
        markmap_markdown: "# ignored",
        tree: { id: "root", title: "ignored", children: [] },
        citation_refs: []
      }),
      content_json: { markdown: "# 历史思维导图\n```mermaid\nflowchart LR\n A --> B\n```" }
    };
    renderWithQuery(<ResourceRenderer resource={legacy} />);

    expect(await screen.findByRole("img", { name: "历史思维导图" })).toBeInTheDocument();
    expect(screen.getByText("查看原始资源文本")).toBeInTheDocument();
  });
});
