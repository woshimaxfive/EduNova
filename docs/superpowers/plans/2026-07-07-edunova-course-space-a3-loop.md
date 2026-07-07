# EduNova Course Space A3 Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `/app/courses/:courseId` from a course chat page into the A3-aligned course learning loop surface, while keeping the logged-in homepage `/app` lightweight and unchanged in product positioning.

**Architecture:** Keep the homepage as the entry surface for asking, uploading materials, selecting materials, and returning to recent courses. Move the A3 competition proof into the course space by deriving a visible learning loop from existing course data, learning state, RAG citations, generated resources, learning path, practice, report, and LangGraph trace. Add focused frontend view-model helpers and course-space components first; reuse existing backend APIs before proposing any new API.

**Tech Stack:** React, TypeScript, TanStack Query, Vitest, React Testing Library, FastAPI-compatible existing API clients, LangGraph trace data, CSS in `frontend/src/styles/global.css`.

---

## Scope Lock

This plan modifies the course route only:

```text
/app/courses/:courseId
```

This plan does not change the logged-in homepage product role:

```text
/app
```

Do not convert EduNova into an OpenMAIC-style virtual classroom. OpenMAIC can inform pacing and process visibility, but the product target remains the A3 requirement: personalized resource generation and a learning multi-agent system.

## A3 Requirement Mapping

Source: `docs/软件杯A3赛题.txt`.

| A3 requirement | Course-space expression |
| --- | --- |
| 对话式学习画像 | Show how profile evidence affects the current course goal and Agent trace. |
| 多智能体协同资源生成 | Allow course-space generation of 5 resource types from the current knowledge point, citation, or weakness. |
| 个性化学习路径和资源推送 | Show next learning step, path summary, recommended resources, and why they were selected. |
| 智能辅导 | Keep course RAG chat with citations, streaming, and safe collaboration trace. |
| 学习效果评估 | Link practice results back to weakness, mastery, path, and report evidence. |
| 非功能性要求 | Keep UI clear, source-grounded, responsive, traceable, and free of fake references. |

## File Structure

Create these focused files:

- `frontend/src/features/course-space/a3Loop.ts`
  - Pure TypeScript view model for course-space learning loop summaries, study steps, and closed-loop actions.
- `frontend/src/features/course-space/a3Loop.test.ts`
  - Unit tests for the view model without React rendering.
- `frontend/src/components/course-space/CourseLoopHero.tsx`
  - Course-space top summary for current goal, evidence, and next step.
- `frontend/src/components/course-space/CourseStudyStepRail.tsx`
  - Compact study-step rail showing A3 learning loop progress.
- `frontend/src/components/course-space/CourseClosedLoopActions.tsx`
  - Answer-level action area for citations, resources, path, practice, report, and trace.
- `frontend/src/components/course-space/CourseInlineResourcePanel.tsx`
  - Course-local 5-resource generation panel and generated result summary.
- `frontend/src/components/course-space/courseSpaceLabels.ts`
  - Shared Chinese labels for resource types, step statuses, and Agent action names.

Modify these existing files:

- `frontend/src/pages/CourseSpacePage.tsx`
  - Compose the new course-space components, fetch current path/resources where useful, and keep existing chat/session behavior.
- `frontend/src/pages/CourseSpacePage.test.tsx`
  - Assert A3 course-space behavior and no regression in existing course chat, citations, resource entry, path entry, and trace display.
- `frontend/src/styles/global.css`
  - Add styles under course-scoped selectors only, such as `.course-loop-hero`, `.course-study-step-rail`, and `.course-closed-loop-actions`.
- `docs/COURSE_SPACE_DESIGN.md`
  - Update the course-space direction from "default Q&A + study mode" to "A3 course learning loop with Q&A and study mode".
- `docs/AGENT_DESIGN.md`
  - Clarify that course-space Agent trace is shown as collaboration evidence, not raw chain-of-thought.
- `docs/STATUS.md`
  - Record the implemented course-space A3 loop status once code and tests pass.
- `docs/DEFENSE_QA.md`
  - Add the answer for why the course space is the A3 demonstration center.

Do not modify these files for this plan unless a test reveals a direct compile dependency:

- `frontend/src/pages/LearningSpacePage.tsx`
- `frontend/src/app/routePaths.ts`
- `backend/app/**`

---

## Task 1: Add Pure A3 Course Loop View Model

**Files:**
- Create: `frontend/src/features/course-space/a3Loop.ts`
- Create: `frontend/src/features/course-space/a3Loop.test.ts`

- [ ] **Step 1: Write failing tests for the A3 loop summary**

