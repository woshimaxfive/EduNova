import { useQueryClient } from "@tanstack/react-query";
import { type Dispatch, type SetStateAction, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  createTutorResourceGenerationJob,
  createTutorSession,
  getTutorSession,
  streamTutorMessage,
  type TutorSessionSummary
} from "../../api/tutor";
import { PATHS } from "../../app/routePaths";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { appendTutorProgressStage, type TutorResponseProgressState } from "../tutor/tutorResponseProgress";
import type { DraftTutorImage } from "../tutor/useTutorImageDraft";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import type { HomeMessage, PendingHomeResourceGeneration } from "./homeLearningModel";
import { mapTutorMessages } from "./homeLearningModel";

type HomeImageDraft = {
  images: DraftTutorImage[];
  attachmentIds: number[];
  uploading: boolean;
  hasFailed: boolean;
  visionReady: boolean;
  clearAfterSend: () => void;
};

type HomeTutorConversationParams = {
  activeThreadId: string | null;
  onActiveThreadChange: (threadId: string | null) => void;
  onComposerFeedback: (feedback: { message: string; tone: FeedbackTone } | null) => void;
  onPromptChange: Dispatch<SetStateAction<string>>;
  prompt: string;
  upsertHomeThread: (session: TutorSessionSummary) => void;
};

type SendQuestionParams = {
  effectiveMaterialIds: string[];
  imageDraft: HomeImageDraft;
};

