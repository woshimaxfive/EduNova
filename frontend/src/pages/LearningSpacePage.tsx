import {
  ArrowRight,
  BookOpen,
  CaretLeft,
  CaretRight,
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
  Student,
  X
} from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
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

type HomeMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export function LearningSpacePage() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<HomeMessage[]>([]);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isDeepThinkingEnabled, setIsDeepThinkingEnabled] = useState(false);
  const { notice, showNotice } = useActionNotice();
  const hasHomeThread = messages.length > 0;

  function openLibrary(message = "已打开资料库。") {
    setIsLibraryOpen(true);
    showNotice(message);
  }

  function handleSendQuestion() {
    const question = prompt.trim();

    if (!question) {
      showNotice("先输入一个学习问题。", "warning");
      return;
    }

    setMessages((current) => [
      ...current,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: question
      },
      {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: "可以先把资料按章节和题型拆开：先补核心概念，再用期末题做检索式复习。真实 AI 接入后，这里会流式展开并显示引用来源。"
      }
    ]);
    setPrompt("");
    showNotice("已生成演示回答，真实 AI 接入后会流式返回。", "success");
  }

  return (
    <LearningSpaceShell hideTopNavigation>
      <div className={["learning-home", isHistoryCollapsed ? "history-collapsed" : "", hasHomeThread ? "chat-active" : ""].filter(Boolean).join(" ")}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <section className="home-history-rail" aria-label="历史对话" data-collapsed={isHistoryCollapsed ? "true" : "false"}>
          <div className="home-sidebar-brand">
            <Link className="brand-mark home-brand" to={PATHS.app} aria-label="EduNova 首页">
              <span className="brand-symbol" aria-hidden="true">
                <Student size={22} weight="duotone" />
              </span>
              <span className="home-sidebar-label">EduNova</span>
            </Link>
            <button
              className="sidebar-collapse-button"
              type="button"
              aria-label={isHistoryCollapsed ? "展开侧栏" : "收起侧栏"}
              aria-expanded={!isHistoryCollapsed}
              onClick={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
            >
              {isHistoryCollapsed ? <CaretRight size={17} weight="bold" aria-hidden="true" /> : <CaretLeft size={17} weight="bold" aria-hidden="true" />}
            </button>
          </div>

          <nav className="home-sidebar-nav" aria-label="主页导航">
            <Link to={PATHS.app}>
              <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
              <span>学习空间</span>
            </Link>
            <Link to={PATHS.library}>
              <BookOpen size={18} weight="duotone" aria-hidden="true" />
              <span>资料库</span>
            </Link>
            <Link to={PATHS.studio}>
              <Sparkle size={18} weight="duotone" aria-hidden="true" />
              <span>Studio</span>
            </Link>
          </nav>

          <button
            className="new-chat-button"
            type="button"
            onClick={() => {
              setPrompt("");
              setMessages([]);
              showNotice("已新建一条主页独立对话。", "success");
            }}
          >
            <Plus size={17} weight="bold" aria-hidden="true" />
            <span>新建对话</span>
          </button>
          <button
            className="history-search-button"
            type="button"
            onClick={() => showNotice("历史搜索会在对话索引接口接入后开放。")}
          >
            <MagnifyingGlass size={16} weight="duotone" aria-hidden="true" />
            <span>搜索历史</span>
          </button>
          <div className="home-rail-heading">
            <span>最近</span>
            <ClockCounterClockwise size={18} weight="duotone" aria-hidden="true" />
          </div>
          <div className="home-thread-list">
            {homeConversations.map((conversation) => (
              <button
                className="home-thread"
                key={conversation.id}
                type="button"
                onClick={() => showNotice(`已切换到「${conversation.title}」演示对话。`)}
              >
                <strong>{conversation.title}</strong>
                <small>{conversation.meta}</small>
              </button>
            ))}
          </div>
        </section>

        <section className={hasHomeThread ? "home-chat-stage chat-active" : "home-chat-stage"} aria-label="AI 学习入口">
          {hasHomeThread ? (
            <section className="home-thread-stage" aria-label="主页对话">
              {messages.map((message) => (
                <article className={`home-message ${message.role}`} key={message.id}>
                  {message.role === "assistant" ? <span className="message-thinking">已思考若干秒</span> : null}
                  <p>{message.content}</p>
                </article>
              ))}
            </section>
          ) : (
            <div className="home-hero-copy">
              <p className="home-kicker">EduNova</p>
              <h1>
                <span>嗨，同学，</span>
                <span>准备好一起学习了吗？</span>
              </h1>
              <p>上传课件、电子书或期末题，然后直接问。需要时再把这段对话变成一门课程。</p>
            </div>
          )}

          <section className={hasHomeThread ? "composer-frame docked" : "composer-frame"} aria-label={hasHomeThread ? "底部学习输入" : "学习输入区"}>
            <div className="conversation-composer">
              <textarea
                aria-label="学习问题输入"
                value={prompt}
                rows={2}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="问我怎么复习，或者说：用这些资料生成一门期末复习课"
              />
              <div className="composer-actions">
                <div className="composer-toolbar" aria-label="输入工具">
                  <button
                    type="button"
                    aria-label="上传资料"
                    onClick={() => openLibrary("已打开资料库，真实上传会在资料解析接口接入后开放。")}
                  >
                    <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
                    <span>上传</span>
                  </button>
                  <button type="button" aria-label="打开资料库" onClick={() => openLibrary()}>
                    <FolderOpen size={18} weight="duotone" aria-hidden="true" />
                    <span>资料库</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsCourseDialogOpen(true);
                      showNotice("已打开生成课程面板。");
                    }}
                  >
                    <Sparkle size={18} weight="duotone" aria-hidden="true" />
                    <span>生成课程</span>
                  </button>
                  <button
                    type="button"
                    aria-label="联网搜索"
                    onClick={() => showNotice("联网搜索会作为可选增强接入，第一版先保留引用来源机制。")}
                  >
                    <MagnifyingGlass size={18} weight="duotone" aria-hidden="true" />
                    <span>搜索</span>
                  </button>
                  <button
                    className={isDeepThinkingEnabled ? "active" : ""}
                    type="button"
                    aria-label="深度思考"
                    aria-pressed={isDeepThinkingEnabled}
                    onClick={() => {
                      setIsDeepThinkingEnabled((enabled) => !enabled);
                      showNotice(isDeepThinkingEnabled ? "已关闭深度思考演示态。" : "已开启深度思考演示态。");
                    }}
                  >
                    <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
                    <span>思考</span>
                  </button>
                  <button type="button" aria-label="语音输入" onClick={() => showNotice("语音输入会在浏览器录音权限流程接入后开放。")}>
                    <Microphone size={18} weight="duotone" aria-hidden="true" />
                    <span>语音</span>
                  </button>
                </div>
                <button className="ask-button" type="button" onClick={handleSendQuestion}>
                  <ArrowRight size={18} weight="bold" aria-hidden="true" />
                  <span>发送</span>
                </button>
              </div>
            </div>
          </section>

          <div className="selected-materials-note">
            <LinkSimple size={16} weight="duotone" aria-hidden="true" />
            <span>已准备 3 份资料，回答时会像联网搜索一样显示来源。</span>
          </div>
          <ActionNotice notice={notice} className="home-action-notice" />

          {!hasHomeThread ? (
            <section className="recent-course-strip" aria-label="最近学习">
              <div className="recent-course-heading">
                <span>最近学习</span>
                <button type="button" onClick={() => showNotice("全部课程列表会在课程 API 接入后展示。")}>
                  查看全部
                </button>
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
          ) : null}
        </section>
      </div>

      {isCourseDialogOpen ? <CourseGenerationDialog onClose={() => setIsCourseDialogOpen(false)} showNotice={showNotice} /> : null}
      {isLibraryOpen ? (
        <MaterialLibraryDrawer onClose={() => setIsLibraryOpen(false)} onSelectMaterials={(count) => showNotice(`已选择 ${count} 份资料。`, "success")} />
      ) : null}
    </LearningSpaceShell>
  );
}

type CourseGenerationDialogProps = {
  onClose: () => void;
};

type CourseGenerationDialogWithNoticeProps = CourseGenerationDialogProps & {
  showNotice: (message: string, tone?: "info" | "success" | "warning") => void;
};

function CourseGenerationDialog({ onClose, showNotice }: CourseGenerationDialogWithNoticeProps) {
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
        <button className="dialog-primary-button" type="button" onClick={() => showNotice("已创建课程草案演示态，真实创建会接入课程 API。", "success")}>
          创建课程草案
        </button>
      </section>
    </div>
  );
}

type MaterialLibraryDrawerProps = CourseGenerationDialogProps & {
  onSelectMaterials: (count: number) => void;
};

function MaterialLibraryDrawer({ onClose, onSelectMaterials }: MaterialLibraryDrawerProps) {
  const selectedCount = libraryMaterials.filter((material) => material.selected).length;

  return (
    <div className="course-dialog-backdrop">
      <section className="material-drawer" role="dialog" aria-modal="true" aria-label="资料库">
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
            <button
              className={material.selected ? "material-chip selected" : "material-chip"}
              key={material.id}
              type="button"
              aria-pressed={material.selected}
              onClick={() => onSelectMaterials(selectedCount)}
            >
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