Create `frontend/src/features/course-space/a3Loop.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

import {
  buildCourseLoopSummary,
  buildStudySteps,
  type CourseLoopInput
} from "./a3Loop";

const baseInput: CourseLoopInput = {
  courseTitle: "人工智能导论",
  materialCount: 3,
  knowledgePointCount: 8,
  progressPercent: 42,
  latestQuestion: "为什么 RAG 能减少幻觉？",
  citationCount: 4,
  pendingWeaknessCount: 2,
  confirmedWeaknessCount: 1,
  resourceCount: 5,
  hasActivePath: true,
  latestTraceWorkflow: "course_tutor",
  latestTraceId: "trace_course_001",
  hasLatestReport: true
};

describe("course-space A3 loop view model", () => {
  it("builds a course goal from weakness and latest question evidence", () => {
    const summary = buildCourseLoopSummary(baseInput);

    expect(summary.title).toBe("人工智能导论");
    expect(summary.currentGoal).toBe("围绕最新问题补强 2 个待确认弱点");
    expect(summary.evidenceLine).toBe("3 份资料 · 8 个知识点 · 4 条引用 · 5 个资源");
    expect(summary.nextAction).toBe("先确认薄弱点，再生成针对性资源并进入路径任务");
    expect(summary.traceLabel).toBe("course_tutor · trace_course_001");
  });

  it("falls back to course progress when there is no latest question", () => {
    const summary = buildCourseLoopSummary({
      ...baseInput,
      latestQuestion: null,
      citationCount: 0,
      pendingWeaknessCount: 0,
      confirmedWeaknessCount: 0,
      resourceCount: 0,
      hasActivePath: false,
      latestTraceWorkflow: null,
      latestTraceId: null
    });

    expect(summary.currentGoal).toBe("从课程资料和知识点开始建立学习闭环");
    expect(summary.nextAction).toBe("先提问或选择知识点，生成第一批个性化学习依据");
    expect(summary.traceLabel).toBeNull();
  });

  it("orders study steps according to the A3 learning loop", () => {
    const steps = buildStudySteps(baseInput);

    expect(steps.map((step) => step.key)).toEqual([
      "profile",
      "retrieval",
      "tutor",
      "weakness",
      "resource",
      "path",
      "assessment",
      "report"
    ]);
    expect(steps.find((step) => step.key === "resource")?.status).toBe("ready");
    expect(steps.find((step) => step.key === "assessment")?.status).toBe("next");
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
cd frontend
pnpm test -- a3Loop
```

Expected result:

```text
FAIL frontend/src/features/course-space/a3Loop.test.ts
Cannot find module './a3Loop'
```

- [ ] **Step 3: Implement the view model**

Create `frontend/src/features/course-space/a3Loop.ts`:

```typescript
export type StudyStepKey =
  | "profile"
  | "retrieval"
  | "tutor"
  | "weakness"
  | "resource"
  | "path"
  | "assessment"
  | "report";

export type StudyStepStatus = "done" | "ready" | "next" | "empty";

export type CourseLoopInput = {
  courseTitle: string;
  materialCount: number;
  knowledgePointCount: number;
  progressPercent: number;
  latestQuestion: string | null;
  citationCount: number;
  pendingWeaknessCount: number;
  confirmedWeaknessCount: number;
  resourceCount: number;
  hasActivePath: boolean;
  latestTraceWorkflow: string | null;
  latestTraceId: string | null;
  hasLatestReport: boolean;
};

export type CourseLoopSummary = {
  title: string;
  currentGoal: string;
  evidenceLine: string;
  nextAction: string;
  progressLabel: string;
  traceLabel: string | null;
};

export type StudyStep = {
  key: StudyStepKey;
  label: string;
  description: string;
  status: StudyStepStatus;
};

export function buildCourseLoopSummary(input: CourseLoopInput): CourseLoopSummary {
  const hasWeakness = input.pendingWeaknessCount > 0 || input.confirmedWeaknessCount > 0;
  const hasQuestion = Boolean(input.latestQuestion?.trim());
  const hasGeneratedEvidence = input.citationCount > 0 || input.resourceCount > 0 || input.hasActivePath;

  const currentGoal =
    hasQuestion && hasWeakness
      ? `围绕最新问题补强 ${input.pendingWeaknessCount + input.confirmedWeaknessCount} 个待确认弱点`
      : hasQuestion
        ? "围绕最新问题建立资料依据和下一步行动"
        : hasGeneratedEvidence
          ? "根据课程证据推进下一步个性化学习"
          : "从课程资料和知识点开始建立学习闭环";

  const nextAction = hasWeakness
    ? "先确认薄弱点，再生成针对性资源并进入路径任务"
    : input.hasActivePath
      ? "继续完成路径任务，并用练习结果更新掌握度"
      : "先提问或选择知识点，生成第一批个性化学习依据";

  const traceLabel =
    input.latestTraceWorkflow && input.latestTraceId ? `${input.latestTraceWorkflow} · ${input.latestTraceId}` : null;

  return {
    title: input.courseTitle,
    currentGoal,
    evidenceLine: `${input.materialCount} 份资料 · ${input.knowledgePointCount} 个知识点 · ${input.citationCount} 条引用 · ${input.resourceCount} 个资源`,
    nextAction,
    progressLabel: `${input.progressPercent}%`,
    traceLabel
  };
}

export function buildStudySteps(input: CourseLoopInput): StudyStep[] {
  const hasRetrieval = input.citationCount > 0;
  const hasTutor = Boolean(input.latestQuestion?.trim());
  const hasWeakness = input.pendingWeaknessCount > 0 || input.confirmedWeaknessCount > 0;
  const hasResources = input.resourceCount > 0;

  return [
    {
      key: "profile",
      label: "画像",
      description: "用学生目标、历史和偏好确定课程目标",
      status: "done"
    },
    {
      key: "retrieval",
      label: "检索",
      description: hasRetrieval ? `找到 ${input.citationCount} 条课程依据` : "等待课程提问或知识点选择",
      status: hasRetrieval ? "done" : "ready"
    },
    {
      key: "tutor",
      label: "辅导",
      description: hasTutor ? "已围绕当前问题生成课程回答" : "等待学生发起课程问题",
      status: hasTutor ? "done" : "ready"
    },
    {
      key: "weakness",
      label: "弱点",
      description: hasWeakness ? `${input.pendingWeaknessCount + input.confirmedWeaknessCount} 个弱点等待处理` : "等待练习或问答沉淀弱点",
      status: hasWeakness ? "ready" : "empty"
    },
    {
      key: "resource",
      label: "资源",
      description: hasResources ? `已有 ${input.resourceCount} 个个性化资源` : "可生成讲解、思维导图、练习、拓展和代码资源",
      status: hasResources ? "ready" : hasWeakness || hasRetrieval ? "next" : "empty"
    },
    {
      key: "path",
      label: "路径",
      description: input.hasActivePath ? "已有学习路径，可继续推进" : "可根据资料、弱点和资源生成路径",
      status: input.hasActivePath ? "ready" : hasResources ? "next" : "empty"
    },
    {
      key: "assessment",
      label: "评估",
      description: "用练习结果更新掌握度和复习队列",
      status: input.hasActivePath || hasResources ? "next" : "empty"
    },
    {
      key: "report",
      label: "报告",
      description: input.hasLatestReport ? "已有学习报告证据" : "完成练习后生成阶段报告",
      status: input.hasLatestReport ? "ready" : "empty"
    }
  ];
}
```

