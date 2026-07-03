import {
  ArrowRight,
  BookOpen,
  ChatCircleText,
  CheckCircle,
  FileArrowUp,
  LinkSimple,
  MagnifyingGlass,
  Microphone,
  Sparkle,
  X
} from "@phosphor-icons/react";
import { type ChangeEvent, type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { buildCoursePath } from "../app/routePaths";
import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { homeConversations } from "../data/demoConversations";
import { useAuthStore } from "../features/auth/authStore";

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

type HomeAnswerPanel = "sources" | "path" | "thinking";

const suggestedPrompts = ["帮我制定 7 天期末复习计划", "把反向传播讲到我能做题", "根据资料生成一门冲刺课"];

export function LearningSpacePage() {
  const user = useAuthStore((state) => state.user);
  const hasStarterContent = user?.starterMode !== "blank";
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const homeChatStageRef = useRef<HTMLElement | null>(null);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<HomeMessage[]>([]);
  const [homeThreads, setHomeThreads] = useState(() => (hasStarterContent ? homeConversations : []));
  const [activeHomeThreadId, setActiveHomeThreadId] = useState<string | null>(null);
  const [materials, setMaterials] = useState<LibraryMaterial[]>(() => (hasStarterContent ? initialLibraryMaterials : []));
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isDeepThinkingEnabled, setIsDeepThinkingEnabled] = useState(false);
  const [isWebSearchEnabled, setIsWebSearchEnabled] = useState(false);
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<HomeAnswerPanel>("sources");
  const [expandedAnswerId, setExpandedAnswerId] = useState<string | null>(null);
  const { notice, showNotice } = useActionNotice();
  const hasHomeThread = messages.length > 0;

  useEffect(() => {
    if (!hasHomeThread) {
      return;
    }

    window.requestAnimationFrame(() => {
      const stage = homeChatStageRef.current;

      if (stage) {
        stage.scrollTop = stage.scrollHeight;
      }
    });
  }, [hasHomeThread, messages.length]);

  function openLibrary(message = "已打开资料库。") {
    setIsLibraryOpen(true);
    showNotice(message);
  }

  function openCourseGeneration() {
    setIsLibraryOpen(false);
    setIsCourseDialogOpen(true);
    showNotice("已打开生成课程。");
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

  function isImageMaterial(file: File) {
    const extension = file.name.split(".").pop()?.toUpperCase();

    return file.type.startsWith("image/") || ["PNG", "JPG", "JPEG", "WEBP"].includes(extension ?? "");
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
      detail: isImageMaterial(file) ? "刚刚上传 · 仅入库，暂不做 OCR" : "刚刚上传 · 等待解析",
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
    const timestamp = Date.now();
    const shouldCreateThread = !activeHomeThreadId || messages.length === 0;
    const nextThreadId = shouldCreateThread ? `home-thread-${timestamp}` : activeHomeThreadId;

    if (!question) {
      showNotice("先输入一个学习问题。", "warning");
      return;
    }

    setMessages((current) => [
      ...current,
      {
        id: `user-${timestamp}`,
        role: "user",
        content: question
      },
      {
        id: `assistant-${timestamp}`,
        role: "assistant",
        content: "可以先把资料按章节和题型拆开：先补核心概念，再用期末题做检索式复习。回答会保留引用和路径建议。"
      }
    ]);
    setHomeThreads((current) => {
      if (shouldCreateThread) {
        return [{ id: nextThreadId, title: question, meta: "刚刚" }, ...current];
      }

      return current.map((thread) => (thread.id === nextThreadId ? { ...thread, meta: "刚刚" } : thread));
    });
    setActiveHomeThreadId(nextThreadId);
    setPrompt("");
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendQuestion();
    }
  }

  function createCourseDraft(selectedCount: number) {
    if (selectedCount === 0) {
      showNotice("请先选择至少一份资料。", "warning");
      return;
    }

    setIsCourseDialogOpen(false);
    setIsLibraryOpen(false);
    showNotice(`已用 ${selectedCount} 份资料创建课程草案，可在最近学习继续完善。`, "success");
  }

  return (
    <LearningSpaceShell hideTopNavigation>
      <div className={["learning-home", isHistoryCollapsed ? "history-collapsed" : "", hasHomeThread ? "chat-active" : ""].filter(Boolean).join(" ")}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar
          isCollapsed={isHistoryCollapsed}
          conversations={homeThreads}
          activeConversationId={activeHomeThreadId}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onNewChat={() => {
            setPrompt("");
            setMessages([]);
            setActiveHomeThreadId(null);
            showNotice("已新建一条主页独立对话。", "success");
          }}
          onSelectConversation={(conversation) => {
            setActiveHomeThreadId(conversation.id);
            setMessages([
              {
                id: `${conversation.id}-user`,
                role: "user",
                content: conversation.title
              },
              {
                id: `${conversation.id}-assistant`,
                role: "assistant",
                content: "我把这段历史对话调出来了。你可以继续追问，也可以把它移入某门课程。"
              }
            ]);
            showNotice(`已切换到「${conversation.title}」。`);
          }}
        />

        <section
          ref={homeChatStageRef}
          className={hasHomeThread ? "home-chat-stage chat-active" : "home-chat-stage"}
          aria-label="AI 学习入口"
        >
          {hasHomeThread ? (
            <section className="home-thread-stage" aria-label="主页对话">
              {messages.map((message) => (
                <article className={`home-message ${message.role}`} key={message.id}>
                  {message.role === "assistant" ? <span className="message-thinking">已思考若干秒</span> : null}
                  <p>{message.content}</p>
                  {message.role === "assistant" ? (
                    <HomeAnswerInsights
                      messageId={message.id}
                      activePanel={activeAnswerPanel}
                      expandedAnswerId={expandedAnswerId}
                      selectedMaterialCount={selectedMaterialIds.length}
                      isWebSearchEnabled={isWebSearchEnabled}
                      onChangePanel={setActiveAnswerPanel}
                      onSetExpandedAnswer={setExpandedAnswerId}
                    />
                  ) : null}
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
            </div>
          )}

          {selectedMaterialIds.length > 0 || isWebSearchEnabled ? (
            <div className="selected-materials-note">
              <LinkSimple size={16} weight="duotone" aria-hidden="true" />
              <span>
                {selectedMaterialIds.length > 0
                  ? `已选择 ${selectedMaterialIds.length} 份资料${isWebSearchEnabled ? "，联网搜索已开" : ""}。`
                  : "联网搜索已开。"}
              </span>
            </div>
          ) : null}
          <ActionNotice notice={notice} className="home-action-notice" />

          <section className={hasHomeThread ? "composer-frame docked" : "composer-frame"} aria-label={hasHomeThread ? "底部学习输入" : "学习输入区"}>
            <div className="conversation-composer">
              <textarea
                aria-label="学习问题输入"
                value={prompt}
                rows={2}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="问学习问题，或用资料生成课程"
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
                      showNotice(isWebSearchEnabled ? "联网搜索已关闭。" : "联网搜索已开启。");
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
                      showNotice(isDeepThinkingEnabled ? "深度思考已关闭。" : "深度思考已开启。");
                    }}
                  >
                    <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
                    <span>思考</span>
                  </button>
                </div>
                <div className="composer-submit-row">
                  <button className="voice-button" type="button" aria-label="语音输入" onClick={() => showNotice("语音输入暂未开启。")}>
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

          {!hasHomeThread ? (
            <div className="home-prompt-row" aria-label="快捷学习建议">
              {suggestedPrompts.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => setPrompt(suggestion)}>
                  {suggestion}
                </button>
              ))}
            </div>
          ) : null}

          {!hasHomeThread && hasStarterContent ? (
            <section className="recent-course-strip" aria-label="最近学习">
              <div className="recent-course-heading">
                <span>最近学习</span>
                <button type="button" onClick={() => showNotice("已显示最近学习。")}>
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
          {!hasHomeThread && !hasStarterContent ? (
            <section className="recent-course-strip empty" aria-label="最近学习">
              <strong>还没有课程</strong>
              <p>上传资料后可直接问，也可生成课程。</p>
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
          onCreate={createCourseDraft}
        />
      ) : null}
    </LearningSpaceShell>
  );
}

