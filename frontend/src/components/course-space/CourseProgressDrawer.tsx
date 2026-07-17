import { ArrowClockwise, ArrowRight, CheckCircle, Circle, Sparkle, X } from "@phosphor-icons/react";

import {
  type CourseWeaknessReviewAction,
  type CourseLearnerContext,
  type CourseWeaknessReviewItem,
  type CourseWeaknessSummary
} from "../../api/courses";
import { type CourseLoopSummary, type StudyStep } from "../../features/course-space/a3Loop";
import { AgentTraceDisclosure } from "../evidence/AgentTraceDisclosure";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { studyStepStatusLabels } from "./courseSpaceLabels";
import { ModalFrame } from "../primitives/Dialog";

type CourseProgressDrawerProps = {
  open: boolean;
  summary: CourseLoopSummary;
  steps: StudyStep[];
  traceId?: string | null;
  weaknessSummary?: CourseWeaknessSummary;
  learnerContext?: CourseLearnerContext;
  weaknessItems: CourseWeaknessReviewItem[];
  updatingWeaknessItemId: string | null;
  learningStateError: boolean;
  weaknessFeedback: string | null;
  isRefreshing: boolean;
  refreshWarning: string | null;
  onClose: () => void;
  onRefresh: () => void;
  onWeaknessAction: (item: CourseWeaknessReviewItem, action: CourseWeaknessReviewAction) => void;
  onPracticeWeakness: (item: CourseWeaknessReviewItem) => void;
  onOpenWeaknessResource: (item: CourseWeaknessReviewItem, resourceId?: string) => void;
};