- [ ] **Step 4: Run the unit test**

Run:

```powershell
cd frontend
pnpm test -- a3Loop
```

Expected result:

```text
PASS frontend/src/features/course-space/a3Loop.test.ts
```

---

## Task 2: Add Course-Space A3 Components

**Files:**
- Create: `frontend/src/components/course-space/courseSpaceLabels.ts`
- Create: `frontend/src/components/course-space/CourseLoopHero.tsx`
- Create: `frontend/src/components/course-space/CourseStudyStepRail.tsx`
- Create: `frontend/src/components/course-space/CourseClosedLoopActions.tsx`

- [ ] **Step 1: Add shared labels**

Create `frontend/src/components/course-space/courseSpaceLabels.ts`:

```typescript
import { type ResourceType } from "../../api/resources";
import { type StudyStepStatus } from "../../features/course-space/a3Loop";

export const resourceTypeLabels: Record<ResourceType, string> = {
  doc: "讲解文档",
  mindmap: "思维导图",
  quiz: "练习题",
  code: "代码实操",
  slide: "PPT 大纲"
};

export const studyStepStatusLabels: Record<StudyStepStatus, string> = {
  done: "已完成",
  ready: "可继续",
  next: "建议下一步",
  empty: "待产生"
};
```

- [ ] **Step 2: Add the loop hero component**

Create `frontend/src/components/course-space/CourseLoopHero.tsx`:

```tsx
import { ArrowRight, Graph, ShieldCheck } from "@phosphor-icons/react";

import { type CourseLoopSummary } from "../../features/course-space/a3Loop";

type CourseLoopHeroProps = {
  summary: CourseLoopSummary;
};

export function CourseLoopHero({ summary }: CourseLoopHeroProps) {
  return (
    <section className="course-loop-hero" aria-label="课程学习闭环">
      <div className="course-loop-copy">
        <span className="course-loop-kicker">
          <Graph size={16} weight="duotone" aria-hidden="true" />
          A3 个性化学习闭环
        </span>
        <h1>{summary.title}</h1>
        <p>{summary.currentGoal}</p>
        <div className="course-loop-evidence" aria-label="课程依据">
          <span>{summary.evidenceLine}</span>
          {summary.traceLabel ? (
            <span>
              <ShieldCheck size={15} weight="duotone" aria-hidden="true" />
              {summary.traceLabel}
            </span>
          ) : null}
        </div>
      </div>
      <div className="course-loop-next">
        <span>下一步</span>
        <strong>{summary.nextAction}</strong>
        <em>{summary.progressLabel}</em>
        <ArrowRight size={18} weight="bold" aria-hidden="true" />
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Add the study-step rail component**

Create `frontend/src/components/course-space/CourseStudyStepRail.tsx`:

```tsx
import { CheckCircle, Circle, Sparkle } from "@phosphor-icons/react";

