import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  createTutorSession,
  getTutorSession,
  listTutorSessions,
  streamTutorMessage,
  type TutorMessage,
  type TutorSessionDetail
} from "../../api/tutor";
import type { ApiEnvelope } from "../../types/api";
import { useBrowserSpeech } from "../speech/useBrowserSpeech";

type UseCourseMentorConversationOptions = {
  courseId: number | null;
  requestedSessionId: string | null;
  contextResourceId: number | null;
  enabled?: boolean;
  onSessionChange: (sessionId: string) => void;
};

export function useCourseMentorConversation({
  courseId,
  requestedSessionId,
  contextResourceId,
  enabled = true,
  onSessionChange
}: UseCourseMentorConversationOptions) {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [streamMessages, setStreamMessages] = useState<TutorMessage[] | null>(null);
  const [isSending, setIsSending] = useState(false);
  const optimisticSequence = useRef(0);
  const speech = useBrowserSpeech({
    onTranscript: (transcript) => setPrompt((current) => current.trim() ? `${current.trim()} ${transcript}` : transcript),
    onNotice: (message) => setFeedback(message)
  });

  const sessionsQuery = useQuery({
    queryKey: ["tutor", "sessions", "course", courseId],
    queryFn: () => listTutorSessions("course", courseId),
    enabled: enabled && courseId !== null,
    staleTime: 10_000
  });
  const sessions = useMemo(() => sessionsQuery.data?.data ?? [], [sessionsQuery.data?.data]);
  const selectedSessionId = sessions.some((session) => session.id === requestedSessionId)
    ? requestedSessionId
    : sessions[0]?.id ?? null;
  const sessionQuery = useQuery({
    queryKey: ["tutor", "session", selectedSessionId],
    queryFn: () => getTutorSession(selectedSessionId ?? ""),
    enabled: enabled && Boolean(selectedSessionId),
    staleTime: 5_000
  });

  useEffect(() => {
    if (selectedSessionId && selectedSessionId !== requestedSessionId) onSessionChange(selectedSessionId);
  }, [onSessionChange, requestedSessionId, selectedSessionId]);

  useEffect(() => {
    if (isSending) return;
    speech.stopListening();
    speech.stopSpeaking();
    // 切换会话时先清除上一会话的临时流式内容，随后由服务端历史恢复。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamMessages(null);
  }, [selectedSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isSending || !sessionQuery.data?.data.messages) return;
    // 服务端会话是刷新恢复的事实来源。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamMessages(sessionQuery.data.data.messages);
  }, [isSending, sessionQuery.data?.data.messages]);

  const messages = streamMessages ?? sessionQuery.data?.data.messages ?? [];

  async function send() {
    const question = prompt.trim();
    if (!question) {
      setFeedback("先输入课程问题，或使用语音输入。");
      return;
    }
    if (courseId === null || isSending) return;

    const previousMessages = messages;
    setIsSending(true);
    setFeedback(null);
    try {
      let sessionId = selectedSessionId;
      if (!sessionId) {
        const created = await createTutorSession({
          scope: "course",
          course_id: courseId,
          mode: "chat",
          title: question.slice(0, 24) || "课程资源提问"
        });
        sessionId = created.data.id;
        onSessionChange(sessionId);
      }

      optimisticSequence.current += 1;
      const sequence = optimisticSequence.current;
      const assistantId = `mentor-assistant-${sequence}`;
      const optimisticMessages: TutorMessage[] = [
        ...previousMessages,
        {
          id: `mentor-user-${sequence}`,
          session_id: sessionId,
          role: "user",
          content: question,
          citation_json: [],
          trace_id: null,
          created_at: new Date().toISOString()
        },
        {
          id: assistantId,
          session_id: sessionId,
          role: "assistant",
          content: "",
          citation_json: [],
          trace_id: null,
          created_at: new Date().toISOString()
        }
      ];
      setStreamMessages(optimisticMessages);

      const detail = await streamTutorMessage(
        sessionId,
        {
          message: question,
          ...(contextResourceId ? { context_resource_id: contextResourceId } : {})
        },
        {
          onToken: (content) => setStreamMessages((current) => (current ?? optimisticMessages).map((message) =>
            message.id === assistantId ? { ...message, content: `${message.content}${content}` } : message
          ))
        }
      );
      setStreamMessages(detail.messages);
      setPrompt("");
      queryClient.setQueryData<ApiEnvelope<TutorSessionDetail>>(
        ["tutor", "session", detail.session.id],
        { data: detail, trace_id: "" }
      );
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", courseId] });
    } catch (error) {
      setStreamMessages(previousMessages);
      setFeedback(error instanceof Error ? error.message : "课程助教暂时不可用，请稍后重试。");
    } finally {
      setIsSending(false);
    }
  }

  function onPromptKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant" && message.content.trim());
  const readLatest = () => {
    if (!latestAssistant) return;
    if (speech.activeSpeechId === latestAssistant.id) speech.stopSpeaking();
    else void speech.speak(latestAssistant.content, latestAssistant.id);
  };

  return {
    prompt,
    setPrompt,
    feedback,
    messages,
    isSending,
    send,
    onPromptKeyDown,
    speech,
    readLatest,
    selectedSessionId
  };
}