export function CourseProgressDrawer({
  open,
  summary,
  steps,
  traceId,
  weaknessSummary,
  learnerContext,
  weaknessItems,
  updatingWeaknessItemId,
  learningStateError,
  weaknessFeedback,
  isRefreshing,
  refreshWarning,
  onClose,
  onRefresh,
  onWeaknessAction,
  onPracticeWeakness,
  onOpenWeaknessResource
}: CourseProgressDrawerProps) {
  if (!open) return null;
  const activeWeaknessCount = weaknessItems.filter((item) => ["pending", "confirmed", "reviewing"].includes(item.status)).length;

  return (
    <ModalFrame title="学习进度" layerClassName="course-drawer-layer" onClose={onClose}>
      <aside className="course-progress-drawer" aria-labelledby="course-progress-title">
        <header className="course-drawer-header">
          <h2 id="course-progress-title">学习进度</h2>
          <div className="course-drawer-header-actions">
            <button
              type="button"
              aria-label={isRefreshing ? "正在刷新学习进度" : "刷新学习进度"}
              disabled={isRefreshing}
              onClick={onRefresh}
            >
              <ArrowClockwise className={isRefreshing ? "spinning" : ""} size={18} weight="bold" aria-hidden="true" />
            </button>
            <button type="button" aria-label="关闭学习进度" onClick={onClose}>
              <X size={19} weight="bold" aria-hidden="true" />
            </button>
          </div>
        </header>

        <div className="course-progress-summary">
          <span>{isRefreshing ? "正在同步最新学习状态" : "当前目标"}</span>
          <strong>{summary.currentGoal}</strong>
          <p>{summary.evidenceLine}</p>
          <div>
            <span>下一步</span>
            <strong>{summary.nextAction}</strong>
            <em>掌握度 {summary.progressLabel}</em>
          </div>
          <InlineFeedback message={refreshWarning} tone="warning" className="course-progress-sync-feedback" />
        </div>

        <section className="course-progress-section" aria-label="课程画像摘要">
          <div className="course-progress-section-heading">
            <h3>课程画像</h3>
            <span>总画像 + 本课程实时状态</span>
          </div>
          <dl className="course-progress-counts">
            <div><dt>画像完整度</dt><dd>{Math.round(learnerContext?.completeness_score ?? 0)}%</dd></div>
            <div><dt>可信维度</dt><dd>{learnerContext?.trusted_dimensions.length ?? 0}</dd></div>
            <div><dt>课程掌握度</dt><dd>{learnerContext?.mastery_average === null || learnerContext?.mastery_average === undefined ? "未评估" : `${Math.round(learnerContext.mastery_average)}%`}</dd></div>
            <div><dt>课程弱点</dt><dd>{learnerContext?.active_weaknesses.length ?? 0}</dd></div>
          </dl>
          <p className="course-progress-empty">
            总画像提供稳定的学习方式与目标，本课程掌握度、弱点和当前任务只在这门课内生效。
          </p>
        </section>

        <section className="course-progress-section" aria-label="A3 学习步骤">
          <div className="course-progress-section-heading">
            <h3>学习步骤</h3>
            <span>依据真实学习行为更新</span>
          </div>
          <ol className="course-progress-steps">
            {steps.map((step) => {
              const Icon = step.status === "done" ? CheckCircle : step.status === "next" ? Sparkle : Circle;
              return (
                <li className={step.status} key={step.key}>
                  <Icon size={18} weight={step.status === "empty" ? "regular" : "duotone"} aria-hidden="true" />
                  <div>
                    <span>{studyStepStatusLabels[step.status]}</span>
                    <strong>{step.label}</strong>
                    <p>{step.description}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>

        <section className="course-progress-section" aria-label="待复习弱点">
          <div className="course-progress-section-heading">
            <h3>待复习弱点</h3>
            <span>{activeWeaknessCount} 项待处理</span>
          </div>
          <dl className="course-progress-counts" aria-label="弱点统计">
            <div><dt>待确认</dt><dd>{weaknessSummary?.pending_count ?? 0}</dd></div>
            <div><dt>待复习</dt><dd>{weaknessSummary?.confirmed_count ?? 0}</dd></div>
            <div><dt>复习中</dt><dd>{weaknessSummary?.reviewing_count ?? 0}</dd></div>
            <div><dt>已攻克</dt><dd>{weaknessSummary?.completed_count ?? 0}</dd></div>
            <div><dt>候选证据</dt><dd>{weaknessSummary?.candidate_event_count ?? 0}</dd></div>
          </dl>
          <InlineFeedback
            message={learningStateError ? "课程学习状态读取失败，请稍后重试。" : weaknessFeedback}
            tone="warning"
            className="course-inline-feedback"
          />
          {weaknessItems.length > 0 ? (
            <ul className="course-progress-weaknesses">
              {weaknessItems.map((item) => {
                const due = isReviewDue(item.next_review_at);
                return (
                <li key={item.id}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{weaknessStatusLabel(item.status, due)}</span>
                    {formatReviewDate(item.next_review_at) ? <small>下次复习 {formatReviewDate(item.next_review_at)}</small> : null}
                    {item.diagnosis?.misconception ? <p><b>当前错因：</b>{item.diagnosis.misconception}</p> : null}
                    {item.diagnosis?.missing_concepts.length ? <p><b>待补概念：</b>{item.diagnosis.missing_concepts.join("、")}</p> : null}
                    {item.diagnosis?.recommended_action ? <p><b>复习建议：</b>{item.diagnosis.recommended_action}</p> : null}
                    {item.diagnosis?.latest_score !== null && item.diagnosis?.latest_score !== undefined ? (
                      <small>
                        再测 {item.diagnosis.latest_score} 分
                        {item.diagnosis.baseline_score !== null ? ` · 起点 ${item.diagnosis.baseline_score} 分` : ""}
                        {item.diagnosis.improvement !== null ? ` · ${item.diagnosis.improvement >= 0 ? "提升" : "变化"} ${item.diagnosis.improvement} 分` : ""}
                      </small>
                    ) : null}
                  </div>
                  <div className="course-progress-weakness-actions" aria-label={`${item.title} 操作`}>
                    {weaknessActions(item).map((action) => (
                      <button
                        key={action.action}
                        type="button"
                        aria-label={`${action.label} ${item.title}`}
                        disabled={updatingWeaknessItemId !== null}
                        onClick={() => onWeaknessAction(item, action.action)}
                      >
                        <span>{updatingWeaknessItemId === item.id ? "更新中" : action.label}</span>
                        <ArrowRight size={13} weight="bold" aria-hidden="true" />
                      </button>
                    ))}
                    {item.status === "confirmed" || item.status === "reviewing" || due ? (
                      <button type="button" onClick={() => onPracticeWeakness(item)}>
                        <span>{due ? "到期复习" : "针对性再测"}</span>
                        <ArrowRight size={13} weight="bold" aria-hidden="true" />
                      </button>
                    ) : null}
                    {item.status === "confirmed" || item.status === "reviewing" ? (
                      <button type="button" onClick={() => onOpenWeaknessResource(item, item.recommended_resources[0]?.id)}>
                        <span>{item.recommended_resources.length > 0 ? "学习推荐资源" : "生成复习资源"}</span>
                        <ArrowRight size={13} weight="bold" aria-hidden="true" />
                      </button>
                    ) : null}
                  </div>
                </li>
                );
              })}
            </ul>
          ) : learningStateError ? null : <p className="course-progress-empty">完成问答或练习后，待确认弱点会出现在这里。</p>}
        </section>

        <AgentTraceDisclosure traceId={traceId} label="查看 CourseBuilderGraph" />
      </aside>
    </ModalFrame>
  );
}

function weaknessStatusLabel(status: string, due = false) {
  if (status === "confirmed") return "待复习";
  if (status === "reviewing") return "复习中";
  if (status === "completed") return due ? "到期复习" : "已攻克";
  if (status === "dismissed") return "已忽略";
  return "待确认";
}

function weaknessActions(item: CourseWeaknessReviewItem): Array<{ action: CourseWeaknessReviewAction; label: string }> {
  if (item.status === "pending") return [{ action: "confirm", label: "确认" }, { action: "dismiss", label: "忽略" }];
  if (item.status === "confirmed") return [{ action: "start", label: "开始复习" }, { action: "dismiss", label: "忽略" }];
  if (item.status === "reviewing") return [{ action: "dismiss", label: "忽略" }];
  if (item.status === "completed") return [{ action: "dismiss", label: "移除" }];
  return [];
}

function formatReviewDate(value: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

function isReviewDue(value: string | null) {
  if (!value) return false;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) && timestamp <= Date.now();
}
