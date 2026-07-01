import {
  ArrowRight,
  BookOpen,
  ChatCircleText,
  CheckCircle,
  ClockCounterClockwise,
  FileArrowUp,
  FolderOpen,
  LinkSimple,
  MagnifyingGlass,
  Microphone,
  Sparkle,
  X
} from "@phosphor-icons/react";
import { useState } from "react";

import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";

const homeConversations = [
  {
    id: "home-1",
    title: "神经网络反向传播怎么复习",
    meta: "主页对话 · 18 分钟前",
    status: "可移入课程"
  },
  {
    id: "home-2",
    title: "把期末题按知识点分组",
    meta: "主页对话 · 昨晚",
    status: "已引用 2 份资料"
  },
  {
    id: "home-3",
    title: "我适合先刷题还是先补概念",
    meta: "画像相关 · 周一",
    status: "独立保留"
  }
];

const libraryMaterials = [
  {
    id: "mat-1",
    title: "人工智能导论课件",
    type: "PPTX",
    detail: "42 页 · 已解析",
    selected: true
  },
  {
    id: "mat-2",
    title: "期末复习题 2025",
    type: "PDF",
    detail: "18 道题 · 已切片",
    selected: true
  },
  {
    id: "mat-3",
    title: "神经网络课堂讲义",
    type: "DOCX",
    detail: "7 个章节 · 可加入课程",
    selected: true
  }
];

const recentCourses = [
  {
    id: "course-ai",
    title: "人工智能导论",
    progress: "47%",
    focus: "监督学习与神经网络",
    next: "继续复习反向传播"
  },
  {
    id: "course-final",
    title: "期末冲刺课",
    progress: "草稿",
    focus: "由 3 份资料生成",
    next: "补充章节结构"
  },
  {
    id: "course-python",
    title: "Python 基础补齐",
    progress: "12%",
    focus: "列表、函数、文件读取",
    next: "生成练习题"
  }
];

const answerSources = [
  "人工智能导论课件 · 第 4 章",
  "神经网络课堂讲义 · 反向传播",
  "期末复习题 2025 · 第 6 题"
];

