import { ArrowClockwise, BookOpenText, CheckCircle, X } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type PracticeSessionDetail } from "../../api/practice";
import { type GeneratedResource } from "../../api/resources";
import { PATHS } from "../../app/routePaths";
import { AgentTraceDisclosure } from "../evidence/AgentTraceDisclosure";
import { ModalFrame } from "../primitives/Dialog";

export type PracticeDrawerMode = "settings" | "results";

type PracticeDrawerProps = {
  mode: PracticeDrawerMode;
  courses: Array<{ id: string; title: string }>;
  points: Array<{ id: string; title: string }>;
  courseId: string;
  pointId: string;
  questionCount: number;
  difficulty: "adaptive" | "easy" | "medium" | "hard";
  session: PracticeSessionDetail | null;
  recommendedResources: GeneratedResource[];
  isGenerating: boolean;
  canGenerate: boolean;
  error: string;
  onCourseChange: (courseId: string) => void;
  onPointChange: (pointId: string) => void;
  onQuestionCountChange: (count: number) => void;
  onDifficultyChange: (difficulty: "adaptive" | "easy" | "medium" | "hard") => void;
  onGenerate: () => void;
  onClose: () => void;
};

export function PracticeDrawer({
  mode,
  courses,
  points,
  courseId,
  pointId,
  questionCount,
  difficulty,
  session,
  recommendedResources,
  isGenerating,
  canGenerate,
  error,
  onCourseChange,
  onPointChange,
  onQuestionCountChange,
  onDifficultyChange,
  onGenerate,
  onClose
}: PracticeDrawerProps) {
  const closure = session?.closure_update;

  return (
    <ModalFrame title={mode === "settings" ? "练习设置" : "学习结果"} layerClassName="practice-drawer-layer" onClose={onClose}>
      <aside className="practice-drawer" aria-labelledby="practice-drawer-title">
        <header>
          <h2 id="practice-drawer-title">{mode === "settings" ? "练习设置" : "学习结果"}</h2>
          <button type="button" aria-label={`关闭${mode === "settings" ? "练习设置" : "学习结果"}`} onClick={onClose}>
            <X size={19} weight="bold" aria-hidden="true" />
          </button>
        </header>

        {mode === "settings" ? (
          <>
            <div className="practice-drawer-content practice-settings-form">
              <label>
                <span>课程</span>
                <select aria-label="选择课程" value={courseId} onChange={(event) => onCourseChange(event.target.value)}>
                  {courses.map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}
                </select>
              </label>
              <label>
                <span>知识点</span>
                <select aria-label="选择知识点" value={pointId} onChange={(event) => onPointChange(event.target.value)}>
                  {points.map((point) => <option key={point.id} value={point.id}>{point.title}</option>)}
                </select>
              </label>
              <fieldset>
                <legend>题量</legend>
                <div className="practice-segmented-control">
                  {[3, 5, 8, 10].map((count) => (
                    <button type="button" key={count} aria-pressed={questionCount === count} onClick={() => onQuestionCountChange(count)}>{count} 题</button>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend>难度</legend>
                <div className="practice-difficulty-options">
                  {([
                    ["adaptive", "智能适配", "根据掌握度和弱点自动选择"],
                    ["easy", "基础", "巩固定义和核心概念"],
                    ["medium", "中等", "检查理解与概念应用"],
                    ["hard", "进阶", "综合推理和迁移应用"]
                  ] as const).map(([value, title, detail]) => (
                    <button type="button" key={value} aria-pressed={difficulty === value} onClick={() => onDifficultyChange(value)}>
                      <span>{title}</span><small>{detail}</small>
                    </button>
                  ))}
                </div>
              </fieldset>
              {error ? <p className="practice-local-error" role="alert">{error}</p> : null}
            </div>
            <footer>
              <span>{points.find((point) => point.id === pointId)?.title || "请选择知识点"} · {questionCount} 题</span>
              <button type="button" disabled={!canGenerate || isGenerating} onClick={onGenerate}>
                <ArrowClockwise size={17} weight="bold" aria-hidden="true" />
                {isGenerating ? "正在生成" : session ? "生成新练习" : "开始针对性练习"}
              </button>
            </footer>
          </>
        ) : (
          <div className="practice-drawer-content practice-result-detail">
            <section>
              <span>闭环更新</span>
              <h3>{closure?.path_update_status === "replanned" ? "学习路径已按本次结果重排" : "本次练习已写入学习状态"}</h3>
              <div className="practice-result-facts">
                <span><CheckCircle size={17} weight="duotone" aria-hidden="true" />新增弱点 {closure?.weaknesses_added ?? 0}</span>
                <span><CheckCircle size={17} weight="duotone" aria-hidden="true" />更新弱点 {closure?.weaknesses_updated ?? 0}</span>
              </div>
              <Link to={`${PATHS.path}?course_id=${session?.course_id ?? ""}`}>{closure?.path_update_status === "replanned" ? "查看更新后的路径" : "前往学习路径"}</Link>
            </section>
            <section>
              <span>推荐资源</span>
              <h3>针对本次薄弱点继续学习</h3>
              {recommendedResources.length > 0 ? recommendedResources.map((resource) => (
                <Link className="practice-recommended-resource" key={resource.id} to={`${PATHS.studio}?course_id=${resource.course_id}&resource_id=${resource.id}`}>
                  <BookOpenText size={18} weight="duotone" aria-hidden="true" />
                  <span><strong>{resource.title}</strong><small>{resource.resource_type}</small></span>
                </Link>
              )) : <p>本次没有可匹配的推荐资源，不会生成虚假推荐。</p>}
            </section>
            <section>
              <span>协作轨迹</span>
              <h3>评分与路径回流依据</h3>
              <AgentTraceDisclosure traceId={session?.agent_trace_id} label="查看 AssessmentGraph" />
              <AgentTraceDisclosure traceId={closure?.path_agent_trace_id} label="查看 PathPlanningGraph" />
            </section>
          </div>
        )}
      </aside>
    </ModalFrame>
  );
}