export function useHomeTutorConversation({
  activeThreadId,
  onActiveThreadChange,
  onComposerFeedback,
  onPromptChange,
  prompt,
  upsertHomeThread
}: HomeTutorConversationParams) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { jobs, trackJob } = useAiJobs();
  const refreshedResourceJobIds = useRef(new Set<string>());
  const [messages, setMessages] = useState<HomeMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [streamingAnswerId, setStreamingAnswerId] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<TutorResponseProgressState | null>(null);
  const [answerProgress, setAnswerProgress] = useState<Record<string, TutorResponseProgressState & { durationMs: number }>>({});
  const [answerWarnings, setAnswerWarnings] = useState<Record<string, string[]>>({});
  const [pendingResourceGeneration, setPendingResourceGeneration] = useState<PendingHomeResourceGeneration | null>(null);
  const hasHomeThread = messages.length > 0;

  useEffect(() => {
    if (!activeThreadId) return;
    const linkedJobIds = new Set(messages.flatMap((message) => message.resource_jobs?.map((job) => job.job_id) ?? []));
    const terminalJob = jobs.find((job) => linkedJobIds.has(job.job_id)
      && ["completed", "failed", "cancelled"].includes(job.status)
      && !refreshedResourceJobIds.current.has(job.job_id));
    if (!terminalJob) return;
    refreshedResourceJobIds.current.add(terminalJob.job_id);
    void getTutorSession(activeThreadId)
      .then((detail) => setMessages(mapTutorMessages(detail.data.messages)))
      .catch(() => refreshedResourceJobIds.current.delete(terminalJob.job_id));
  }, [activeThreadId, jobs, messages]);

  async function handleSendQuestion({ effectiveMaterialIds, imageDraft }: SendQuestionParams) {
    const question = prompt.trim();
    if (!question && imageDraft.attachmentIds.length === 0) {
      onComposerFeedback({ message: "先输入问题或添加图片。", tone: "warning" });
      return;
    }
    if (imageDraft.uploading || imageDraft.hasFailed) {
      onComposerFeedback({
        message: imageDraft.uploading ? "图片上传完成后才能发送。" : "请移除上传失败的图片后重试。",
        tone: "warning"
      });
      return;
    }
    if (imageDraft.attachmentIds.length > 0 && !imageDraft.visionReady) {
      onComposerFeedback({ message: "图片草稿已保留，请先配置默认图片理解模型。", tone: "warning" });
      return;
    }
    if (isSending) return;

    setIsSending(true);
    onComposerFeedback(null);
    const messagesBeforeSend = messages;
    let optimisticAssistantId: string | null = null;
    let streamWarnings: string[] = [];
    const startedAt = currentTimestamp();
    let progressStages = ["正在读取会话上下文"];

    try {
      let sessionId = activeThreadId;
      if (!sessionId) {
        const created = await createTutorSession({
          scope: "home",
          course_id: null,
          mode: "chat",
          title: buildHomeSessionTitle(question || "图片提问"),
          selected_material_ids: effectiveMaterialIds.map(Number)
        });
        sessionId = created.data.id;
        onActiveThreadChange(sessionId);
      }

      const optimisticKey = createOptimisticKey(sessionId);
      const optimisticUserId = `stream-user-${optimisticKey}`;
      optimisticAssistantId = `stream-assistant-${optimisticKey}`;
      setStreamingAnswerId(optimisticAssistantId);
      setStreamProgress({ startedAt, stages: progressStages });
      setMessages([
        ...messagesBeforeSend,
        {
          id: optimisticUserId,
          role: "user",
          content: question || "请分析并讲解这张图片",
          citation_json: [],
          trace_id: null,
          attachments: imageDraft.images.flatMap((image) => image.attachment ? [image.attachment] : [])
        },
        {
          id: optimisticAssistantId,
          role: "assistant",
          content: "",
          citation_json: [],
          trace_id: null,
          attachments: [],
          streaming: true
        }
      ]);

      const detail = await streamTutorMessage(
        sessionId,
        {
          message: question,
          ...(imageDraft.attachmentIds.length ? { attachment_ids: imageDraft.attachmentIds } : {})
        },
        {
          onMetadata: (metadata) => {
            if (!optimisticAssistantId) return;
            updateMessage(optimisticAssistantId, (message) => ({ ...message, trace_id: metadata.trace_id }));
          },
          onStatus: (status) => {
            progressStages = appendTutorProgressStage(progressStages, status.label);
            setStreamProgress((current) => current ? { ...current, stages: progressStages } : current);
          },
          onSources: (sources) => {
            streamWarnings = sources.warnings;
            if (!optimisticAssistantId) return;
            setAnswerWarnings((current) => ({ ...current, [optimisticAssistantId as string]: sources.warnings }));
            updateMessage(optimisticAssistantId, (message) => ({ ...message, citation_json: sources.citations }));
          },
          onToken: (content) => {
            if (!optimisticAssistantId || !content) return;
            updateMessage(optimisticAssistantId, (message) => ({ ...message, content: message.content + content }));
          },
          onReplace: (replacement) => {
            if (!optimisticAssistantId) return;
            updateMessage(optimisticAssistantId, (message) => ({ ...message, content: replacement.content }));
          }
        }
      );

      const persistedMessages = mapTutorMessages(detail.messages);
      const persistedAssistant = [...persistedMessages].reverse().find((message) => message.role === "assistant");
      const persistedAssistantId = persistedAssistant?.id;
      if (persistedAssistantId) {
        setAnswerProgress((current) => ({
          ...current,
          [persistedAssistantId]: { startedAt, stages: progressStages, durationMs: Date.now() - startedAt }
        }));
      }
      if (persistedAssistantId && streamWarnings.length > 0) {
        setAnswerWarnings((current) => {
          const next = { ...current, [persistedAssistantId]: streamWarnings };
          if (optimisticAssistantId) delete next[optimisticAssistantId];
          return next;
        });
      }
      setMessages(persistedMessages);
      if (persistedAssistantId && persistedAssistant?.resource_proposal?.action === "generate") {
        setPendingResourceGeneration({ sessionId: detail.session.id, messageId: persistedAssistantId });
      }
      onActiveThreadChange(detail.session.id);
      navigate(`${PATHS.app}?session_id=${detail.session.id}`, { replace: true, state: null });
      upsertHomeThread(detail.session);
      onPromptChange("");
      imageDraft.clearAfterSend();
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    } catch (error) {
      setMessages(messagesBeforeSend);
      onComposerFeedback({
        message: error instanceof Error ? error.message : "消息发送失败，请稍后再试。",
        tone: "warning"
      });
    } finally {
      setStreamingAnswerId(null);
      setStreamProgress(null);
      setIsSending(false);
    }
  }

  async function generateResource(courseId: number) {
    if (!pendingResourceGeneration) return;
    try {
      const job = await createTutorResourceGenerationJob(
        pendingResourceGeneration.sessionId,
        pendingResourceGeneration.messageId,
        { course_id: courseId }
      );
      trackJob(job);
      const detail = await getTutorSession(pendingResourceGeneration.sessionId);
      setMessages(mapTutorMessages(detail.data.messages));
      setPendingResourceGeneration(null);
    } catch (error) {
      onComposerFeedback({
        message: error instanceof Error ? error.message : "资源生成任务创建失败，请稍后再试。",
        tone: "warning"
      });
    }
  }

  function updateMessage(messageId: string, update: (message: HomeMessage) => HomeMessage) {
    setMessages((current) => current.map((message) => message.id === messageId ? update(message) : message));
  }

  const restoreMessages = useCallback((nextMessages: HomeMessage[]) => {
    setMessages(nextMessages);
  }, []);

  function resetConversation() {
    setMessages([]);
    setStreamingAnswerId(null);
    setStreamProgress(null);
    setAnswerProgress({});
    setAnswerWarnings({});
    setPendingResourceGeneration(null);
  }

  function openResourceGeneration(messageId: string) {
    if (activeThreadId) setPendingResourceGeneration({ sessionId: activeThreadId, messageId });
  }

  function closeResourceGeneration() {
    setPendingResourceGeneration(null);
  }

  return {
    answerProgress,
    answerWarnings,
    closeResourceGeneration,
    generateResource,
    hasHomeThread,
    isSending,
    messages,
    openResourceGeneration,
    pendingResourceGeneration,
    resetConversation,
    restoreMessages,
    handleSendQuestion,
    streamProgress,
    streamingAnswerId
  };
}

function buildHomeSessionTitle(question: string) {
  return Array.from(question).slice(0, 30).join("");
}

function currentTimestamp() {
  return Date.now();
}

function createOptimisticKey(sessionId: string) {
  return `${Date.now()}-${sessionId}`;
}