import { type StudyStep } from "../../features/course-space/a3Loop";
import { studyStepStatusLabels } from "./courseSpaceLabels";

type CourseStudyStepRailProps = {
  steps: StudyStep[];
};

export function CourseStudyStepRail({ steps }: CourseStudyStepRailProps) {
  return (
    <section className="course-study-step-rail" aria-label="A3 学习步骤">
      {steps.map((step) => {
        const Icon = step.status === "done" ? CheckCircle : step.status === "next" ? Sparkle : Circle;

        return (
          <article className={`course-study-step ${step.status}`} key={step.key}>
            <Icon size={18} weight={step.status === "empty" ? "regular" : "duotone"} aria-hidden="true" />
            <div>
              <span>{studyStepStatusLabels[step.status]}</span>
              <strong>{step.label}</strong>
              <p>{step.description}</p>
            </div>
          </article>
        );
      })}
    </section>
  );
}
```

- [ ] **Step 4: Add the closed-loop action component**

Create `frontend/src/components/course-space/CourseClosedLoopActions.tsx`:

```tsx
import { ArrowSquareOut, FileText, Graph, ListChecks, Sparkle, Target } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";

type CourseClosedLoopActionsProps = {
  courseId: number;
  citationCount: number;
  resourceCount: number;
  hasActivePath: boolean;
  hasTrace: boolean;
  onOpenCitations: () => void;
  onOpenResources: () => void;
  onOpenPath: () => void;
  onOpenTrace: () => void;
};

export function CourseClosedLoopActions({
  courseId,
  citationCount,
  resourceCount,
  hasActivePath,
  hasTrace,
  onOpenCitations,
  onOpenResources,
  onOpenPath,
  onOpenTrace
}: CourseClosedLoopActionsProps) {
  return (
    <section className="course-closed-loop-actions" aria-label="课程闭环行动">
      <button type="button" onClick={onOpenCitations}>
        <FileText size={17} weight="duotone" aria-hidden="true" />
        <span>来源</span>
        <em>{citationCount} 条</em>
      </button>
      <button type="button" onClick={onOpenResources}>
        <Sparkle size={17} weight="duotone" aria-hidden="true" />
        <span>生成资源</span>
        <em>{resourceCount} 个</em>
      </button>
      <button type="button" onClick={onOpenPath}>
        <Target size={17} weight="duotone" aria-hidden="true" />
        <span>学习路径</span>
        <em>{hasActivePath ? "已生成" : "可生成"}</em>
      </button>
      <Link to={`${PATHS.practice}?course_id=${courseId}`}>
        <ListChecks size={17} weight="duotone" aria-hidden="true" />
        <span>进入练习</span>
        <ArrowSquareOut size={15} weight="bold" aria-hidden="true" />
      </Link>
      <button type="button" onClick={onOpenTrace}>
        <Graph size={17} weight="duotone" aria-hidden="true" />
        <span>Agent 轨迹</span>
        <em>{hasTrace ? "真实 trace" : "暂无"}</em>
      </button>
    </section>
  );
}
```

- [ ] **Step 5: Run TypeScript tests for compile feedback**

Run:

```powershell
cd frontend
pnpm test -- a3Loop
```

Expected result:

```text
PASS frontend/src/features/course-space/a3Loop.test.ts
```

---

## Task 3: Integrate A3 Loop Into CourseSpacePage

**Files:**
- Modify: `frontend/src/pages/CourseSpacePage.tsx`
- Modify: `frontend/src/pages/CourseSpacePage.test.tsx`
- Modify: `frontend/src/styles/global.css`

- [ ] **Step 1: Add integration tests for course-space scope**

In `frontend/src/pages/CourseSpacePage.test.tsx`, add tests that assert the course space shows A3 loop language and does not depend on the homepage layout:

```tsx
it("shows the A3 learning loop in course space without replacing course chat", async () => {
  renderCourseSpacePage();

  expect(await screen.findByRole("region", { name: "课程学习闭环" })).toBeInTheDocument();
  expect(screen.getByText("A3 个性化学习闭环")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "课程对话空间" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /来源/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /生成资源/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /学习路径/ })).toBeInTheDocument();
});

