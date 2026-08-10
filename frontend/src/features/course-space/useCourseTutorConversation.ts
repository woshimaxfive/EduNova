import { type QueryClient, useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import {
  createTutorResourceGenerationJob,
  createTutorSession,
  deleteTutorSession,
  getTutorSession,
  listTutorSessions,
  renameTutorSession,
  streamTutorMessage,
  type TutorSessionSummary
} from "../../api/tutor";
import type { CourseWorkspaceMode } from "../../components/course-space/CourseWorkspaceHeader";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { useBrowserSpeech } from "../speech/useBrowserSpeech";
import { appendTutorProgressStage, type TutorResponseProgressState } from "../tutor/tutorResponseProgress";
import { useTutorPersistedResponseProgress } from "../tutor/useTutorPersistedResponseProgress";
import { invalidateCourseLearningLoop } from "./courseLoopQueries";
import {
  courseQuestionTitle,
  mapCourseSessionsToConversations,
  mapTutorMessagesToCourseMessages,
  sanitizeCourseAnswerContent,
  type CourseMessage
} from "./courseConversation";
import { useCourseTutorAttachments } from "./useCourseTutorAttachments";

type TutorSessionsResponse = Awaited<ReturnType<typeof listTutorSessions>>;
type SearchParamsSetter = (next: URLSearchParams, options?: { replace?: boolean }) => void;

type CourseTutorConversationParams = {
  activeTurnMessageId: string | null;
  courseId: number;
  courseMode: CourseWorkspaceMode;
  enabled: boolean;
  queryClient: QueryClient;
  resetWorkspace: () => void;
  searchParams: URLSearchParams;
  sessions: TutorSessionSummary[];
  setSearchParams: SearchParamsSetter;
};

const COURSE_COMPOSER_MAX_HEIGHT = 154;

export function useCourseTutorConversation({
  activeTurnMessageId,
  courseId,
  courseMode,
  enabled,
  queryClient,
  resetWorkspace,
  searchParams,
  sessions,
  setSearchParams
}: CourseTutorConversationParams) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<CourseMessage[]>([]);
  const [streamingSessionId, setStreamingSessionId] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<TutorResponseProgressState | null>(null);
  const [answerProgress, setAnswerProgress] = useState<Record<string, TutorResponseProgressState & { durationMs: number }>>({});
  const [isSending, setIsSending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const optimisticMessageSequence = useRef(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const { trackJob } = useAiJobs();
  const speech = useBrowserSpeech({
    onTranscript: (transcript) => setPrompt((current) => current.trim() ? `${current.trim()} ${transcript}` : transcript),
    onNotice: (message) => setFeedback(message)
  });

  const latestSessionId = sessions[0]?.id ?? null;
  const requestedSessionId = searchParams.get("course_session_id");
  const requestedMessageId = searchParams.get("course_message_id");
  const restorableSessionId = sessions.some((session) => session.id === requestedSessionId)
    ? requestedSessionId
    : null;
  const selectedSessionId = enabled
    ? (activeSessionId ?? restorableSessionId ?? latestSessionId)
    : null;
  const activeSessionQuery = useQuery({
    queryKey: ["tutor", "session", selectedSessionId],
    queryFn: () => getTutorSession(selectedSessionId ?? ""),
    enabled: enabled && Boolean(selectedSessionId),
    staleTime: 5_000
  });
  const activeSessionDetail = activeSessionQuery.data?.data;
  const activeSessionDetailId = activeSessionDetail?.session?.id ?? null;
  const persistedMessages = enabled && activeSessionDetailId === selectedSessionId
    ? mapTutorMessagesToCourseMessages(activeSessionDetail?.messages ?? [])
    : [];
  const displayedMessages = streamingSessionId !== null
    ? messages
    : enabled && selectedSessionId && activeSessionDetailId === selectedSessionId
      ? persistedMessages
      : messages;
  const persistedAnswerProgress = useTutorPersistedResponseProgress(
    displayedMessages
      .filter((message) => message.role === "assistant")
      .map((message) => ({ messageId: message.id, traceId: message.traceId })),
    activeTurnMessageId
  );
  const imageDraft = useCourseTutorAttachments({
    courseId,
    enabled,
    selectedSessionId,
    queryClient,
    setActiveSessionId,
    setFeedback
  });
  const sidebarConversations = enabled ? mapCourseSessionsToConversations(sessions) : [];
  const hasDisplayedMessages = displayedMessages.length > 0;
  const latestMessageSignature = displayedMessages.length > 0
    ? `${displayedMessages.at(-1)?.id ?? ""}:${displayedMessages.at(-1)?.content.length ?? 0}`
    : "empty";

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    const nextHeight = Math.min(input.scrollHeight, COURSE_COMPOSER_MAX_HEIGHT);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > COURSE_COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
  }, [prompt]);

  useEffect(() => {
    if (courseMode !== "chat" || !hasDisplayedMessages) return;
    const frame = window.requestAnimationFrame(() => {
      const requestedTarget = requestedMessageId
        ? document.getElementById(`course-message-${requestedMessageId}`)
        : null;
      const target = requestedTarget ?? chatEndRef.current;
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ block: requestedTarget ? "center" : "end" });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [courseMode, hasDisplayedMessages, latestMessageSignature, requestedMessageId, selectedSessionId]);

  function selectConversation(sessionId: string) {
    if (!enabled) return;
    speech.stopListening();
    speech.stopSpeaking();
    imageDraft.discardAll();
    setActiveSessionId(sessionId);
    setStreamingSessionId(null);
    setMessages([]);
    resetWorkspace();
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "chat");
    nextParams.set("view", "overview");
    nextParams.set("course_session_id", sessionId);
    nextParams.delete("course_message_id");
    nextParams.delete("panel");
    nextParams.delete("detail");
    nextParams.delete("mentor");
    setSearchParams(nextParams, { replace: true });
  }

  async function createConversation() {
    if (!enabled) return;
    speech.stopListening();
    speech.stopSpeaking();
    imageDraft.discardAll();
    setPrompt("");
    setMessages([]);
    resetWorkspace();
    try {
      const created = await createTutorSession({
        scope: "course",
        course_id: courseId,
        mode: "chat",
        title: "新建课程对话"
      });
      setActiveSessionId(created.data.id);
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("mode", "chat");
      nextParams.set("view", "overview");
      nextParams.set("course_session_id", created.data.id);
      nextParams.delete("course_message_id");
      nextParams.delete("knowledge_point_id");
      nextParams.delete("panel");
      nextParams.delete("detail");
      setSearchParams(nextParams, { replace: true });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
    } catch {
      setFeedback("新建课程对话失败，请稍后重试。");
    }
  }

  function updateSessionList(updater: (current: TutorSessionSummary[]) => TutorSessionSummary[]) {
    queryClient.setQueryData<TutorSessionsResponse>(["tutor", "sessions", "course", courseId], (current) =>
      current ? { ...current, data: updater(current.data) } : current
    );
  }

  async function renameConversation(conversation: { id: string; title: string }, title: string) {
    const normalizedTitle = title.trim();
    if (!enabled || !normalizedTitle) return;
    try {
      const renamed = await renameTutorSession(conversation.id, { title: normalizedTitle });
      updateSessionList((current) =>
        current.map((session) => session.id === conversation.id ? { ...session, title: renamed.data.title } : session)
      );
      setFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
    } catch {
      setFeedback("会话改名失败，请稍后重试。");
    }
  }

  async function deleteConversation(conversation: { id: string }) {
    if (!enabled) return;
    try {
      await deleteTutorSession(conversation.id);
      updateSessionList((current) => current.filter((session) => session.id !== conversation.id));
      queryClient.removeQueries({ queryKey: ["tutor", "session", conversation.id] });
      if (selectedSessionId === conversation.id || activeSessionId === conversation.id) {
        setActiveSessionId(null);
        setStreamingSessionId(null);
        setMessages([]);
        resetWorkspace();
        const nextParams = new URLSearchParams(searchParams);
        nextParams.delete("course_session_id");
        nextParams.delete("course_message_id");
        nextParams.delete("mentor");
        setSearchParams(nextParams, { replace: true });
      }
      setFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
    } catch {
      setFeedback("会话删除失败，请稍后重试。");
    }
  }

  function toggleReadMessage(message: CourseMessage) {
    if (speech.activeSpeechId === message.id) {
      speech.stopSpeaking();
      return;
    }
    speech.speak(sanitizeCourseAnswerContent(message.content), message.id);
  }

  async function sendQuestion() {
    const question = prompt.trim();
    if (!question && imageDraft.attachmentIds.length === 0) {
      setFeedback("先输入课程问题或添加图片。");
      return;
    }
    if (imageDraft.uploading || imageDraft.hasFailed) {
      setFeedback(imageDraft.uploading ? "图片上传完成后才能发送。" : "请移除上传失败的图片后重试。");
      return;
    }
    if (imageDraft.attachmentIds.length > 0 && !imageDraft.visionReady) {
      setFeedback("图片草稿已保留，请先配置默认图片理解模型。");
      return;
    }
    if (isSending) return;
    if (!enabled) {
      setFeedback("课程地址无效，请从课程列表重新进入。");
      return;
    }

    setIsSending(true);
    const startedAt = Date.now();
    let progressStages = ["正在准备课程回答"];
    setStreamProgress({ startedAt, stages: progressStages });
    setFeedback(null);
    const previousMessages = displayedMessages;

    try {
      let sessionId = selectedSessionId;
      if (!sessionId) {
        const createdSession = await createTutorSession({
          scope: "course",
          course_id: courseId,
          mode: "chat",
          title: courseQuestionTitle(question || "图片提问")
        });
        sessionId = createdSession.data.id;
      }

      setActiveSessionId(sessionId);
      setStreamingSessionId(sessionId);
      optimisticMessageSequence.current += 1;
      const optimisticId = optimisticMessageSequence.current;
      const assistantMessageId = `course-assistant-stream-${optimisticId}`;
      setMessages([
        ...previousMessages,
        {
          id: `course-user-stream-${optimisticId}`,
          role: "user",
          content: question || "请分析并讲解这张图片",
          attachments: imageDraft.images.flatMap((image) => image.attachment ? [image.attachment] : [])
        },
        { id: assistantMessageId, role: "assistant", content: "", citations: [], attachments: [] }
      ]);

      const detail = await streamTutorMessage(sessionId, {
        message: question,
        ...(imageDraft.attachmentIds.length ? { attachment_ids: imageDraft.attachmentIds } : {})
      }, {
        onStatus: (status) => {
          progressStages = appendTutorProgressStage(progressStages, status.label);
          setStreamProgress((current) => current ? { ...current, stages: progressStages } : current);
        },
        onToken: (content) => {
          setMessages((current) => current.map((message) =>
            message.id === assistantMessageId ? { ...message, content: `${message.content}${content}` } : message
          ));
        }
      });
      let persistedMessages = mapTutorMessagesToCourseMessages(detail.messages);
      const persistedAssistant = [...persistedMessages].reverse().find((message) => message.role === "assistant");
      if (persistedAssistant?.resourceProposal?.action === "generate") {
        try {
          const job = await createTutorResourceGenerationJob(detail.session.id, persistedAssistant.id, { course_id: courseId });
          trackJob(job);
          const refreshed = await getTutorSession(detail.session.id);
          persistedMessages = mapTutorMessagesToCourseMessages(refreshed.data.messages);
        } catch (resourceError) {
          setFeedback(resourceError instanceof Error ? resourceError.message : "回答已保存，但资源任务创建失败，请在回答下方重试。");
        }
      }

      setActiveSessionId(detail.session.id);
      setMessages(persistedMessages);
      setStreamingSessionId(null);
      setStreamProgress(null);
      setPrompt("");
      imageDraft.clearAfterSend();
      if (persistedAssistant) {
        setAnswerProgress((current) => ({
          ...current,
          [persistedAssistant.id]: { startedAt, stages: progressStages, durationMs: Date.now() - startedAt }
        }));
      }
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("course_session_id", detail.session.id);
      if (persistedAssistant) nextParams.set("course_message_id", persistedAssistant.id);
      setSearchParams(nextParams, { replace: true });
      queryClient.setQueryData(["tutor", "session", detail.session.id], { data: detail, trace_id: null });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
      void invalidateCourseLearningLoop(queryClient, courseId);
    } catch (error) {
      setMessages(previousMessages);
      setStreamingSessionId(null);
      setStreamProgress(null);
      setFeedback(error instanceof Error ? error.message : "模型暂不可用，请检查设置或稍后重试。");
    } finally {
      setIsSending(false);
    }
  }

  async function generateSuggestedResources(message: CourseMessage) {
    if (!selectedSessionId || !enabled || !message.resourceProposal) return;
    try {
      const job = await createTutorResourceGenerationJob(selectedSessionId, message.id, { course_id: courseId });
      trackJob(job);
      const refreshed = await getTutorSession(selectedSessionId);
      setMessages(mapTutorMessagesToCourseMessages(refreshed.data.messages));
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "资源生成任务创建失败，请稍后再试。");
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion();
    }
  }

  return {
    answerProgress,
    chatEndRef,
    createConversation,
    deleteConversation,
    displayedMessages,
    feedback,
    generateSuggestedResources,
    handleComposerKeyDown,
    hasDisplayedMessages,
    imageDraft,
    inputRef,
    isSending,
    persistedAnswerProgress,
    prompt,
    renameConversation,
    selectConversation,
    selectedSessionId,
    sendQuestion,
    setPrompt,
    sidebarConversations,
    speech,
    streamProgress,
    toggleReadMessage
  };
}