export function LearningSpacePage() {
  const [prompt, setPrompt] = useState("我想用这些资料生成一门期末复习课");
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);

  return (
    <LearningSpaceShell>
      <div className="learning-home">
        <section className="home-history-rail" aria-label="主页历史">
          <div className="home-rail-heading">
            <ClockCounterClockwise size={19} weight="duotone" aria-hidden="true" />
            <span>主页历史</span>
          </div>
          <button className="new-chat-button" type="button">
            <ChatCircleText size={17} weight="duotone" aria-hidden="true" />
            <span>新建对话</span>
          </button>
          <div className="home-thread-list">
            {homeConversations.map((conversation) => (
              <button className="home-thread" key={conversation.id} type="button">
                <strong>{conversation.title}</strong>
                <small>{conversation.meta}</small>
                <span>{conversation.status}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="home-chat-stage" aria-label="AI 学习对话">
          <div className="home-hero-copy">
            <p className="section-kicker">EduNova 学习主页</p>
            <h1>上传资料，开始和你的课程对话</h1>
            <p>
              先把资料、问题和目标放进主页。它可以独立保存，也可以在生成课程后移入某个课程空间。
            </p>
          </div>

          <div className="conversation-composer">
            <div className="composer-toolbar" aria-label="输入工具">
              <button type="button">
                <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
                <span>上传资料</span>
              </button>
              <button type="button">
                <FolderOpen size={18} weight="duotone" aria-hidden="true" />
                <span>选择资料</span>
              </button>
              <button type="button">
                <MagnifyingGlass size={18} weight="duotone" aria-hidden="true" />
                <span>联网搜索</span>
              </button>
              <button type="button">
                <Microphone size={18} weight="duotone" aria-hidden="true" />
                <span>语音</span>
              </button>
            </div>
            <textarea
              aria-label="学习问题输入"
              value={prompt}
              rows={4}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="上传课件、电子书或期末题，然后直接问：帮我生成一门复习课"
            />
            <div className="composer-actions">
              <button className="generate-course-button" type="button" onClick={() => setIsCourseDialogOpen(true)}>
                <Sparkle size={18} weight="fill" aria-hidden="true" />
                <span>生成课程</span>
              </button>
              <button className="ask-button" type="button">
                <ArrowRight size={18} weight="bold" aria-hidden="true" />
                <span>发送</span>
              </button>
            </div>
          </div>

          <article className="answer-preview" aria-label="回答预览">
            <div className="answer-avatar" aria-hidden="true">
              <Sparkle size={18} weight="fill" />
            </div>
            <div>
              <strong>可以，我会先根据 3 份资料整理课程骨架。</strong>
              <p>
                初步建议拆成“概念速通、算法理解、神经网络、期末题训练”四段。资料不足的地方会标记为低依据，不会伪装成课程结论。
              </p>
              <div className="answer-source-row" aria-label="引用来源">
                {answerSources.map((source) => (
                  <button key={source} type="button">
                    <LinkSimple size={15} weight="duotone" aria-hidden="true" />
                    <span>{source}</span>
                  </button>
                ))}
              </div>
              <div className="answer-process-row">
                <button type="button">展开学习路径建议</button>
                <button type="button">查看 Agent 过程</button>
              </div>
            </div>
          </article>
        </section>

        <aside className="home-context-rail" role="region" aria-label="资料库轻入口">
          <div className="context-heading">
            <p className="section-kicker">资料库</p>
            <h2>本次对话参考</h2>
            <span>已选择 3 份资料</span>
          </div>
          <div className="material-stack">
            {libraryMaterials.map((material) => (
              <button className={material.selected ? "material-chip selected" : "material-chip"} key={material.id} type="button">
                <span>{material.type}</span>
                <strong>{material.title}</strong>
                <small>{material.detail}</small>
              </button>
            ))}
          </div>
          <button className="context-link-button" type="button">
            <FolderOpen size={17} weight="duotone" aria-hidden="true" />
            <span>打开资料库</span>
          </button>
        </aside>

        <section className="recent-course-strip" aria-label="最近课程">
          <div className="recent-course-heading">
            <p className="section-kicker">最近课程</p>
            <h2>进入课程后再看画布、路径和资源</h2>
          </div>
          <div className="recent-course-list">
            {recentCourses.map((course) => (
              <button className="recent-course" key={course.id} type="button">
                <BookOpen size={19} weight="duotone" aria-hidden="true" />
                <span>
                  <strong>{course.title}</strong>
                  <small>{course.focus}</small>
                </span>
                <em>{course.progress}</em>
                <span className="course-next">{course.next}</span>
              </button>
            ))}
          </div>
        </section>
      </div>

      {isCourseDialogOpen ? <CourseGenerationDialog onClose={() => setIsCourseDialogOpen(false)} /> : null}
    </LearningSpaceShell>
  );
}

type CourseGenerationDialogProps = {
  onClose: () => void;
};

function CourseGenerationDialog({ onClose }: CourseGenerationDialogProps) {
  return (
    <div className="course-dialog-backdrop">
      <section className="course-dialog" role="dialog" aria-modal="true" aria-labelledby="course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <p className="section-kicker">生成课程</p>
          <h2 id="course-dialog-title">生成课程</h2>
          <p>这一步会把主页资料整理成课程空间。主页对话可以移入课程，也可以继续独立保留。</p>
        </div>
        <label className="dialog-field">
          <span>课程名称</span>
          <input aria-label="课程名称" defaultValue="人工智能导论期末复习" />
        </label>
        <div className="dialog-materials">
          <div>
            <strong>已选择 3 份资料</strong>
            <small>课件、讲义和期末题会先进入资料库，再关联到新课程。</small>
          </div>
          {libraryMaterials.map((material) => (
            <span key={material.id}>
              <CheckCircle size={16} weight="duotone" aria-hidden="true" />
              {material.title}
            </span>
          ))}
        </div>
        <button className="dialog-primary-button" type="button">
          创建课程草案
        </button>
      </section>
    </div>
  );
}