it("keeps the logged-in homepage out of the course-space A3 loop contract", async () => {
  renderCourseSpacePage();

  expect(await screen.findByRole("region", { name: "课程学习闭环" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "进入你的学习空间" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the course-space tests and confirm they fail**

Run:

```powershell
cd frontend
pnpm test -- CourseSpacePage
```

Expected result:

```text
FAIL frontend/src/pages/CourseSpacePage.test.tsx
Unable to find an accessible element with the role "region" and name "课程学习闭环"
```

- [ ] **Step 3: Compose the new view model in CourseSpacePage**

In `frontend/src/pages/CourseSpacePage.tsx`, add imports:

```tsx
import { CourseClosedLoopActions } from "../components/course-space/CourseClosedLoopActions";
import { CourseLoopHero } from "../components/course-space/CourseLoopHero";
import { CourseStudyStepRail } from "../components/course-space/CourseStudyStepRail";
import { buildCourseLoopSummary, buildStudySteps } from "../features/course-space/a3Loop";
import { listResources } from "../api/resources";
import { getCurrentPath } from "../api/paths";
import { getLatestReport } from "../api/reports";
```

Add queries after `agentTraceQuery`:

```tsx
  const courseResourcesQuery = useQuery({
    queryKey: ["resources", "course", numericCourseId],
    queryFn: () => listResources({ courseId: numericCourseId }),
    enabled: hasRealCourseId,
    staleTime: 10_000
  });
  const currentPathQuery = useQuery({
    queryKey: ["paths", "current", numericCourseId],
    queryFn: () => getCurrentPath(numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 10_000
  });
  const latestReportQuery = useQuery({
    queryKey: ["reports", "latest", numericCourseId],
    queryFn: () => getLatestReport(numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 10_000
  });
```

Add derived data:

```tsx
  const generatedResources = courseResourcesQuery.data?.data ?? [];
  const currentPath = currentPathQuery.data?.data ?? null;
  const latestReport = latestReportQuery.data?.data ?? null;
  const latestUserQuestion = [...displayedCourseMessages].reverse().find((message) => message.role === "user")?.content ?? null;
  const courseLoopInput = {
    courseTitle: courseSummary.title,
    materialCount,
    knowledgePointCount,
    progressPercent: courseSummary.progressPercent,
    latestQuestion: latestUserQuestion,
    citationCount: latestRagResults.length,
    pendingWeaknessCount: weaknessSummary?.pending_count ?? 0,
    confirmedWeaknessCount: weaknessSummary?.confirmed_count ?? 0,
    resourceCount: generatedResources.length,
    hasActivePath: Boolean(currentPath?.path),
    latestTraceWorkflow: agentTraceQuery.data?.data.workflow ?? null,
    latestTraceId: latestAgentTraceId,
    hasLatestReport: latestReport?.status === "ready"
  };
  const courseLoopSummary = buildCourseLoopSummary(courseLoopInput);
  const courseStudySteps = buildStudySteps(courseLoopInput);
```

Replace the old `<header className="course-space-hero">...</header>` with:

```tsx
            <CourseLoopHero summary={courseLoopSummary} />
            <CourseStudyStepRail steps={courseStudySteps} />
```

Keep the old course metrics data visible through `CourseLoopHero`; do not add a second course title block.

- [ ] **Step 4: Replace the answer action row with closed-loop actions**

Inside the answer detail panel, replace the repeated action buttons with:

```tsx
                      <CourseClosedLoopActions
                        courseId={numericCourseId}
                        citationCount={latestRagResults.length}
                        resourceCount={generatedResources.length}
                        hasActivePath={Boolean(currentPath?.path)}
                        hasTrace={Boolean(latestAgentTraceId)}
                        onOpenCitations={() => setActiveAnswerPanel("citations")}
                        onOpenResources={() => setActiveAnswerPanel("resources")}
                        onOpenPath={() => setActiveAnswerPanel("path")}
                        onOpenTrace={() => setActiveAnswerPanel("thinking")}
                      />
```

Keep the existing `AnswerDetailPanel` rendering behavior for citations, resources, path, and thinking. This task changes the action presentation, not the answer data contract.

- [ ] **Step 5: Add scoped CSS**

Append course-scoped styles to `frontend/src/styles/global.css` near the existing course-space block:

```css
.course-loop-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.34fr);
  gap: 18px;
  align-items: stretch;
  padding: 22px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.84);
}

.course-loop-copy {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.course-loop-kicker,
.course-loop-evidence,
.course-loop-evidence span,
.course-loop-next span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.course-loop-copy h1 {
  margin: 0;
  color: #10201d;
  font-size: clamp(1.55rem, 2.6vw, 2.4rem);
  line-height: 1.08;
  letter-spacing: 0;
}

.course-loop-copy p,
.course-loop-evidence,
.course-loop-next strong {
  margin: 0;
  color: rgba(16, 32, 29, 0.72);
}

.course-loop-next {
  display: grid;
  gap: 8px;
  align-content: center;
  padding: 16px;
  border-radius: 8px;
  background: #e8f7f3;
  color: #0f3f38;
}

.course-loop-next em {
  font-style: normal;
  font-weight: 800;
}

.course-study-step-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.course-study-step {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  min-height: 112px;
  padding: 12px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
}

.course-study-step span,
.course-study-step p,
.course-closed-loop-actions em {
  color: rgba(16, 32, 29, 0.58);
  font-size: 0.78rem;
}

.course-study-step strong {
  display: block;
  margin-top: 2px;
  color: #10201d;
}

.course-study-step p {
  margin: 4px 0 0;
  line-height: 1.45;
}

.course-closed-loop-actions {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.course-closed-loop-actions button,
.course-closed-loop-actions a {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.82);
  color: #10201d;
  text-decoration: none;
}

@media (max-width: 860px) {
  .course-loop-hero,
  .course-study-step-rail,
  .course-closed-loop-actions {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd frontend
pnpm test -- CourseSpacePage a3Loop
```

Expected result:

```text
PASS frontend/src/features/course-space/a3Loop.test.ts
PASS frontend/src/pages/CourseSpacePage.test.tsx
```

---

## Task 4: Embed 5-Type Resource Generation in Course Space

**Files:**
- Create: `frontend/src/components/course-space/CourseInlineResourcePanel.tsx`
- Modify: `frontend/src/pages/CourseSpacePage.tsx`
- Modify: `frontend/src/pages/CourseSpacePage.test.tsx`

- [ ] **Step 1: Write the resource panel test**

In `frontend/src/pages/CourseSpacePage.test.tsx`, add:

```tsx
it("lets the student generate five A3 resource types from course space", async () => {
  renderCourseSpacePage();

  expect(await screen.findByRole("button", { name: /生成资源/ })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /生成资源/ }));

  expect(screen.getByRole("region", { name: "课程资源生成" })).toBeInTheDocument();
  expect(screen.getByLabelText("讲解文档")).toBeChecked();
  expect(screen.getByLabelText("思维导图")).toBeChecked();
  expect(screen.getByLabelText("练习题")).toBeChecked();
  expect(screen.getByLabelText("代码实操")).toBeChecked();
  expect(screen.getByLabelText("PPT 大纲")).toBeChecked();
  expect(screen.getByRole("button", { name: "生成 5 类个性化资源" })).toBeEnabled();
});
```

- [ ] **Step 2: Add the inline resource panel**

Create `frontend/src/components/course-space/CourseInlineResourcePanel.tsx`:

```tsx
import { type ChangeEvent } from "react";

import { type ResourceType } from "../../api/resources";
import { resourceTypeLabels } from "./courseSpaceLabels";

const orderedResourceTypes: ResourceType[] = ["doc", "mindmap", "quiz", "code", "slide"];

type CourseInlineResourcePanelProps = {
  selectedTypes: ResourceType[];
  isGenerating: boolean;
  feedback: string | null;
  onToggleType: (resourceType: ResourceType) => void;
  onGenerate: () => void;
};

export function CourseInlineResourcePanel({
  selectedTypes,
  isGenerating,
  feedback,
  onToggleType,
  onGenerate
}: CourseInlineResourcePanelProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onToggleType(event.target.value as ResourceType);
  }

  return (
    <section className="course-inline-resource-panel" role="region" aria-label="课程资源生成">
      <div className="course-inline-resource-heading">
        <div>
          <span>多智能体资源生成</span>
          <h3>从当前课程证据生成 A3 资源</h3>
        </div>
        <button type="button" disabled={isGenerating || selectedTypes.length === 0} onClick={onGenerate}>
          {isGenerating ? "生成中" : `生成 ${selectedTypes.length} 类个性化资源`}
        </button>
      </div>
      <div className="course-resource-type-grid">
        {orderedResourceTypes.map((resourceType) => (
          <label key={resourceType}>
            <input
              type="checkbox"
              value={resourceType}
              checked={selectedTypes.includes(resourceType)}
              onChange={handleChange}
            />
            <span>{resourceTypeLabels[resourceType]}</span>
          </label>
        ))}
      </div>
      {feedback ? <p className="course-inline-resource-feedback">{feedback}</p> : null}
    </section>
  );
}
```

- [ ] **Step 3: Wire generation in CourseSpacePage**

In `frontend/src/pages/CourseSpacePage.tsx`, add imports:

```tsx
import { CourseInlineResourcePanel } from "../components/course-space/CourseInlineResourcePanel";
import { generateResources, type ResourceType } from "../api/resources";
```

Add state:

```tsx
  const [selectedCourseResourceTypes, setSelectedCourseResourceTypes] = useState<ResourceType[]>([
    "doc",
    "mindmap",
    "quiz",
    "code",
    "slide"
  ]);
  const [courseResourceFeedback, setCourseResourceFeedback] = useState<string | null>(null);
```

Add mutation:

```tsx
  const courseResourceMutation = useMutation({
    mutationFn: () =>
      generateResources({
        course_id: numericCourseId,
        knowledge_point_id:
          studyTarget?.type === "knowledge" ? Number.parseInt(studyTarget.id, 10) : undefined,
        resource_types: selectedCourseResourceTypes,
        learning_goal: latestUserQuestion ?? courseLoopSummary.currentGoal,
        difficulty: "medium"
      }),
    onSuccess: () => {
      setCourseResourceFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["resources", "course", numericCourseId] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state", numericCourseId] });
    },
    onError: () => {
      setCourseResourceFeedback("课程资源生成失败，请稍后重试。");
    }
  });
```

Add handlers:

```tsx
  function toggleCourseResourceType(resourceType: ResourceType) {
    setSelectedCourseResourceTypes((current) =>
      current.includes(resourceType)
        ? current.filter((item) => item !== resourceType)
        : [...current, resourceType]
    );
  }

  function submitCourseResourceGeneration() {
    if (!hasRealCourseId || courseResourceMutation.isPending || selectedCourseResourceTypes.length === 0) {
      return;
    }
    courseResourceMutation.mutate();
  }
```

Render `CourseInlineResourcePanel` when `activeAnswerPanel === "resources"` inside the answer detail area:

```tsx
                      {activeAnswerPanel === "resources" ? (
                        <CourseInlineResourcePanel
                          selectedTypes={selectedCourseResourceTypes}
                          isGenerating={courseResourceMutation.isPending}
                          feedback={courseResourceFeedback}
                          onToggleType={toggleCourseResourceType}
                          onGenerate={submitCourseResourceGeneration}
                        />
                      ) : null}
```

Keep the existing resource工坊 link or summary if it already exists, but make the inline panel the first visible resource action after an answer.

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
cd frontend
pnpm test -- CourseSpacePage
```

Expected result:

```text
PASS frontend/src/pages/CourseSpacePage.test.tsx
```

---

## Task 5: Connect Path, Practice, and Report Return Flow

**Files:**
- Modify: `frontend/src/pages/CourseSpacePage.tsx`
- Modify: `frontend/src/components/course-space/CourseClosedLoopActions.tsx`
- Modify: `frontend/src/pages/CourseSpacePage.test.tsx`

- [ ] **Step 1: Add return-flow tests**

In `frontend/src/pages/CourseSpacePage.test.tsx`, add:

```tsx
it("shows path, practice, and report actions as part of the course learning loop", async () => {
  renderCourseSpacePage();

  expect(await screen.findByRole("region", { name: "课程学习闭环" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /学习路径/ })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /进入练习/ })).toHaveAttribute("href", "/app/practice?course_id=43");
  expect(screen.getByRole("link", { name: /学习报告/ })).toHaveAttribute("href", "/app/reports?course_id=43");
});
```

- [ ] **Step 2: Add report link to closed-loop actions**

Update `CourseClosedLoopActionsProps`:

```tsx
type CourseClosedLoopActionsProps = {
  courseId: number;
  citationCount: number;
  resourceCount: number;
  hasActivePath: boolean;
  hasTrace: boolean;
  onOpenCitations: () => void;
  onOpenResources: () => void;
  onOpenPath: () => void;
  onOpenTrace: () => void;
};
```

Inside the returned action grid, add:

```tsx
      <Link to={`${PATHS.reports}?course_id=${courseId}`}>
        <FileText size={17} weight="duotone" aria-hidden="true" />
        <span>学习报告</span>
        <ArrowSquareOut size={15} weight="bold" aria-hidden="true" />
      </Link>
```

If the grid becomes too dense on desktop, keep it two rows inside the same action section. Do not move path, practice, or report into the homepage.

- [ ] **Step 3: Run targeted tests**

Run:

```powershell
cd frontend
pnpm test -- CourseSpacePage
```

Expected result:

```text
PASS frontend/src/pages/CourseSpacePage.test.tsx
```

---

## Task 6: Update Course-Space Styling Responsively

**Files:**
- Modify: `frontend/src/styles/global.css`

- [ ] **Step 1: Add resource panel styles**

Append these course-scoped styles near the other course-space styles:

```css
.course-inline-resource-panel {
  display: grid;
  gap: 14px;
  padding: 14px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 8px;
  background: rgba(248, 253, 251, 0.92);
}

.course-inline-resource-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.course-inline-resource-heading span {
  color: rgba(16, 32, 29, 0.56);
  font-size: 0.78rem;
}

.course-inline-resource-heading h3 {
  margin: 2px 0 0;
  color: #10201d;
  font-size: 1rem;
  letter-spacing: 0;
}

.course-inline-resource-heading button {
  min-height: 38px;
  border: 0;
  border-radius: 8px;
  background: #0f766e;
  color: #ffffff;
  font-weight: 800;
}

.course-resource-type-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.course-resource-type-grid label {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 8px;
  background: #ffffff;
  color: #10201d;
}

.course-inline-resource-feedback {
  margin: 0;
  color: #9f1239;
  font-size: 0.86rem;
}

@media (max-width: 720px) {
  .course-inline-resource-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .course-resource-type-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 2: Check color direction**

Run:

```powershell
rg -n "#7c3aed|purple|violet|orb|bokeh|gradient" frontend\src\styles\global.css
```

Expected result:

```text
No new course-space selectors use purple-heavy, orb, bokeh, or decorative gradient styling.
```

- [ ] **Step 3: Run build**

Run:

```powershell
cd frontend
pnpm build
```

Expected result:

```text
vite build completed successfully
```

---

## Task 7: Sync Documentation and Defense Wording

**Files:**
- Modify: `docs/COURSE_SPACE_DESIGN.md`
- Modify: `docs/AGENT_DESIGN.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/DEFENSE_QA.md`

- [ ] **Step 1: Update course-space design wording**

In `docs/COURSE_SPACE_DESIGN.md`, update the one-line direction to:

```text
课程空间 = A3 个性化学习闭环主场 + 默认问答模式 + 按需进入学习模式
```

Add this boundary paragraph near the top:

```text
本轮课程空间改造只作用于 `/app/courses/:courseId`。登录后首页 `/app` 继续保持轻量 AI 学习入口，不承载完整赛题能力，不改成复杂驾驶舱。
```

- [ ] **Step 2: Update Agent design wording**

In `docs/AGENT_DESIGN.md`, under frontend presentation, add:

```text
- 课程空间把 LangGraph trace 产品化为 A3 学习闭环证据，说明画像、检索、辅导、弱点、资源、路径、评估和审核如何协作；不展示原始思维链、系统提示词或完整模型输入。
```

- [ ] **Step 3: Update defense Q&A**

In `docs/DEFENSE_QA.md`, add:

```markdown
## 课程空间为什么是主展示页？

A：A3 赛题核心不是普通聊天，而是个性化资源生成与学习多智能体系统。EduNova 将 `/app/courses/:courseId` 设计为课程级学习闭环主场：同一页面串联课程资料、RAG 引用问答、弱点识别、5 类资源生成、学习路径、练习评估、报告证据和 LangGraph Agent 轨迹。登录后首页 `/app` 保持轻量入口，避免把所有功能堆到首页。
```

- [ ] **Step 4: Update status after implementation passes**

In `docs/STATUS.md`, add a concise status item after the course-space phase entry:

```text
课程空间已按 A3 赛题主线升级为课程级个性化学习闭环展示面，能在课程上下文中展示当前目标、资料证据、Agent 协作轨迹、资源生成入口、路径/练习/报告回流入口；登录后首页仍保持轻量学习入口。
```

- [ ] **Step 5: Run encoding check**

Run:

```powershell
.\scripts\verify_encoding.ps1
```

Expected result:

```text
Encoding verification passed
```

---

## Task 8: Full Verification and Browser Acceptance

**Files:**
- No planned source edits.

- [ ] **Step 1: Run focused frontend tests**

Run:

```powershell
cd frontend
pnpm test -- CourseSpacePage a3Loop
```

Expected result:

```text
PASS frontend/src/features/course-space/a3Loop.test.ts
PASS frontend/src/pages/CourseSpacePage.test.tsx
```

- [ ] **Step 2: Run frontend lint and build**

Run:

```powershell
cd frontend
pnpm lint
pnpm build
```

Expected result:

```text
No lint errors
vite build completed successfully
```

- [ ] **Step 3: Run project verification**

Run:

```powershell
.\scripts\verify_encoding.ps1
.\scripts\test.ps1
```

Expected result:

```text
Encoding verification passed
Backend tests pass
Frontend tests pass
Frontend lint/build pass
Docker Compose config check passes
```

- [ ] **Step 4: Start Docker and verify course space**

Run:

```powershell
docker compose up --build -d
```

Expected result:

```text
Frontend, backend, database, Redis, and worker services are running or healthy.
```

Use the browser acceptance route:

```text
http://127.0.0.1:8080
```

Check desktop width:

```text
1. Log in or use the demo entry.
2. Enter a real course at `/app/courses/:courseId`.
3. Confirm the top surface says "A3 个性化学习闭环".
4. Ask a course question and confirm the answer still streams.
5. Open 来源, 生成资源, 学习路径, 进入练习, 学习报告, Agent 轨迹.
6. Confirm no content overlaps and the page does not look like a backend dashboard.
```

Check mobile width `390px`:

```text
1. The loop hero stacks cleanly.
2. Study steps do not overflow.
3. Closed-loop action buttons wrap or stack without clipping text.
4. The composer remains usable.
```

- [ ] **Step 5: Git safety check**

Run:

```powershell
git status --short
git diff --name-only
```

Expected result:

```text
Changed files are limited to course-space frontend files, course-space tests, scoped CSS, and synced docs.
No real .env, API key, JWT, uploaded private material, generated export, or local cache is staged.
```

---

## Self-Review Checklist

- [ ] The plan implements the A3 course-space direction, not an OpenMAIC clone.
- [ ] The plan does not change the logged-in homepage `/app` product role.
- [ ] The plan uses existing resource, path, practice, report, tutor, and trace APIs before proposing backend changes.
- [ ] The plan keeps raw chain-of-thought, system prompts, complete model input, API keys, and private user material out of the UI.
- [ ] The plan includes unit tests, page tests, lint/build, encoding check, full verification, Docker, desktop browser acceptance, and `390px` mobile acceptance.
- [ ] The plan updates Chinese living docs in the same implementation phase as the UI changes.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-07-07-edunova-course-space-a3-loop.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

