import { type ReactNode } from "react";

import { MarkdownMessage } from "../feedback/MarkdownMessage";

type CourseAssistantTurnProps = {
  messageId?: string;
  content: string;
  status?: string | null;
  actions?: ReactNode;
  detail?: ReactNode;
};

export function CourseAssistantTurn({ messageId, content, status, actions, detail }: CourseAssistantTurnProps) {
  return (
    <article id={messageId ? `course-message-${messageId}` : undefined} className="course-message assistant course-assistant-turn">
      {content ? <MarkdownMessage content={content} /> : status ? <span className="message-thinking" role="status" aria-live="polite">{status}</span> : null}
      {actions}
      {detail ? <div className="course-turn-detail">{detail}</div> : null}
    </article>
  );
}
