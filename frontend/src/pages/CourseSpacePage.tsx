import {
  ArrowLeft,
  ChartLineUp,
  ChatCircleText,
  CheckCircle,
  FileText,
  ListChecks,
  Sparkle,
  Target
} from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { LearningCanvas } from "../components/canvas/LearningCanvas";
import { EvidenceLayer } from "../components/evidence/EvidenceLayer";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { StudioDock } from "../components/studio/StudioDock";
import { demoLearningSpace } from "../data/demoLearningSpace";

const courseThreads = [
  "监督学习这一章怎么安排复习？",
  "把神经网络薄弱点整理成练习",
  "解释泛化能力和过拟合的区别"
];

const courseActionLinks = [
  { label: "进入 AI 辅导", to: PATHS.tutor, icon: ChatCircleText },
  { label: "开始练习", to: PATHS.practice, icon: ListChecks },
  { label: "查看学习报告", to: PATHS.reports, icon: ChartLineUp }
];

type AnswerPanelKind = "citations" | "path" | "agent";

export function CourseSpacePage() {
  const [activeThread, setActiveThread] = useState(courseThreads[0]);
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<AnswerPanelKind>("citations");
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const snapshot = demoLearningSpace;
  const canvasSnapshot = {
    ...snapshot,
    currentCourse: {
      ...snapshot.currentCourse,
      title: `${snapshot.currentCourse.title}知识画布`
    }
  };

  return (
    <LearningSpaceShell hideTopNavigation>
      <section className={isHistoryCollapsed ? "app-workspace-layout history-collapsed" : "app-workspace-layout"}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar
          isCollapsed={isHistoryCollapsed}
          conversations={courseThreads.map((title, index) => ({ id: `course-thread-${index}`, title, meta: "课程内" }))}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onSelectConversation={(conversation) => setActiveThread(conversation.title)}
        />
        <section className="route-main-surface course-route-surface">
          <div className="course-space">
            <header className="course-space-hero">
              <Link className="course-back-link" to={PATHS.app}>
                <ArrowLeft size={17} weight="bold" aria-hidden="true" />
                <span>回到学习主页</span>
              </Link>
              <div className="course-space-title">
                <h1>{snapshot.currentCourse.title}</h1>
                <p>{snapshot.currentCourse.description} 课程对话、资料、路径和引用都在这里。</p>
              </div>
              <dl className="course-space-metrics" aria-label="课程状态">
                <div>
                  <dt>进度</dt>
                  <dd>{snapshot.currentCourse.progressPercent}%</dd>
                </div>
                <div>
                  <dt>资料</dt>
                  <dd>{snapshot.materials.length}</dd>
                </div>
                <div>
                  <dt>引用</dt>
                  <dd>{snapshot.citations.length}</dd>
                </div>
              </dl>
            </header>

            <section className="course-space-grid">
              <section className="course-chat-panel" role="region" aria-label="课程对话空间">
                <div className="course-panel-heading">
                  <span className="course-panel-icon" aria-hidden="true">
                    <ChatCircleText size={20} weight="duotone" />
                  </span>
                  <div>
                    <h2>继续问</h2>
                  </div>
                </div>

                <div className="course-thread-list" aria-label="课程内历史对话">
                  {courseThreads.map((thread) => (
                    <button
                      className={activeThread === thread ? "active" : ""}
                      type="button"
                      key={thread}
                      aria-pressed={activeThread === thread}
                      onClick={() => setActiveThread(thread)}
                    >
                      {thread}
                    </button>
                  ))}
                </div>

                <article className="course-answer">
                  <p className="course-answer-label">AI 辅导回答</p>
                  <h2>监督学习先抓住“数据、目标、泛化”三件事</h2>
                  <p>先区分训练集和测试集，再把过拟合、泛化误差和正则化连起来。</p>
                  <div className="answer-action-row" aria-label="回答展开入口">
                    <button
                      className={activeAnswerPanel === "citations" ? "active" : ""}
                      type="button"
                      aria-pressed={activeAnswerPanel === "citations"}
                      onClick={() => setActiveAnswerPanel("citations")}
                    >
                      <FileText size={17} weight="duotone" aria-hidden="true" />
                      <span>引用来源</span>
                    </button>
                    <button
                      className={activeAnswerPanel === "path" ? "active" : ""}
                      type="button"
                      aria-pressed={activeAnswerPanel === "path"}
                      onClick={() => setActiveAnswerPanel("path")}
                    >
                      <Target size={17} weight="duotone" aria-hidden="true" />
                      <span>学习路径</span>
                    </button>
                    <button
                      className={activeAnswerPanel === "agent" ? "active" : ""}
                      type="button"
                      aria-pressed={activeAnswerPanel === "agent"}
                      onClick={() => setActiveAnswerPanel("agent")}
                    >
                      <Sparkle size={17} weight="duotone" aria-hidden="true" />
                      <span>Agent 过程</span>
                    </button>
                  </div>
                  <AnswerDetailPanel activePanel={activeAnswerPanel} />
                  <div className="answer-citation-strip" aria-label="回答引用预览">
                    {snapshot.citations.map((citation) => (
                      <span key={citation.id}>{citation.sourceTitle}</span>
                    ))}
                  </div>
                </article>

                <label className="course-composer">
                  <span>课程问题输入</span>
                  <textarea rows={3} placeholder="继续问这门课，例如：给我生成监督学习 10 分钟复习路线" />
                </label>
              </section>

              <aside className="course-context-panel" aria-label="课程学习上下文">
                <div className="course-panel-heading">
                  <span className="course-panel-icon" aria-hidden="true">
                    <CheckCircle size={20} weight="duotone" />
                  </span>
                  <div>
                    <h2>下一步</h2>
                  </div>
                </div>
                <ol className="course-task-list" aria-label="课程任务">
                  {snapshot.todayTasks.map((task) => (
                    <li key={task.id} className={task.status}>
                      <strong>{task.title}</strong>
                      <span>{task.type}</span>
                    </li>
                  ))}
                </ol>
                <nav className="course-action-links" aria-label="课程行动入口">
                  {courseActionLinks.map((action) => {
                    const Icon = action.icon;

                    return (
                      <Link key={action.to} to={action.to}>
                        <Icon size={17} weight="duotone" aria-hidden="true" />
                        <span>{action.label}</span>
                      </Link>
                    );
                  })}
                </nav>
              </aside>
            </section>

            <LearningCanvas snapshot={canvasSnapshot} />

            <div className="course-space-secondary">
              <StudioDock outputs={snapshot.studioOutputs} />
              <EvidenceLayer snapshot={snapshot} />
            </div>
          </div>
        </section>
      </section>
    </LearningSpaceShell>
  );
}

type AnswerDetailPanelProps = {
  activePanel: AnswerPanelKind;
};

function AnswerDetailPanel({ activePanel }: AnswerDetailPanelProps) {
  if (activePanel === "path") {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>建议路径</strong>
        <p>先复习训练集、测试集和目标函数，再进入过拟合、正则化和泛化误差，最后用 10 分钟练习巩固。</p>
      </section>
    );
  }

  if (activePanel === "agent") {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>Agent 过程</strong>
        <p>RetrieverAgent 先检索课程资料，PlannerAgent 生成复习顺序，TutorAgent 再把结论写成可追问回答。</p>
      </section>
    );
  }

  return (
    <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
      <strong>引用来源</strong>
      <p>AI 导论内置讲义和期末复习题样例会作为回答依据。</p>
    </section>
  );
}
