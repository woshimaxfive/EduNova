import {
  ArrowRight,
  BookOpen,
  CaretLeft,
  CaretRight,
  ChatCircleText,
  CheckCircle,
  ClockCounterClockwise,
  FileArrowUp,
  GearSix,
  LinkSimple,
  MagnifyingGlass,
  Microphone,
  Plus,
  SignOut,
  Sparkle,
  Student,
  UserCircle,
  X
} from "@phosphor-icons/react";
import { type ChangeEvent, type KeyboardEvent, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { useAuthStore } from "../features/auth/authStore";

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

type LibraryMaterial = {
  id: string;
  title: string;
  type: string;
  detail: string;
  modified: string;
  size: string;
};

const initialLibraryMaterials: LibraryMaterial[] = [
  {
    id: "mat-1",
    title: "人工智能导论课件",
    type: "PPTX",
    detail: "42 页 · 已解析",
    modified: "今天",
    size: "4.8 MB"
  },
  {
    id: "mat-2",
    title: "期末复习题 2025",
    type: "PDF",
    detail: "18 道题 · 已切片",
    modified: "昨天",
    size: "1.6 MB"
  },
  {
    id: "mat-3",
    title: "神经网络课堂讲义",
    type: "DOCX",
    detail: "7 个章节 · 可加入课程",
    modified: "周一",
    size: "820 KB"
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
  const navigate = useNavigate();
  const clearSession = useAuthStore((state) => state.clearSession);
  const user = useAuthStore((state) => state.user);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<HomeMessage[]>([]);
  const [materials, setMaterials] = useState<LibraryMaterial[]>(initialLibraryMaterials);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isDeepThinkingEnabled, setIsDeepThinkingEnabled] = useState(false);
  const [isWebSearchEnabled, setIsWebSearchEnabled] = useState(false);
  const { notice, showNotice } = useActionNotice();
  const hasHomeThread = messages.length > 0;

  function openLibrary(message = "已打开资料库。") {
    setIsLibraryOpen(true);
    showNotice(message);
  }

  function openCourseGeneration() {
    setIsCourseDialogOpen(true);
    showNotice("已打开从资料生成课程面板。");
  }

  function logout() {
    clearSession();
    navigate(PATHS.login);
  }

  function formatFileSize(size: number) {
    if (size >= 1024 * 1024) {
      return `${(size / 1024 / 1024).toFixed(1)} MB`;
    }

    if (size >= 1024) {
      return `${Math.ceil(size / 1024)} KB`;
    }

    return `${size} B`;
  }

  function inferMaterialType(fileName: string) {
    const extension = fileName.split(".").pop()?.toUpperCase();

    return extension && extension.length <= 5 ? extension : "FILE";
  }

  function handleUploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const uploadedMaterial: LibraryMaterial = {
      id: `upload-${Date.now()}`,
      title: file.name,
      type: inferMaterialType(file.name),
      detail: "刚刚上传 · 等待解析",
      modified: "刚刚",
      size: formatFileSize(file.size)
    };

    setMaterials((current) => [uploadedMaterial, ...current]);
    showNotice(`${file.name} 已上传到资料库。`, "success");
    event.target.value = "";
  }

  function toggleMaterialSelection(materialId: string) {
    setSelectedMaterialIds((current) => {
      const next = current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId];

      showNotice(next.length > 0 ? `已选择 ${next.length} 份资料。` : "已清空本次参考资料。", next.length > 0 ? "success" : "info");

      return next;
    });
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

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendQuestion();
    }
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
          <div className="home-account-section" aria-label="账号入口">
            <Link className="home-account-link" to={PATHS.profile}>
              <UserCircle size={18} weight="duotone" aria-hidden="true" />
              <span>个人资料</span>
            </Link>
            <Link className="home-account-link" to={PATHS.settings}>
              <GearSix size={18} weight="duotone" aria-hidden="true" />
              <span>设置</span>
            </Link>
            <button className="home-account-link" type="button" onClick={logout}>
              <SignOut size={18} weight="duotone" aria-hidden="true" />
              <span>退出登录</span>
            </button>
            <div className="home-user-mini">
              <span>{user?.displayName?.slice(0, 1) ?? "学"}</span>
              <strong>{user?.displayName ?? "演示学生"}</strong>
            </div>
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
                onKeyDown={handleComposerKeyDown}
                placeholder="问我怎么复习，或者说：用这些资料生成一门期末复习课"
              />
              <div className="composer-actions">
                <div className="composer-toolbar" aria-label="输入工具">
                  <input
                    ref={uploadInputRef}
                    className="visually-hidden"
                    type="file"
                    aria-label="上传资料文件"
                    accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg"
                    onChange={handleUploadFile}
                  />
                  <button
                    type="button"
                    aria-label="上传资料"
                    onClick={() => uploadInputRef.current?.click()}
                  >
                    <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
                    <span>上传</span>
                  </button>
                  <button type="button" aria-label="打开资料库" onClick={() => openLibrary()}>
                    <BookOpen size={18} weight="duotone" aria-hidden="true" />
                    <span>资料库</span>
                  </button>
                  <button type="button" onClick={openCourseGeneration}>
                    <Sparkle size={18} weight="duotone" aria-hidden="true" />
                    <span>生成课程</span>
                  </button>
                  <button
                    className={isWebSearchEnabled ? "active" : ""}
                    type="button"
                    aria-label="联网搜索"
                    aria-pressed={isWebSearchEnabled}
                    onClick={() => {
                      setIsWebSearchEnabled((enabled) => !enabled);
                      showNotice(isWebSearchEnabled ? "已关闭联网搜索演示态。" : "已开启联网搜索，回答会显示来源入口。");
                    }}
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
                </div>
                <div className="composer-submit-row">
                  <button className="voice-button" type="button" aria-label="语音输入" onClick={() => showNotice("语音输入会在浏览器录音权限流程接入后开放。")}>
                    <Microphone size={18} weight="duotone" aria-hidden="true" />
                  </button>
                  <button className="ask-button" type="button" onClick={handleSendQuestion}>
                    <ArrowRight size={18} weight="bold" aria-hidden="true" />
                    <span>发送</span>
                  </button>
                </div>
              </div>
            </div>
          </section>

          <div className="selected-materials-note">
            <LinkSimple size={16} weight="duotone" aria-hidden="true" />
            <span>
              {selectedMaterialIds.length > 0
                ? `已选择 ${selectedMaterialIds.length} 份资料，回答时会像联网搜索一样显示来源。`
                : "可以从资料库选择资料；联网搜索开启后也会显示来源。"}
            </span>
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

      {isLibraryOpen ? (
        <MaterialLibraryDrawer
          materials={materials}
          selectedMaterialIds={selectedMaterialIds}
          onToggleMaterial={toggleMaterialSelection}
          onOpenCourseGeneration={openCourseGeneration}
          onClose={() => setIsLibraryOpen(false)}
          showNotice={showNotice}
        />
      ) : null}
      {isCourseDialogOpen ? (
        <CourseGenerationDialog
          materials={materials}
          selectedMaterialIds={selectedMaterialIds}
          onToggleMaterial={toggleMaterialSelection}
          onClose={() => setIsCourseDialogOpen(false)}
          showNotice={showNotice}
        />
      ) : null}
    </LearningSpaceShell>
  );
}

