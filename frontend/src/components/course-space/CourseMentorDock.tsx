import * as Popover from "@radix-ui/react-popover";
import {
  ArrowRight,
  ChatCircleText,
  Microphone,
  Pause,
  Play,
  SpeakerHigh,
  SpeakerSlash,
  Sparkle,
  X
} from "@phosphor-icons/react";
import type { KeyboardEvent } from "react";

import type { LearningNextAction } from "../../api/learning";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { MarkdownMessage } from "../feedback/MarkdownMessage";
import "../../styles/course-mentor.css";

export type CourseMentorMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type CourseMentorDockProps = {
  open: boolean;
  courseTitle: string;
  pointTitle: string;
  resourceTitle?: string | null;
  masteryScore: number | null;
  weaknessCount: number;
  recommendation: LearningNextAction | null;
  messages: CourseMentorMessage[];
  prompt: string;
  isSending: boolean;
  feedback: string | null;
  isListening: boolean;
  isTranscribing: boolean;
  isSpeaking: boolean;
  isSpeechPaused: boolean;
  onOpenChange: (open: boolean) => void;
  onPromptChange: (value: string) => void;
  onPromptKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
  onToggleListening: () => void;
  onReadLatest: () => void;
  onPauseOrResume: () => void;
  onStopSpeaking: () => void;
};

export function CourseMentorDock({
  open,
  courseTitle,
  pointTitle,
  resourceTitle,
  masteryScore,
  weaknessCount,
  recommendation,
  messages,
  prompt,
  isSending,
  feedback,
  isListening,
  isTranscribing,
  isSpeaking,
  isSpeechPaused,
  onOpenChange,
  onPromptChange,
  onPromptKeyDown,
  onSend,
  onToggleListening,
  onReadLatest,
  onPauseOrResume,
  onStopSpeaking
}: CourseMentorDockProps) {
  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant" && message.content.trim());
  const subject = resourceTitle || pointTitle;
  const quickQuestions = resourceTitle
    ? [
        "解释这份资源的核心内容",
        "这份资源最容易误解什么",
        "根据这份资源检查我的理解"
      ]
    : [
        `换个例子讲解“${pointTitle}”`,
        `检查我是否理解“${pointTitle}”`,
        `为什么现在学习“${pointTitle}”`
      ];

  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>
        <button
          className={open ? "course-mentor-fab active" : "course-mentor-fab"}
          type="button"
          aria-label={open ? "收起课程助教" : "打开课程助教"}
          aria-expanded={open}
        >
          <Sparkle size={23} weight="fill" aria-hidden="true" />
          {weaknessCount > 0 ? <span className="course-mentor-attention" aria-label="当前知识点有待复习内容" /> : null}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="course-mentor-panel"
          role="dialog"
          aria-label="EduNova 课程助教"
          side="top"
          align="end"
          sideOffset={14}
          collisionPadding={12}
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <header className="course-mentor-header">
            <span className="course-mentor-avatar"><Sparkle size={20} weight="fill" aria-hidden="true" /></span>
            <div>
              <strong>EduNova 课程助教</strong>
              <span>{courseTitle} · {subject}</span>
            </div>
            <Popover.Close aria-label="关闭课程助教"><X size={18} weight="bold" aria-hidden="true" /></Popover.Close>
          </header>

          <section className="course-mentor-context" aria-label="当前学习状态">
            <div><span>掌握度</span><strong>{masteryScore === null ? "待评估" : `${Math.round(masteryScore)} 分`}</strong></div>
            <div><span>待复习</span><strong>{weaknessCount} 项</strong></div>
            <p>{recommendation?.description ?? "继续围绕当前内容学习，问答和练习完成后建议会自动更新。"}</p>
          </section>

          <section className="course-mentor-thread" aria-label="课程助教消息">
            {messages.slice(-6).map((message) => (
              <article className={`course-mentor-message ${message.role}`} key={message.id}>
                {message.role === "assistant" ? <MarkdownMessage content={message.content} /> : <p>{message.content}</p>}
              </article>
            ))}
            {messages.length === 0 ? (
              <div className="course-mentor-empty">
                <ChatCircleText size={22} weight="duotone" aria-hidden="true" />
                <p>围绕当前内容提问，回答会保存在这门课程的会话中。</p>
              </div>
            ) : null}
          </section>

          <div className="course-mentor-quick-actions" aria-label="快捷提问">
            {quickQuestions.map((question) => (
              <button type="button" key={question} onClick={() => onPromptChange(question)}>{question}</button>
            ))}
          </div>

          <footer className="course-mentor-composer">
            <label htmlFor="course-mentor-input">继续问当前内容</label>
            <textarea
              id="course-mentor-input"
              rows={2}
              value={prompt}
              onChange={(event) => onPromptChange(event.target.value)}
              onKeyDown={onPromptKeyDown}
              placeholder="输入问题，Enter 发送，Shift + Enter 换行"
            />
            <div className="course-mentor-controls">
              <button
                type="button"
                aria-label={isTranscribing ? "正在识别" : isListening ? "结束录音" : "语音输入"}
                aria-pressed={isListening}
                disabled={isTranscribing}
                onClick={onToggleListening}
              >
                <Microphone size={18} weight={isListening ? "fill" : "duotone"} aria-hidden="true" />
              </button>
              {latestAssistant && !isSpeaking ? (
                <button type="button" aria-label="朗读最新回答" onClick={onReadLatest}>
                  <SpeakerHigh size={18} weight="duotone" aria-hidden="true" />
                </button>
              ) : null}
              {isSpeaking ? (
                <>
                  <button type="button" aria-label={isSpeechPaused ? "继续朗读" : "暂停朗读"} onClick={onPauseOrResume}>
                    {isSpeechPaused ? <Play size={18} weight="fill" aria-hidden="true" /> : <Pause size={18} weight="fill" aria-hidden="true" />}
                  </button>
                  <button type="button" aria-label="停止朗读" onClick={onStopSpeaking}>
                    <SpeakerSlash size={18} weight="duotone" aria-hidden="true" />
                  </button>
                </>
              ) : null}
              <button className="course-mentor-send" type="button" aria-label="发送问题" disabled={isSending} onClick={onSend}>
                <ArrowRight size={18} weight="bold" aria-hidden="true" />
              </button>
            </div>
            <InlineFeedback message={feedback} tone="warning" className="course-inline-feedback" />
          </footer>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