type HomeAnswerInsightsProps = {
  messageId: string;
  activePanel: HomeAnswerPanel;
  expandedAnswerId: string | null;
  selectedMaterialCount: number;
  isWebSearchEnabled: boolean;
  onChangePanel: (panel: HomeAnswerPanel) => void;
  onSetExpandedAnswer: (messageId: string | null) => void;
};

function HomeAnswerInsights({
  messageId,
  activePanel,
  expandedAnswerId,
  selectedMaterialCount,
  isWebSearchEnabled,
  onChangePanel,
  onSetExpandedAnswer
}: HomeAnswerInsightsProps) {
  const isExpanded = expandedAnswerId === messageId;
  const handleInsightClick = (panel: HomeAnswerPanel) => {
    const shouldCollapse = isExpanded && activePanel === panel;

    onChangePanel(panel);
    onSetExpandedAnswer(shouldCollapse ? null : messageId);
  };
  const sourceText =
    selectedMaterialCount > 0
      ? `本次回答参考了 ${selectedMaterialCount} 份已选资料${isWebSearchEnabled ? "，并补充联网搜索线索" : ""}。`
      : isWebSearchEnabled
        ? "本次回答会优先显示联网来源，资料库内容未被选入。"
        : "未选择资料时，回答先使用通用学习策略；选择资料后会显示更具体的引用。";

  return (
    <section className="home-answer-insights" aria-label="回答附加信息">
      <div className="answer-insight-tabs" aria-label="回答展开入口">
        <button
          className={isExpanded && activePanel === "sources" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "sources"}
          aria-pressed={isExpanded && activePanel === "sources"}
          onClick={() => handleInsightClick("sources")}
        >
          <LinkSimple size={16} weight="duotone" aria-hidden="true" />
          <span>来源</span>
        </button>
        <button
          className={isExpanded && activePanel === "path" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "path"}
          aria-pressed={isExpanded && activePanel === "path"}
          onClick={() => handleInsightClick("path")}
        >
          <BookOpen size={16} weight="duotone" aria-hidden="true" />
          <span>学习路径</span>
        </button>
        <button
          className={isExpanded && activePanel === "thinking" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "thinking"}
          aria-pressed={isExpanded && activePanel === "thinking"}
          onClick={() => handleInsightClick("thinking")}
        >
          <Sparkle size={16} weight="duotone" aria-hidden="true" />
          <span>思考过程</span>
        </button>
      </div>

      {isExpanded ? (
        <div className="answer-insight-panel" role="region" aria-label="回答展开详情">
          {activePanel === "sources" ? (
            <>
              <span className="insight-mark">
                <CheckCircle size={16} weight="fill" aria-hidden="true" />
                来源
              </span>
              <p>{sourceText}</p>
            </>
          ) : null}
          {activePanel === "path" ? (
            <>
              <span className="insight-mark">
                <BookOpen size={16} weight="fill" aria-hidden="true" />
                下一步
              </span>
              <p>先用 10 分钟补概念，再做 3 道同类题，最后把错因写回画像和复习队列。</p>
            </>
          ) : null}
          {activePanel === "thinking" ? (
            <>
              <span className="insight-mark">
                <Sparkle size={16} weight="fill" aria-hidden="true" />
                处理摘要
              </span>
              <p>已按“目标识别、资料线索、复习动作”整理，真实 Agent 接入后会替换为可追踪执行记录。</p>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

type CourseGenerationDialogProps = {
  onClose: () => void;
};

type CourseGenerationDialogWithNoticeProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onCreate: (selectedCount: number) => void;
};

function CourseGenerationDialog({ materials, selectedMaterialIds, onToggleMaterial, onClose, onCreate }: CourseGenerationDialogWithNoticeProps) {
  const selectedCount = selectedMaterialIds.length;

  return (
    <div className="course-dialog-backdrop">
      <section className="course-dialog" role="dialog" aria-modal="true" aria-labelledby="course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <h2 id="course-dialog-title">从资料生成课程</h2>
        </div>
        <label className="dialog-field">
          <span>课程名称</span>
          <input aria-label="课程名称" defaultValue="人工智能导论期末复习" />
        </label>
        <MaterialFileList materials={materials} selectedMaterialIds={selectedMaterialIds} onToggleMaterial={onToggleMaterial} />
        <div className="dialog-selection-summary">
          <strong>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "先选择要生成课程的资料"}</strong>
          <small>只建立关联，不移动原文件。</small>
        </div>
        <button
          className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button disabled"}
          type="button"
          disabled={selectedCount === 0}
          onClick={() => onCreate(selectedCount)}
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
  const [searchTerm, setSearchTerm] = useState("");
  const visibleMaterials = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    if (!normalizedSearch) {
      return materials;
    }

    return materials.filter((material) =>
      `${material.title} ${material.type} ${material.detail}`.toLowerCase().includes(normalizedSearch)
    );
  }, [materials, searchTerm]);

  return (
    <div className="course-dialog-backdrop">
      <section className="material-drawer" role="dialog" aria-modal="true" aria-labelledby="library-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭资料库" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <h2 id="library-dialog-title">资料库</h2>
        </div>
        <div className="file-library-toolbar">
          <label className="file-search-field">
            <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
            <input aria-label="搜索资料" placeholder="搜索资料" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} />
          </label>
          <button type="button" onClick={onOpenCourseGeneration}>
            <Sparkle size={17} weight="duotone" aria-hidden="true" />
            <span>生成课程</span>
          </button>
        </div>
        <MaterialFileList
          materials={visibleMaterials}
          selectedMaterialIds={selectedMaterialIds}
          onToggleMaterial={onToggleMaterial}
          emptyText={materials.length === 0 ? undefined : "没有匹配的资料。"}
        />
        <div className="library-dialog-footer">
          <span>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "当前未选择资料"}</span>
          <button
            className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button secondary disabled"}
            type="button"
            disabled={selectedCount === 0}
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
  emptyText?: string;
};

function MaterialFileList({ materials, selectedMaterialIds, onToggleMaterial, emptyText = "资料库还是空的，先上传一份课件或试卷。" }: MaterialFileListProps) {
  return (
    <div className="material-file-list" role="list" aria-label="资料库文件列表">
      <div className="material-file-header" aria-hidden="true">
        <span>名称</span>
        <span>修改时间</span>
        <span>大小</span>
      </div>
      {materials.length === 0 ? <p className="material-file-empty">{emptyText}</p> : null}
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
