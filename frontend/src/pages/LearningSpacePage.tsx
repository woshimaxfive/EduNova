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
  Plus,
  Sparkle,
  X
} from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { buildCoursePath } from "../app/routePaths";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";

const homeConversations = [
  {
    id: "home-1",
    title: "神经网络反向传播怎么复习",
    meta: "18 分钟前"
  },
  {
    id: "home-2",
    title: "把期末题按知识点分组",
    meta: "昨晚"
  },
  {
    id: "home-3",
    title: "我适合先刷题还是先补概念",
    meta: "周一"
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
    next: "继续复习"
  },
  {
    id: "course-final",
    title: "期末冲刺课",
    progress: "草稿",
    focus: "由 3 份资料生成",
    next: "补章节"
  },
  {
    id: "course-python",
    title: "Python 基础补齐",
    progress: "12%",
    focus: "列表、函数、文件读取",
    next: "做练习"
  }
];

export function LearningSpacePage() {
  const [prompt, setPrompt] = useState("");
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);

  return (
    <LearningSpaceShell>
      <div className="learning-home">
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <section className="home-history-rail" aria-label="历史对话">
          <div className="home-rail-heading">
            <span>历史对话</span>
            <ClockCounterClockwise size={18} weight="duotone" aria-hidden="true" />
          </div>
          <button className="new-chat-button" type="button">
            <Plus size={17} weight="bold" aria-hidden="true" />
            <span>新建对话</span>
          </button>
          <button className="history-search-button" type="button">
            <MagnifyingGlass size={16} weight="duotone" aria-hidden="true" />
            <span>搜索历史</span>
          </button>
          <div className="home-thread-list">
            {homeConversations.map((conversation) => (
              <button className="home-thread" key={conversation.id} type="button">
                <strong>{conversation.title}</strong>
                <small>{conversation.meta}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="home-chat-stage" aria-label="AI 学习入口">
          <div className="home-hero-copy">
            <p className="home-kicker">EduNova</p>
            <h1>
              <span>嗨，同学，</span>
              <span>准备好一起学习了吗？</span>
            </h1>
            <p>上传课件、电子书或期末题，然后直接问。需要时再把这段对话变成一门课程。</p>
          </div>

          <div className="conversation-composer">
            <textarea
              aria-label="学习问题输入"
              value={prompt}
              rows={3}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="问我怎么复习，或者说：用这些资料生成一门期末复习课"
            />
            <div className="composer-actions">
              <div className="composer-toolbar" aria-label="输入工具">
                <button type="button" aria-label="上传资料">
                  <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
                  <span>上传</span>
                </button>
                <button type="button" aria-label="打开资料库" onClick={() => setIsLibraryOpen(true)}>
                  <FolderOpen size={18} weight="duotone" aria-hidden="true" />
                  <span>资料库</span>
                </button>
                <button type="button" onClick={() => setIsCourseDialogOpen(true)}>
                  <Sparkle size={18} weight="duotone" aria-hidden="true" />
                  <span>生成课程</span>
                </button>
                <button type="button" aria-label="联网搜索">
                  <MagnifyingGlass size={18} weight="duotone" aria-hidden="true" />
                  <span>搜索</span>
                </button>
                <button type="button" aria-label="深度思考">
                  <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
                  <span>思考</span>
                </button>
                <button type="button">
                  <Microphone size={18} weight="duotone" aria-hidden="true" />
                  <span>语音</span>
                </button>
              </div>
              <button className="ask-button" type="button">
                <ArrowRight size={18} weight="bold" aria-hidden="true" />
                <span>发送</span>
              </button>
            </div>
          </div>

          <div className="selected-materials-note">
            <LinkSimple size={16} weight="duotone" aria-hidden="true" />
            <span>已准备 3 份资料，回答时会像联网搜索一样显示来源。</span>
          </div>

          <section className="recent-course-strip" aria-label="最近学习">
            <div className="recent-course-heading">
              <span>最近学习</span>
              <button type="button">查看全部</button>
            </div>
            <ul className="recent-course-list" aria-label="最近学习列表">
              {recentCourses.map((course) => (
                <li key={course.id}>
                  <Link className="recent-course" to={buildCoursePath(course.id)}>
                    <BookOpen size={18} weight="duotone" aria-hidden="true" />
                    <span>
                      <strong>{course.title}</strong>
                      <small>{course.focus}</small>
                    </span>
                    <em>{course.progress}</em>
                    <span className="course-next">{course.next}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </section>
      </div>

      {isCourseDialogOpen ? <CourseGenerationDialog onClose={() => setIsCourseDialogOpen(false)} /> : null}
      {isLibraryOpen ? <MaterialLibraryDrawer onClose={() => setIsLibraryOpen(false)} /> : null}
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

function MaterialLibraryDrawer({ onClose }: CourseGenerationDialogProps) {
  return (
    <div className="course-dialog-backdrop">
      <section className="material-drawer" role="dialog" aria-modal="true" aria-labelledby="library-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭资料库" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <p className="home-kicker">资料库</p>
          <h2 id="library-dialog-title">选择本次对话参考</h2>
          <p>资料独立保存在资料库里。可以先用于主页问答，也可以稍后加入某门课程。</p>
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
      </section>
    </div>
  );
}