type CourseGenerationDialogProps = {
  onClose: () => void;
};

type CourseGenerationDialogWithNoticeProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  showNotice: (message: string, tone?: "info" | "success" | "warning") => void;
};

function CourseGenerationDialog({ materials, selectedMaterialIds, onToggleMaterial, onClose, showNotice }: CourseGenerationDialogWithNoticeProps) {
  const selectedCount = selectedMaterialIds.length;

  return (
    <div className="course-dialog-backdrop">
      <section className="course-dialog" role="dialog" aria-modal="true" aria-labelledby="course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <p className="section-kicker">Course builder</p>
          <h2 id="course-dialog-title">从资料生成课程</h2>
          <p>选择资料库里的课件、电子书或期末题，EduNova 会把它们整理成课程草案。主页对话仍可独立保留。</p>
        </div>
        <label className="dialog-field">
          <span>课程名称</span>
          <input aria-label="课程名称" defaultValue="人工智能导论期末复习" />
        </label>
        <MaterialFileList materials={materials} selectedMaterialIds={selectedMaterialIds} onToggleMaterial={onToggleMaterial} />
        <div className="dialog-selection-summary">
          <strong>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "先选择要生成课程的资料"}</strong>
          <small>资料仍保存在资料库中，生成课程时只建立关联，不移动原文件。</small>
        </div>
        <button
          className="dialog-primary-button"
          type="button"
          onClick={() =>
            showNotice(selectedCount > 0 ? "已创建课程草案演示态，真实创建会接入课程 API。" : "请先选择至少一份资料。", selectedCount > 0 ? "success" : "warning")
          }
        >
          创建课程草案
        </button>
      </section>
    </div>
  );
}

type MaterialLibraryDrawerProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onOpenCourseGeneration: () => void;
  showNotice: (message: string, tone?: "info" | "success" | "warning") => void;
};

function MaterialLibraryDrawer({ materials, selectedMaterialIds, onToggleMaterial, onOpenCourseGeneration, onClose, showNotice }: MaterialLibraryDrawerProps) {
  const selectedCount = selectedMaterialIds.length;

  return (
    <div className="course-dialog-backdrop">
      <section className="material-drawer" role="dialog" aria-modal="true" aria-labelledby="library-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭资料库" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <p className="home-kicker">资料库</p>
          <h2 id="library-dialog-title">学习资料库</h2>
          <p>所有上传资料都先独立保存。需要用于本次对话时再手动选择，高亮后才会作为参考。</p>
        </div>
        <div className="file-library-toolbar">
          <label className="file-search-field">
            <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
            <input aria-label="搜索资料" placeholder="搜索资料" />
          </label>
          <button type="button" onClick={onOpenCourseGeneration}>
            <Sparkle size={17} weight="duotone" aria-hidden="true" />
            <span>生成课程</span>
          </button>
        </div>
        <MaterialFileList materials={materials} selectedMaterialIds={selectedMaterialIds} onToggleMaterial={onToggleMaterial} />
        <div className="library-dialog-footer">
          <span>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "当前未选择资料"}</span>
          <button
            className="dialog-primary-button"
            type="button"
            onClick={() =>
              showNotice(selectedCount > 0 ? `本次对话将参考 ${selectedCount} 份资料。` : "先点选资料，再作为对话参考。", selectedCount > 0 ? "success" : "warning")
            }
          >
            作为本次对话参考
          </button>
        </div>
      </section>
    </div>
  );
}

type MaterialFileListProps = {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
};

function MaterialFileList({ materials, selectedMaterialIds, onToggleMaterial }: MaterialFileListProps) {
  return (
    <div className="material-file-list" role="list" aria-label="资料库文件列表">
      <div className="material-file-header" aria-hidden="true">
        <span>名称</span>
        <span>修改时间</span>
        <span>大小</span>
      </div>
      {materials.map((material) => {
        const isSelected = selectedMaterialIds.includes(material.id);

        return (
          <button
            className={isSelected ? "material-file-row selected" : "material-file-row"}
            key={material.id}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onToggleMaterial(material.id)}
          >
            <span className="material-file-type">{material.type}</span>
            <span className="material-file-main">
              <strong>{material.title}</strong>
              <small>{material.detail}</small>
            </span>
            <span className="material-file-meta">{material.modified}</span>
            <span className="material-file-meta">{material.size}</span>
            {isSelected ? <CheckCircle size={18} weight="duotone" aria-hidden="true" /> : null}
          </button>
        );
      })}
    </div>
  );
}
