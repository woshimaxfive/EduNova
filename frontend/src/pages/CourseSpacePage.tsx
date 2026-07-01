import {
  ArrowLeft,
  ChatCircleText,
  CheckCircle,
  FileText,
  Sparkle,
  Target
} from "@phosphor-icons/react";
import { Link, useParams } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { LearningCanvas } from "../components/canvas/LearningCanvas";
import { EvidenceLayer } from "../components/evidence/EvidenceLayer";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { StudioDock } from "../components/studio/StudioDock";
import { demoLearningSpace } from "../data/demoLearningSpace";

const courseThreads = [
  "监督学习这一章怎么安排复习？",
  "把神经网络薄弱点整理成练习",
  "解释泛化能力和过拟合的区别"
];

export function CourseSpacePage() {
  const { courseId } = useParams();
  const snapshot = demoLearningSpace;
  const canvasSnapshot = {
    ...snapshot,
    currentCourse: {
      ...snapshot.currentCourse,
      title: `${snapshot.currentCourse.title}知识画布`
    }
  };

  return (
    <LearningSpaceShell>
      <div className="course-space">
        <header className="course-space-hero">
          <Link className="course-back-link" to={PATHS.app}>
            <ArrowLeft size={17} weight="bold" aria-hidden="true" />
            <span>回到学习主页</span>
          </Link>
          <div className="course-space-title">
            <p className="section-kicker">课程空间 · {courseId ?? "course-ai"}</p>
            <h1>{snapshot.currentCourse.title}</h1>
            <p>{snapshot.currentCourse.description} 这里承载课程内对话、资料、路径、引用、Agent 轨迹和 Studio 输出。</p>
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
                <p className="section-kicker">课程对话</p>
                <h2>围绕这门课继续问</h2>
              </div>
            </div>

            <div className="course-thread-list" aria-label="课程内历史对话">
              {courseThreads.map((thread) => (
                <button type="button" key={thread}>
                  {thread}
                </button>
              ))}
            </div>

            <article className="course-answer">
              <p className="course-answer-label">AI 辅导回答</p>
              <h2>监督学习先抓住“数据、目标、泛化”三件事</h2>
              <p>
                先用课程资料里的例子区分训练集和测试集，再把过拟合、泛化误差和正则化连起来。回答下方保留引用、路径建议和
                Agent 过程，后续接入真实 RAG 后这里会替换为流式回答。
              </p>
              <div className="answer-action-row" aria-label="回答展开入口">
                <button type="button">
                  <FileText size={17} weight="duotone" aria-hidden="true" />
                  <span>引用来源</span>
                </button>
                <button type="button">
                  <Target size={17} weight="duotone" aria-hidden="true" />
                  <span>学习路径</span>
                </button>
                <button type="button">
                  <Sparkle size={17} weight="duotone" aria-hidden="true" />
                  <span>Agent 过程</span>
                </button>
              </div>
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
                <p className="section-kicker">今日建议</p>
                <h2>下一步学习</h2>
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
          </aside>
        </section>

        <LearningCanvas snapshot={canvasSnapshot} />

        <div className="course-space-secondary">
          <StudioDock outputs={snapshot.studioOutputs} />
          <EvidenceLayer snapshot={snapshot} />
        </div>
      </div>
    </LearningSpaceShell>
  );
}
